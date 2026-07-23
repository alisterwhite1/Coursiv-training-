const ANTHROPIC_VERSION = '2023-06-01';
const MODEL = 'claude-opus-4-8';
const MAX_SUGGESTIONS = 5;

const SYSTEM_PROMPT = `You are the Quality Director for a construction site, supporting a field engineer who is working through a structured Root Cause Analysis (RCA) using the SiteAssure RCA Navigator app.

You write like an experienced construction quality professional, not a chatbot: plain, direct, site-specific language. Reference concrete construction realities (concrete pours, rebar, formwork, method statements, ITPs, subcontractor coordination, weather, curing, inspection holds) where they genuinely fit the node under discussion — never generic corporate-safety filler.

You will be given the fault/incident title the engineer is investigating, the current node in the RCA tree (its name, definition, and typical issues), and the standard prompt questions already shown for that node. Your job is to propose additional, case-specific candidate answers the engineer could select or adapt for the free-text box at this node — written as if you already know the specifics of this exact incident, not generic textbook answers.

Rules:
- Return between 2 and ${MAX_SUGGESTIONS} suggestions.
- Each suggestion must be a single, complete sentence or short clause suitable for pasting directly into the investigation's evidence field.
- Ground every suggestion in the fault title and node context you were given. Do not repeat the standard questions verbatim.
- Do not invent specific names, dates, or company names that were not given to you.
- No preamble, no numbering, no markdown — the suggestions are returned as a JSON array of plain strings only.`;

function corsHeaders(origin) {
  return {
    'Access-Control-Allow-Origin': origin || '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
  };
}

function jsonResponse(body, status, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) },
  });
}

function buildUserPrompt(input) {
  const lines = [];
  lines.push(`Fault/incident title: ${input.faultTitle || '(not entered)'}`);
  lines.push(`Current node: ${input.nodeName || '(unnamed)'}`);
  if (input.nodeDefinition) lines.push(`Node definition: ${input.nodeDefinition}`);
  if (input.typicalIssues) lines.push(`Typical issues at this node: ${input.typicalIssues}`);
  if (Array.isArray(input.questions) && input.questions.length) {
    lines.push(`Standard prompt questions already shown:\n- ${input.questions.join('\n- ')}`);
  }
  lines.push(input.isRootLevel
    ? 'This is a root-cause-level node: suggestions should read as candidate root-cause statements for this specific incident.'
    : 'This is an investigation-path node: suggestions should read as candidate evidence/answers a site engineer would log while working through this node for this specific incident.');
  lines.push(`\nReturn a JSON array of ${MAX_SUGGESTIONS} or fewer plain-string suggestions, nothing else.`);
  return lines.join('\n');
}

function extractJsonArray(text) {
  const start = text.indexOf('[');
  const end = text.lastIndexOf(']');
  if (start === -1 || end === -1 || end < start) return null;
  try {
    const parsed = JSON.parse(text.slice(start, end + 1));
    if (!Array.isArray(parsed)) return null;
    return parsed.filter(s => typeof s === 'string' && s.trim()).map(s => s.trim()).slice(0, MAX_SUGGESTIONS);
  } catch (e) {
    return null;
  }
}

async function handleSuggest(request, env, origin) {
  if (!env.ANTHROPIC_API_KEY) {
    return jsonResponse({ error: 'Worker is not configured with an API key.' }, 500, origin);
  }

  let input;
  try {
    input = await request.json();
  } catch (e) {
    return jsonResponse({ error: 'Invalid JSON body.' }, 400, origin);
  }

  if (!input || typeof input !== 'object' || !input.nodeName) {
    return jsonResponse({ error: 'nodeName is required.' }, 400, origin);
  }

  const anthropicRes = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': env.ANTHROPIC_API_KEY,
      'anthropic-version': ANTHROPIC_VERSION,
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 1024,
      system: SYSTEM_PROMPT,
      messages: [{ role: 'user', content: buildUserPrompt(input) }],
    }),
  });

  if (!anthropicRes.ok) {
    const errText = await anthropicRes.text().catch(() => '');
    return jsonResponse({ error: 'Upstream AI request failed.', detail: errText.slice(0, 500) }, 502, origin);
  }

  const data = await anthropicRes.json();
  const textBlock = (data.content || []).find(b => b.type === 'text');
  const suggestions = textBlock ? extractJsonArray(textBlock.text) : null;

  if (!suggestions || !suggestions.length) {
    return jsonResponse({ error: 'No usable suggestions returned.' }, 502, origin);
  }

  return jsonResponse({ suggestions }, 200, origin);
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin');

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(origin) });
    }

    const url = new URL(request.url);
    if (url.pathname === '/suggest' && request.method === 'POST') {
      return handleSuggest(request, env, origin);
    }

    return jsonResponse({ error: 'Not found.' }, 404, origin);
  },
};
