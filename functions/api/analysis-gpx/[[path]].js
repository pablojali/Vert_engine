// Cloudflare Pages Function: GET /api/analysis-gpx/*
//
// The only way to read a submitted GPX back out of R2 - the bucket
// itself is never made public. Gated behind ADMIN_TOKEN (see
// functions/api/analysis-request.js for the full env var list); the
// email sent for each request already includes this token in the link,
// so opening it from your inbox just works. Anyone without the token
// gets a plain 404, same as a URL that doesn't exist.

export async function onRequestGet(context) {
  const request = context.request;
  const env = context.env;
  const params = context.params;

  const url = new URL(request.url);
  const token = url.searchParams.get("token");
  if (!env.ADMIN_TOKEN || token !== env.ADMIN_TOKEN) {
    return new Response("Not found", { status: 404 });
  }

  const pathSegments = Array.isArray(params.path) ? params.path : [params.path];
  const key = pathSegments.filter(Boolean).join("/");
  if (!key || !env.GPX_BUCKET) {
    return new Response("Not found", { status: 404 });
  }

  const object = await env.GPX_BUCKET.get(key);
  if (!object) {
    return new Response("Not found", { status: 404 });
  }

  return new Response(object.body, {
    headers: {
      "content-type": (object.httpMetadata && object.httpMetadata.contentType) || "application/gpx+xml",
      "content-disposition": 'attachment; filename="' + key.split("/").pop() + '"',
      "cache-control": "private, no-store",
      "x-robots-tag": "noindex",
    },
  });
}
