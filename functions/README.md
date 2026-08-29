# "Get Your VTL Analysis" backend

Two Cloudflare Pages Functions, deployed automatically as part of the
normal publish (`python publish.py` copies this folder to
`output/functions/`, which gets mirrored into `vertlabs-web` like
everything else). No Node.js, no external backend service, no access to
the private Terrain Intelligence Engine - just the two files here,
running on Cloudflare's edge runtime.

- `api/analysis-request.js` - `POST /api/analysis-request`. Validates
  the form, verifies Turnstile, stores the GPX in R2, emails a
  notification via Resend.
- `api/analysis-gpx/[[path]].js` - `GET /api/analysis-gpx/*`. The only
  way to read a stored GPX back out - gated by `ADMIN_TOKEN`, since the
  R2 bucket itself is never made public.

## One-time setup (Cloudflare dashboard)

All of this is done once, in the Cloudflare dashboard for the
`vertlabs-web` Pages project - nothing here needs a code change.

1. **R2 bucket.** Cloudflare dashboard -> R2 -> Create bucket (e.g.
   `vtl-analysis-requests`). Leave it private - do **not** enable public
   access or connect a custom domain to it. Then: Pages project ->
   Settings -> Functions -> R2 bucket bindings -> add a binding named
   exactly `GPX_BUCKET` pointing at that bucket.

2. **Turnstile.** Cloudflare dashboard -> Turnstile -> Add site, domain
   `vertlabs.run`, widget mode "Managed". You get a **Site Key** (public)
   and a **Secret Key** (private).
   - Site Key: paste it into `builder/env.py`, replacing the placeholder
     `env.globals["turnstile_site_key"]` value. This is safe to commit -
     Turnstile site keys are meant to be public.
   - Secret Key: set as the `TURNSTILE_SECRET_KEY` env var below.

3. **Resend** (email). Create a free account at resend.com, verify the
   `vertlabs.run` sending domain (Resend walks you through the DNS
   records), then create an API key.

4. **Admin token.** Generate one long random string yourself, e.g.:
   ```
   openssl rand -hex 32
   ```
   This becomes `ADMIN_TOKEN` below - it's what the GPX download link in
   the notification email is authenticated with. Don't reuse it anywhere
   else.

5. **Environment variables.** Pages project -> Settings -> Environment
   variables, for the **Production** environment (and Preview too, if
   you want the `staging` branch to also be able to send test emails):

   | Name                   | Type   | Value                                    |
   |------------------------|--------|-------------------------------------------|
   | `TURNSTILE_SECRET_KEY` | Secret | from step 2                                |
   | `RESEND_API_KEY`       | Secret | from step 3                                |
   | `ADMIN_TOKEN`          | Secret | from step 4                                |
   | `NOTIFY_EMAIL`         | Plain  | the inbox that should receive requests     |
   | `PUBLIC_SITE_URL`      | Plain  | `https://vertlabs.run`                     |

   The `GPX_BUCKET` binding from step 1 is separate from these (it's a
   binding, not a plain env var) but shows up alongside them in the same
   Settings page.

## What happens without this setup

The form still works end-to-end without every piece configured, just
degraded:

- No `TURNSTILE_SECRET_KEY` set -> the check passes open (doesn't block
  real submissions, but also doesn't block bots) - configure it before
  relying on this in production.
- No `GPX_BUCKET` binding -> every submission fails with a clean
  `server_error` response (nothing is silently lost or misfiled).
- No `RESEND_API_KEY`/`NOTIFY_EMAIL` -> the GPX is still safely stored in
  R2, the visitor still sees "Request Received", but no notification
  email goes out - you'd only find the request by browsing the R2
  bucket directly until these are set.

## Limits

- Max GPX size: 15 MB (enforced in both `assets/js/analysis-form.js` and
  `functions/api/analysis-request.js` - the server-side check is the
  real one, the client-side one is just faster feedback).
- Upload must be named `*.gpx` **and** contain a recognizable
  `<gpx ...>`/`<?xml` tag in its first 400 bytes - a renamed non-GPX file
  is rejected either way.

## Testing the full flow

1. Deploy with the env vars above set (staging branch first is fine -
   Pages Functions run on preview deploys too).
2. Go to `/analysis/` on that deploy, fill the form with a real .gpx
   file, submit.
3. You should see "Request Received" in the page, and a notification
   email should land at `NOTIFY_EMAIL` within a few seconds, with a
   "GPX file: https://.../api/analysis-gpx/...?token=..." link - click
   it to confirm it downloads the exact file you uploaded.
4. Try the same link with the token removed/wrong -> should 404.
5. Try submitting the GPX field with a renamed `.txt` file -> should be
   rejected client-side immediately, and server-side too if you bypass
   the client check (e.g. via curl).
