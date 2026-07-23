# Deploying the SiteAssure AI-Suggestions Worker

This Worker adds optional AI-generated suggestions to the RCA Navigator's
evidence prompts. It is fully optional — the app works without it, using
its built-in static suggestions only. Deploy this from your own terminal,
not from the sandbox that built it, so your Anthropic API key never
leaves your machine except to Cloudflare's secret store.

## 1. Install Wrangler (Cloudflare's CLI)

```
npm install -g wrangler
```

## 2. Log in to Cloudflare

```
cd worker
wrangler login
```

This opens a browser tab to authorize the CLI against your Cloudflare account.

## 3. Set your Anthropic API key as a secret

Get a key from https://console.anthropic.com/settings/keys if you don't
already have one, then run:

```
wrangler secret put ANTHROPIC_API_KEY
```

Paste the key when prompted. It's stored encrypted by Cloudflare and is
never visible in the Worker source or dashboard afterward.

## 4. Deploy

```
wrangler deploy
```

Wrangler will print a URL like:

```
https://siteassure-rca-ai.<your-subdomain>.workers.dev
```

That's your Worker's live URL.

## 5. Point the app at it

In RCA Navigator: open the NCR Register, click the settings/gear icon
(NCR Numbering Format modal), scroll to **AI-Assisted Suggestions**, and
paste the URL from step 4 into the **Worker URL** field. Save.

From then on, whenever you're entering evidence at an RCA node, the app
will show its usual built-in suggestions immediately, and — if the
Worker responds within ~12 seconds — a second group of AI-suggested
options grounded in your fault title and the current node will appear
underneath them. If the Worker is unreachable, slow, or errors, nothing
breaks; the built-in suggestions are all you'll see.

## Cost

Each suggestion request makes one call to `claude-opus-4-8`. Cloudflare
Workers' free tier covers light usage; Anthropic API usage is billed
per your Anthropic account. There's no fixed cost — you only pay for
calls actually made.

## Updating later

If you edit `worker/src/index.js`, redeploy with:

```
wrangler deploy
```

No need to re-set the secret unless you're rotating the API key.
