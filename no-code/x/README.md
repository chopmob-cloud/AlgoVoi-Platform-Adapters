# AlgoVoi X (Twitter) Adapter

Auto-post tweets when crypto payments are confirmed, or share hosted checkout links on X — all without writing a payment processor.

Supports **Algorand · VOI · Hedera · Stellar** (USDC + native tokens).  
Works standalone or inside no-code flows: **Zapier · Make · n8n · direct webhook**.

---

## What it does

| Surface | Trigger | Output |
|---------|---------|--------|
| **Webhook handler** | AlgoVoi sends `payment.confirmed` | Tweet with amount, network, TX ID |
| **Post payment link** | Your code or flow calls `post_payment_link()` | Creates checkout URL → posts tweet |
| **Raw tweet** | Call `post_tweet()` directly | Any tweet (e.g. campaign, announcement) |

All three surfaces are in a single file: `x_algovoi.py`.

---

## Installation

No package manager needed — copy the file:

```bash
# from the repo root
cp no-code/x/x_algovoi.py /your/project/
pip install requests-oauthlib   # only dependency
```

Or use directly from the repo:

```bash
git clone https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
pip install requests-oauthlib
```

---

## Credentials

### AlgoVoi credentials

Obtain from **https://app.algovoi.com → Settings → API Keys**:

| Variable | Description |
|----------|-------------|
| `ALGOVOI_API_KEY` | `algv_...` key for your tenant |
| `ALGOVOI_TENANT_ID` | Your tenant UUID |
| `ALGOVOI_PAYOUT_ADDRESS` | Default wallet address for payouts |
| `ALGOVOI_WEBHOOK_SECRET` | HMAC-SHA256 secret (for webhook surface) |

### X (Twitter) credentials

1. Go to **https://developer.x.com/en/portal/dashboard**
2. Click **+ Add Project** → any name → select **"Making a bot"**
3. Inside the project, create an **App**
4. App → **Settings** → **User authentication settings** → Edit:
   - App permissions: **Read and Write**
   - Type of App: **Web App, Automated App or Bot**
   - Callback URI: `https://localhost` (placeholder)
   - Website URL: `https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters`
   - Save
5. App → **Keys and Tokens** → copy all four:

| Variable | Where to find it |
|----------|-----------------|
| `X_API_KEY` | API Key |
| `X_API_KEY_SECRET` | API Key Secret |
| `X_ACCESS_TOKEN` | Access Token |
| `X_ACCESS_TOKEN_SECRET` | Access Token Secret |

> **Important:** Generate the Access Token and Secret *after* enabling Read+Write.  
> If they were generated before, regenerate them now or you'll get `403 Forbidden`.

---

## Quick start

### 1 — Webhook handler (Flask)

AlgoVoi calls your endpoint when a payment is confirmed; the adapter validates the HMAC-SHA256 signature and posts a tweet automatically.

```python
from flask import Flask, request, jsonify
from x_algovoi import AlgoVoiX

handler = AlgoVoiX(
    algovoi_key="algv_...",
    tenant_id="your-tenant-uuid",
    payout_algorand="ADDR...",           # wallet for Algorand payouts
    payout_voi="ADDR...",                # wallet for VOI payouts
    payout_hedera="0.0.XXXXXX",          # wallet for Hedera payouts
    payout_stellar="GADDR...",           # wallet for Stellar payouts
    webhook_secret="your-webhook-secret",
    x_api_key="...",
    x_api_key_secret="...",
    x_access_token="...",
    x_access_token_secret="...",
)

app = Flask(__name__)

@app.route("/x/webhook", methods=["POST"])
def x_webhook():
    res = handler.on_payment_received(
        raw_body=request.get_data(as_text=True),
        signature=request.headers.get("X-AlgoVoi-Signature", ""),
    )
    return jsonify(res.to_dict()), res.http_status
```

Configure the webhook URL in **AlgoVoi Dashboard → Settings → Webhooks**:  
`https://your-domain.com/x/webhook`

### 2 — Post a payment link

Create an AlgoVoi hosted checkout and share it as a tweet in one call:

```python
result = handler.post_payment_link(
    amount="5.00",
    network="algorand_mainnet",      # see Networks section
    label="Premium access — 5 USDC",
)
print(result.checkout_url)   # https://pay.algovoi.com/c/...
print(result.tweet_url)      # https://x.com/i/web/status/...
```

### 3 — Post a raw tweet

```python
result = handler.post_tweet("AlgoVoi now supports Stellar USDC payments! #AlgoVoi #crypto")
print(result.tweet_url)
```

### 4 — List supported networks

```python
from x_algovoi import list_networks
for net in list_networks():
    print(net["id"], net["asset"], net["chain"])
```

---

## Tweet templates

### Payment confirmed

