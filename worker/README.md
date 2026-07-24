# Deploying the SiteSnag photo upload Worker

This Worker replaces the direct R2 upload SiteSnag currently does from the
browser. Right now, the app has a Cloudflare R2 access key and secret key
sitting in plain text inside `sitesnag.html` — anyone who views the page
source can read them and use them to write/delete objects in your photo
bucket. This Worker removes that: the browser calls the Worker over HTTPS,
and the Worker talks to R2 using a bucket **binding** (configured below),
which never exposes a secret key anywhere, including in its own source code.

This is the same deployment pattern already used for the RCA Navigator app's
AI-suggestions Worker, if you've set one of those up before.

## 1. Install Wrangler (Cloudflare's CLI), if you haven't already

```
npm install -g wrangler
```

## 2. Log in to Cloudflare

```
cd worker
wrangler login
```

Opens a browser tab to authorize the CLI against your Cloudflare account.

## 3. Deploy

```
wrangler deploy
```

Wrangler will print a URL like:

```
https://sitesnag-photo-upload.<your-subdomain>.workers.dev
```

That's your Worker's live URL — copy it.

## 4. Tell me the URL

Once deployed, send me the Worker URL and I'll update `sitesnag.html` to
upload through it instead of talking to R2 directly. At that point I'll
also delete the hardcoded R2 access key and secret key from the app's
source entirely — they won't be needed anymore.

## Cost

Cloudflare Workers' free tier covers this comfortably — 100,000 requests/day
included, and photo uploads are nowhere near that volume even at hundreds
of users. There is no cost beyond what you may already be paying for R2
storage itself.

## Rotating the old exposed key (recommended, do this regardless of timing)

Since the current R2 access key has been visible in the public page source,
it's worth rotating it in the Cloudflare dashboard (R2 → Manage API Tokens)
once the Worker is live and confirmed working — the old key can simply be
deleted/revoked at that point, since nothing will depend on it anymore.
