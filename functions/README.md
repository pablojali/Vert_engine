# "Get Your VTL Analysis" backend

One Cloudflare Pages Function, deployed automatically as part of the
normal publish (`python publish.py` copies this folder to
`output/functions/`, which gets mirrored into `vertlabs-web` like
everything else). No Node.js, no external backend service, no file
storage, no access to the private Terrain Intelligence Engine - just
`api/analysis-request.js`, running on Cloudflare's edge runtime.

`POST /api/analysis-request` validates the form, verifies Turnstile,
and emails it to VTL via Resend with the **GPX attached directly to the
email**. GPX files submitted through this form are small (a few MB at
most), so there's no separate file storage (R2 or otherwise, which has
a cost) - the GPX is never persisted anywhere server-side, it only ever
exists in memory for the length of the request and then in the
resulting email.

## One-time setup (Cloudflare dashboard)

All of this is done once, in the Cloudflare dashboard for the
`vertlabs-web` Pages project - nothing here needs a code change.

1. **Turnstile.** Cloudflare dashboard -> Turnstile -> Add site, domain
   `vertlabs.run`, widget mode "Managed". You get a **Site Key** (public)
   and a **Secret Key** (private).
   - Site Key: paste it into `builder/env.py`, replacing the placeholder
     `env.globals["turnstile_site_key"]` value. This is safe to commit -
     Turnstile site keys are meant to be public.
   - Secret Key: set as the `TURNSTILE_SECRET_KEY` env var below.

2. **Resend** (email). Create a free account at resend.com, verify a
   sending domain there (Resend walks you through the DNS records) -
   **use a subdomain** like `notify.vertlabs.run` rather than the bare
   `vertlabs.run`, so it can never collide with your real mailboxes'
   MX records (e.g. Migadu). Then create an API key **in that same
   Resend project**. The `from` address in
   `functions/api/analysis-request.js` must exactly match whatever
   domain you verified - if you use a different subdomain, update that
   line too.

3. **Environment variables.** Pages project -> Settings -> Environment
   variables, for the **Production** environment (and Preview too, if
   you want the `staging` branch to also be able to send test emails):

   | Name                   | Type   | Value                                          |
   |------------------------|--------|-------------------------------------------------|
   | `TURNSTILE_SECRET_KEY` | Secret | from step 1                                     |
   | `RESEND_API_KEY`       | Secret | from step 2                                     |
   | `NOTIFY_EMAIL`         | Plain  | the inbox that should receive requests (your choice - doesn't have to be hello@vertlabs.run) |

That's the whole setup - no bucket, no binding, no admin token.

## What happens without this setup

The form still responds cleanly without every piece configured:

- No `TURNSTILE_SECRET_KEY` set -> the check passes open (doesn't block
  real submissions, but also doesn't block bots) - configure it before
  relying on this in production.
- No `RESEND_API_KEY` or `NOTIFY_EMAIL` -> every submission fails with a
  clean `server_error` response and the visitor is told something went
  wrong (nothing is silently lost, but nothing is silently saved either
  - there's no fallback storage once you remove R2 from the picture, so
  configure Resend before considering this live).

## Limits

- Max GPX size: 8 MB (enforced in both `assets/js/analysis-form.js` and
  `functions/api/analysis-request.js` - the server-side check is the
  real one, the client-side one is just faster feedback). Kept
  deliberately well under typical inbox attachment limits (Gmail caps
  incoming mail around 25 MB) since base64-encoding an attachment
  inflates it by about a third - real GPX files are almost always a few
  MB at most, so this is generous headroom, not a tight squeeze.
- Upload must be named `*.gpx` **and** contain a recognizable
  `<gpx ...>`/`<?xml` tag in its first 400 bytes - a renamed non-GPX file
  is rejected either way.

## Testing the full flow

1. Deploy with the env vars above set (staging branch first is fine -
   Pages Functions run on preview deploys too).
2. Go to `/analysis/` on that deploy, fill the form with a real .gpx
   file, submit.
3. You should see "Request Received" in the page, and a notification
   email should land at `NOTIFY_EMAIL` within a few seconds, with the
   GPX file attached - open it to confirm it's the exact file you
   uploaded.
4. Try submitting the GPX field with a renamed `.txt` file -> should be
   rejected client-side immediately, and server-side too if you bypass
   the client check (e.g. via curl).