```
✅ 0.01 USDC payment confirmed on Algorand

Verified directly on the blockchain by AlgoVoi — open-source crypto
payment adapters for Zapier, Make, n8n, AI agents & more.
No banks, no card processors.

TX: ABCD1234…
#AlgoVoi #crypto
```

### Payment link

```
Premium access — 5 USDC

Pay 5.00 USDC on Algorand with crypto — verified on-chain by AlgoVoi.
No account needed, just a wallet.

https://pay.algovoi.com/c/...
#AlgoVoi
```

To customise, pass `tweet_template` to the constructor:

```python
handler = AlgoVoiX(
    ...
    tweet_template="💸 {amount_display} {asset} received on {network_label} — TX {tx_id_short}",
)
```

Available placeholders: `{amount_display}`, `{asset}`, `{network_label}`, `{tx_id_short}`, `{tx_id}`.

---

## Networks

| ID | Asset | Chain |
|----|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Algorand |
| `voi_mainnet` | aUSDC (ARC-200 302190) | VOI |
| `hedera_mainnet` | USDC (HTS 0.0.456858) | Hedera |
| `stellar_mainnet` | USDC (Circle) | Stellar |
| `algorand_mainnet_algo` | ALGO (native) | Algorand |
| `voi_mainnet_voi` | VOI (native) | VOI |
| `hedera_mainnet_hbar` | HBAR (native) | Hedera |
| `stellar_mainnet_xlm` | XLM (native) | Stellar |

Testnet variants exist for all 8 (append `_testnet` or replace `mainnet` with `testnet`).

---

## End-to-end test

`e2e_test.py` runs a full mainnet round-trip across all 4 chains — no mocks, no MCP:

1. Checks network health (block heights via public nodes)
2. Checks wallet balances (optional)
3. Creates 4 checkout links via AlgoVoi REST API
4. Displays QR / checkout URLs and waits for you to pay
5. Polls `GET /checkout/{token}/status` until `paid`
6. Calls the local webhook handler to validate HMAC + build tweet text
7. Posts 4 tweets via X API
8. Prints TX IDs and tweet URLs

```bash
# Run from repo root — reads keys.txt automatically
python no-code/x/e2e_test.py

# Resume mode — skip Steps 1-4 if you already have checkout tokens
python no-code/x/e2e_test.py \
    --token-algo  TOKEN_ALGO  \
    --token-voi   TOKEN_VOI   \
    --token-hedera TOKEN_HEDERA \
    --token-stellar TOKEN_STELLAR
```

Credentials are read in this order: CLI arg → environment variable → `keys.txt`.

`keys.txt` format (at repo root, gitignored):

```
ALGOVOI_API_KEY=algv_...
ALGOVOI_TENANT_ID=...
ALGOVOI_WEBHOOK_SECRET=...
X_API_KEY=...
X_API_SECRET=...
X_ACCESS_TOKEN=...
X_ACCESS_SECRET=...
```

---

## Rate limits

X API Free tier: **500 tweets / month** (app-level).  
Avoid calling `post_payment_link` or `post_tweet` in hot loops — use the webhook surface for production payment notifications.

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `401 Unauthorized` | Wrong keys or wrong key type | Regenerate Access Token *after* enabling Read+Write |
| `403 Forbidden` | App has Read-only permissions | App → Settings → set Read+Write → regenerate tokens |
| `429 Too Many Requests` | Rate limit hit | Wait 15 min (or until next month if monthly cap hit) |
| `duplicate content` | Same tweet text posted twice | Change the tweet text slightly |
| `ALGOVOI_API_KEY not set` | Missing env var or keys.txt entry | Set the var or add it to keys.txt |
| `invalid signature` | Wrong webhook secret | Check `ALGOVOI_WEBHOOK_SECRET` matches AlgoVoi dashboard |

---

## No-code flows

### Zapier — Code by Zapier step

```python
import urllib.request, json, hmac, hashlib

# Trigger: Webhook by Zapier (catch AlgoVoi webhook)
body   = input_data["body"]
secret = input_data["webhook_secret"]

sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
# Compare sig to X-AlgoVoi-Signature header, then call x_algovoi as a subprocess
```

### Make (Integromat) — HTTP module

Point the HTTP module at your deployed webhook endpoint (`/x/webhook`).  
AlgoVoi signs the body; the adapter validates and tweets automatically.

### n8n — HTTP Request node

Same pattern: POST to your `/x/webhook` endpoint from an n8n Webhook trigger node.

---

## File reference

| File | Purpose |
|------|---------|
| `x_algovoi.py` | Main adapter — `AlgoVoiX` class, `list_networks()` |
| `post_test_tweet.py` | One-shot tweet for credential verification |
| `e2e_test.py` | Full 4-chain mainnet end-to-end test |

---

## Links

- **Repo:** https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
- **AlgoVoi:** https://algovoi.com
- **X Developer portal:** https://developer.x.com
- **License:** Business Source License 1.1 — see `LICENSE`
