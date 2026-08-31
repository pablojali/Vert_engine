// Cloudflare Pages Function: POST /api/analysis-request
//
// Receives the "Get Your VTL Analysis" form (multipart/form-data),
// validates it, verifies Turnstile, and emails it to VTL via Resend
// with the GPX attached directly - GPX files are small (a few MB at
// most), so there's no need for separate file storage (R2, which has a
// cost) at this volume. The GPX is never persisted anywhere server-side
// - it only ever exists in memory for the length of this request and in
// the resulting email. Runs entirely on Cloudflare's edge using only
// Web-standard APIs (fetch, FormData, btoa) - no Node.js APIs, and no
// access whatsoever to the private Terrain Intelligence Engine (a
// completely separate, private codebase/repo).
//
// Required env vars - set in Cloudflare Pages -> Settings ->
// Environment variables (secrets):
//
//   TURNSTILE_SECRET_KEY  secret - from the Turnstile widget you create
//                         in the Cloudflare dashboard (Turnstile -> Add
//                         site). The matching public "site key" goes in
//                         builder/env.py (not a secret, safe in git).
//   RESEND_API_KEY        secret - from https://resend.com (free tier
//                         is enough for this volume). Verify the
//                         notify.vertlabs.run sending SUBdomain there
//                         first (kept separate from the vertlabs.run
//                         root domain so it can't collide with Migadu's
//                         MX records for real mailboxes there) - the
//                         "from" address below must match whatever
//                         domain you actually verified in Resend, or
//                         every send fails with a 403.
//   NOTIFY_EMAIL          plain var - where the notification (with the
//                         GPX attached) lands. Your choice of inbox -
//                         doesn't have to be hello@vertlabs.run.
//
// If TURNSTILE_SECRET_KEY/RESEND_API_KEY aren't set yet, the Function
// still degrades safely (Turnstile check passes open, a missing Resend
// key is reported as a clean server_error instead of a silent failure)
// - but you need both configured before relying on this in production.

// Base64-encoded (after inflation) attachments need to stay well under
// typical inbox limits (Gmail caps incoming mail around 25 MB) - real
// GPX files are almost always a few MB at most, so this is generous
// headroom, not a tight squeeze.
const MAX_GPX_BYTES = 8 * 1024 * 1024; // keep in sync with assets/js/analysis-form.js
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

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000; // process in chunks - avoids blowing the
  // call-stack/argument limit that String.fromCharCode.apply(null, hugeArray)
  // would hit on a multi-MB file.
  let binary = "";
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
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

async function sendNotificationEmail(env, fields, gpxFile) {
  const gpxBase64 = arrayBufferToBase64(await gpxFile.arrayBuffer());

  const lines = [
    "Name: " + fields.name,
    "Email: " + fields.email,
    "Race: " + fields.race,
    "Distance: " + fields.distance,
    "Race date: " + fields.race_date,
    "Message: " + (fields.message || "(none)"),
    "",
    "GPX file attached: " + sanitizeFilename(gpxFile.name),
  ];

  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: "Bearer " + env.RESEND_API_KEY,
    },
    body: JSON.stringify({
      from: "Vertical Trail Labs <hello@notify.vertlabs.run>",
      to: [env.NOTIFY_EMAIL],
      reply_to: fields.email,
      subject: "VTL Analysis Request — " + fields.name + " — " + fields.race,
      text: lines.join("\n"),
      attachments: [
        {
          filename: sanitizeFilename(gpxFile.name),
          content: gpxBase64,
        },
      ],
    }),
  });

  if (!res.ok) {
    const errorBody = await res.text().catch(function () {
      return "(could not read response body)";
    });
    console.error("Resend API error", res.status, errorBody);
    return { ok: false, detail: "Resend " + res.status + ": " + errorBody };
  }

  return { ok: true, detail: null };
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

  if (!env.RESEND_API_KEY || !env.NOTIFY_EMAIL) {
    console.error(
      "Missing env var(s):",
      (!env.RESEND_API_KEY ? "RESEND_API_KEY " : "") + (!env.NOTIFY_EMAIL ? "NOTIFY_EMAIL" : "")
    );
    return jsonResponse({ success: false, error: "server_error" }, 500);
  }

  const emailResult = await sendNotificationEmail(env, fields, gpxFile).catch(function (err) {
    console.error("sendNotificationEmail threw:", err && err.message);
    return { ok: false, detail: "threw: " + (err && err.message) };
  });
  if (!emailResult.ok) {
    return jsonResponse({ success: false, error: "server_error" }, 500);
  }

  return jsonResponse({ success: true });
}

export async function onRequestGet() {
  return jsonResponse({ success: false, error: "method_not_allowed" }, 405);
}
