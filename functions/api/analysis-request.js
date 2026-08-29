// Cloudflare Pages Function: POST /api/analysis-request
//
// Receives the "Get Your VTL Analysis" form (multipart/form-data),
// validates it, verifies Turnstile, stores the GPX privately in R2, and
// emails a notification via Resend. Runs entirely on Cloudflare's edge
// using only Web-standard APIs (fetch, FormData, crypto, R2 bindings) -
// no Node.js APIs, and no access whatsoever to the private Terrain
// Intelligence Engine (a completely separate, private codebase/repo).
//
// Required bindings/env vars - set in Cloudflare Pages ->
// Settings -> Environment variables (secrets) / Bindings:
//
//   GPX_BUCKET            R2 bucket binding. Create a bucket, bind it
//                         here under this exact name. Never enable
//                         public access on it - this Function is the
//                         only door in.
//   TURNSTILE_SECRET_KEY  secret - from the Turnstile widget you create
//                         in the Cloudflare dashboard (Turnstile -> Add
//                         site). The matching public "site key" goes in
//                         builder/env.py (not a secret, safe in git).
//   RESEND_API_KEY        secret - from https://resend.com (free tier
//                         is enough for this volume). Verify the
//                         vertlabs.run sending domain there first.
//   NOTIFY_EMAIL          plain var - where the notification lands.
//   ADMIN_TOKEN           secret - a long random string you generate
//                         yourself (e.g. `openssl rand -hex 32`). Gates
//                         /api/analysis-gpx/* downloads.
//   PUBLIC_SITE_URL       plain var - "https://vertlabs.run", used to
//                         build the GPX download link in the email.
//
// If GPX_BUCKET/TURNSTILE_SECRET_KEY/RESEND_API_KEY aren't set yet, the
// Function still degrades safely (Turnstile check passes open, storage/
// email errors are reported without ever leaking why) - but you do need
// all of them configured before relying on this in production.

const MAX_GPX_BYTES = 15 * 1024 * 1024; // keep in sync with assets/js/analysis-form.js
const MAX_FIELD_LENGTH = 500;

function jsonResponse(body, status) {
  return new Response(JSON.stringify(body), {
    status: status || 200,
    headers: { "content-type": "application/json" },
  });
}

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function sanitizeFilename(name) {
  return (name || "upload.gpx").replace(/[^a-zA-Z0-9_.-]/g, "_").slice(-120);
}

async function looksLikeGpx(file) {
  // Cheap content sniff so a renamed .txt doesn't sail through just
  // because of its extension.
  const head = await file
    .slice(0, 400)
    .text()
    .catch(function () {
      return "";
    });
  return /<\?xml|<gpx[\s>]/i.test(head);
}

async function verifyTurnstile(token, secret, ip) {
  if (!secret) return true; // not configured yet - don't hard-block submissions
  if (!token) return false;
  const body = new URLSearchParams();
  body.set("secret", secret);
  body.set("response", token);
  if (ip) body.set("remoteip", ip);
  const res = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
    method: "POST",
    body: body,
  });
  const data = await res.json().catch(function () {
    return { success: false };
  });
  return !!data.success;
}

async function sendNotificationEmail(env, fields, gpxKey) {
  const downloadUrl =
    env.PUBLIC_SITE_URL && env.ADMIN_TOKEN
      ? env.PUBLIC_SITE_URL + "/api/analysis-gpx/" + gpxKey + "?token=" + env.ADMIN_TOKEN
      : "(configure PUBLIC_SITE_URL / ADMIN_TOKEN for a direct link) R2 key: " + gpxKey;

  const lines = [
    "Name: " + fields.name,
    "Email: " + fields.email,
    "Race: " + fields.race,
    "Distance: " + fields.distance,
    "Race date: " + fields.race_date,
    "Message: " + (fields.message || "(none)"),
    "",
    "GPX file: " + downloadUrl,
  ];

  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: "Bearer " + env.RESEND_API_KEY,
    },
    body: JSON.stringify({
      from: "Vertical Trail Labs <hello@vertlabs.run>",
      to: [env.NOTIFY_EMAIL],
      reply_to: fields.email,
      subject: "VTL Analysis Request — " + fields.name + " — " + fields.race,
      text: lines.join("\n"),
    }),
  });

  return res.ok;
}

