// SiteSnag photo upload/serve proxy.
// The app both PUTs and GETs photos here instead of talking to R2 directly.
// This Worker holds no credentials — it authenticates to R2 via the bucket
// binding, which Cloudflare manages internally. Serving reads through here
// (rather than R2's public pub-*.r2.dev URL) avoids that URL's "not for
// production, rate-limited" behaviour, which was silently dropping photo
// requests under normal use.

function corsHeaders(env) {
  return {
    'Access-Control-Allow-Origin': env.ALLOWED_ORIGIN || '*',
    'Access-Control-Allow-Methods': 'GET, PUT, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

export default {
  async fetch(request, env) {
    const headers = corsHeaders(env);

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers });
    }

    const url = new URL(request.url);
    const key = decodeURIComponent(url.pathname.replace(/^\//, ''));
    if (!key || key.includes('..')) {
      return new Response('Invalid path', { status: 400, headers });
    }

    if (request.method === 'PUT') {
      const contentType = request.headers.get('Content-Type') || 'image/jpeg';
      await env.PHOTOS.put(key, request.body, { httpMetadata: { contentType } });
      return new Response(JSON.stringify({ ok: true, key }), {
        status: 200,
        headers: { ...headers, 'Content-Type': 'application/json' },
      });
    }

    if (request.method === 'GET') {
      const obj = await env.PHOTOS.get(key);
      if (!obj) return new Response('Not found', { status: 404, headers });
      return new Response(obj.body, {
        status: 200,
        headers: {
          ...headers,
          'Content-Type': obj.httpMetadata?.contentType || 'image/jpeg',
          'Cache-Control': 'public, max-age=31536000, immutable',
        },
      });
    }

    return new Response('Method not allowed', { status: 405, headers });
  },
};
