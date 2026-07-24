// SiteSnag photo upload proxy.
// The app PUTs a photo here instead of talking to R2 directly, so the R2
// access key/secret never has to live in client-side JS. This Worker holds
// no credentials at all — it authenticates to R2 via the bucket binding
// configured in wrangler.toml, which Cloudflare manages internally.

function corsHeaders(env) {
  return {
    'Access-Control-Allow-Origin': env.ALLOWED_ORIGIN || '*',
    'Access-Control-Allow-Methods': 'PUT, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

export default {
  async fetch(request, env) {
    const headers = corsHeaders(env);

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers });
    }

    if (request.method !== 'PUT') {
      return new Response('Method not allowed', { status: 405, headers });
    }

    const url = new URL(request.url);
    // Path after the leading slash becomes the R2 object key, e.g. /proj123/169..._open.jpg
    const key = decodeURIComponent(url.pathname.replace(/^\//, ''));
    if (!key || key.includes('..')) {
      return new Response('Invalid path', { status: 400, headers });
    }

    const contentType = request.headers.get('Content-Type') || 'image/jpeg';
    await env.PHOTOS.put(key, request.body, {
      httpMetadata: { contentType },
    });

    return new Response(JSON.stringify({ ok: true, key }), {
      status: 200,
      headers: { ...headers, 'Content-Type': 'application/json' },
    });
  },
};