export async function onRequestPost(context) {
  const request = context.request;
  const env = context.env;

  let form;
  try {
    form = await request.formData();
  } catch (err) {
    return jsonResponse({ success: false, error: "invalid_input" }, 400);
  }

  // Honeypot: a real visitor never sees or fills this field (off-screen,
  // see .analysis-honeypot in style.css). A filled value means a bot -
  // reply success without doing anything, so the bot doesn't learn its
  // submission was rejected and keep adapting.
  if ((form.get("company") || "").toString().trim()) {
    return jsonResponse({ success: true });
  }

  const turnstileToken = form.get("cf-turnstile-response");
  const clientIp = request.headers.get("CF-Connecting-IP");
  const turnstileOk = await verifyTurnstile(turnstileToken, env.TURNSTILE_SECRET_KEY, clientIp);
  if (!turnstileOk) {
    return jsonResponse({ success: false, error: "spam_detected" }, 400);
  }

  const fields = {
    name: (form.get("name") || "").toString().trim().slice(0, MAX_FIELD_LENGTH),
    email: (form.get("email") || "").toString().trim().slice(0, MAX_FIELD_LENGTH),
    race: (form.get("race") || "").toString().trim().slice(0, MAX_FIELD_LENGTH),
    distance: (form.get("distance") || "").toString().trim().slice(0, MAX_FIELD_LENGTH),
    race_date: (form.get("race_date") || "").toString().trim().slice(0, MAX_FIELD_LENGTH),
    message: (form.get("message") || "").toString().trim().slice(0, 5000),
  };

  if (!fields.name || !fields.email || !fields.race || !fields.distance || !fields.race_date) {
    return jsonResponse({ success: false, error: "invalid_input" }, 400);
  }
  if (!isValidEmail(fields.email)) {
    return jsonResponse({ success: false, error: "invalid_input" }, 400);
  }

  const gpxFile = form.get("gpx");
  if (!gpxFile || typeof gpxFile === "string") {
    return jsonResponse({ success: false, error: "gpx_invalid" }, 400);
  }
  if (gpxFile.size > MAX_GPX_BYTES) {
    return jsonResponse({ success: false, error: "gpx_too_large" }, 400);
  }
  if (!/\.gpx$/i.test(gpxFile.name || "") || !(await looksLikeGpx(gpxFile))) {
    return jsonResponse({ success: false, error: "gpx_invalid" }, 400);
  }

  if (!env.GPX_BUCKET) {
    return jsonResponse({ success: false, error: "server_error" }, 500);
  }

  const requestId = crypto.randomUUID();
  const gpxKey = "analysis-requests/" + requestId + "/" + sanitizeFilename(gpxFile.name);

  try {
    await env.GPX_BUCKET.put(gpxKey, gpxFile.stream(), {
      httpMetadata: { contentType: "application/gpx+xml" },
      customMetadata: {
        name: fields.name,
        email: fields.email,
        race: fields.race,
        race_date: fields.race_date,
      },
    });
  } catch (err) {
    return jsonResponse({ success: false, error: "server_error" }, 500);
  }

  // The submission is already safely stored even if the notification
  // email fails (e.g. RESEND_API_KEY not configured yet) - don't lose it
  // over a downstream email hiccup.
  const emailed =
    env.RESEND_API_KEY && env.NOTIFY_EMAIL
      ? await sendNotificationEmail(env, fields, gpxKey).catch(function () {
          return false;
        })
      : false;

  return jsonResponse({ success: true, emailed: emailed });
}

export async function onRequestGet() {
  return jsonResponse({ success: false, error: "method_not_allowed" }, 405);
}
