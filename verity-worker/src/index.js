// Verity Checker — Cloudflare Worker
// Holds the Anthropic API key as a Cloudflare secret (ANTHROPIC_API_KEY).
// Verifies the caller has a valid Supabase session before proxying.
// Environment variables required:
//   ANTHROPIC_API_KEY  — Anthropic secret key (set via `wrangler secret put`)
//   SUPABASE_URL       — e.g. https://xyzxyz.supabase.co
//   ALLOWED_ORIGIN     — e.g. https://alisterwhite1.github.io

const CORS = (env) => ({
  'Access-Control-Allow-Origin': env.ALLOWED_ORIGIN || '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
});

async function verifySupabaseSession(token, env) {
  const res = await fetch(`${env.SUPABASE_URL}/auth/v1/user`, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'apikey': env.SUPABASE_ANON_KEY,
    },
  });
  if (!res.ok) return null;
  return res.json();
}

export default {
  async fetch(request, env) {
    const cors = CORS(env);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors });
    }

    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405, headers: cors });
    }

    // Verify Supabase session
    const authHeader = request.headers.get('Authorization') || '';
    const token = authHeader.replace(/^Bearer\s+/i, '').trim();
    if (!token) {
      return new Response(JSON.stringify({ error: 'Unauthorised — no session token' }), {
        status: 401, headers: { ...cors, 'Content-Type': 'application/json' },
      });
    }
    const user = await verifySupabaseSession(token, env);
    if (!user) {
      return new Response(JSON.stringify({ error: 'Unauthorised — invalid or expired session' }), {
        status: 401, headers: { ...cors, 'Content-Type': 'application/json' },
      });
    }

    // Parse request body (same shape as what the browser was sending directly to Anthropic)
    let body;
    try { body = await request.json(); }
    catch { return new Response(JSON.stringify({ error: 'Invalid JSON body' }), { status: 400, headers: cors }); }

    // Forward to Anthropic
    const anthropicRes = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify(body),
    });

    const data = await anthropicRes.json();
    return new Response(JSON.stringify(data), {
      status: anthropicRes.status,
      headers: { ...cors, 'Content-Type': 'application/json' },
    });
  },
};
