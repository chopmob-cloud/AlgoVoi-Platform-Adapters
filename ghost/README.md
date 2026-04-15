# Ghost — AlgoVoi Payment Adapter

Accept AlgoVoi stablecoin payments (USDC on Algorand / VOI / Hedera / Stellar) as a **crypto tip / membership-access alternative** for Ghost 5.x blogs. On verified on-chain payment, the adapter calls the Ghost Admin API to create or upgrade the reader's member record — including optional tier comping (paid newsletter access).

**v1.0.0 — Ghost 5.x / Python 3.9+ / zero runtime deps except PyJWT**

Full integration guide: [ghost/](.)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Use cases

- **"Pay with Crypto" alternative to Stripe** — Ghost's built-in paid membership works via Stripe. This adapter gives your readers another option: pay 0.01+ USDC on Algorand / VOI / Hedera / Stellar and get granted access automatically.
- **Tip jar on individual posts** — one-off payments that upgrade the reader's member label (no subscription).
- **Gift subscriptions** — pay for someone else to get access; the webhook includes the recipient email.
- **Agent / bot paid access** — AI agents can buy access to a gated newsletter via x402 / MPP / AP2 flows (via the `ai-adapters/` middleware, layered on top).

---

## How it works

```
Reader clicks "Pay with Crypto" on a gated post
        │
        ▼
Your Flask / Django / FastAPI app calls:
    GhostAlgoVoi.process_payment(reader_email, amount=4.99)
        │
        ▼
AlgoVoi gateway returns a checkout URL + token
        │
        ▼
Reader redirected to api1.ilovechicken.co.uk/checkout/{token}
        │
        ▼
Reader pays on-chain via wallet
        │
        ▼
AlgoVoi fires a webhook → POST /webhook/algovoi (your Flask route)
  • HMAC-SHA256 (base64) signature verified
  • Cross-check via verify_payment(token) — cancel-bypass guard
  • Extract reader_email + tx_id from payload
        │
        ▼
GhostAlgoVoi.upgrade_member(reader_email, tx_id, tier_id=...)
  • POST / PUT /ghost/api/admin/members/ via short-lived JWT
  • Adds "AlgoVoi-paid" label + notes TX ID
  • Optionally comps the reader onto a named tier
        │
        ▼
Reader has access. Ghost's own email notifications fire.
```

---

## Install

```bash
pip install PyJWT
```

That's the only dependency. Everything else (HMAC, JSON, HTTP) uses the Python standard library.

---

## Quick start

```python
from flask import Flask
from ghost_algovoi import GhostAlgoVoi

adapter = GhostAlgoVoi(
    ghost_url       = "https://yourblog.ghost.io",
    ghost_admin_key = "65abcdef...:0123456789abcdef...",   # from Ghost admin
    api_base        = "https://api1.ilovechicken.co.uk",
    api_key         = "algv_YOUR_API_KEY",
    tenant_id       = "YOUR_TENANT_UUID",
    webhook_secret  = "YOUR_ALGOVOI_WEBHOOK_SECRET",
    default_network = "algorand_mainnet",
    base_currency   = "USD",
)

app = Flask(__name__)

# 1. Endpoint the reader hits when they click "Pay with Crypto":
@app.route("/pay", methods=["POST"])
def pay():
    from flask import request, redirect
    email = request.form["email"]
    result = adapter.process_payment(email, amount=4.99)
    if not result:
        return "Could not create payment link", 500
    return redirect(result["checkout_url"])

# 2. AlgoVoi webhook endpoint — upgrades member on verified payment:
app.add_url_rule(
    "/webhook/algovoi",
    view_func=adapter.flask_webhook_handler(tier_id="65xxxxxxxxxxxxxxxxxxxxxx"),
    methods=["POST"],
)
```

---

## How to get your Ghost Admin API key

1. In Ghost admin, go to **Settings → Integrations → Custom Integrations**.
2. Click **+ Add custom integration**, name it "AlgoVoi Payments".
3. Copy the **Admin API Key** — it's two hex strings separated by `:` (e.g. `65abcdef01234567...:0123456789abcdef...`).
4. Paste into `ghost_admin_key` in the constructor.

---

## How to find your Ghost tier ID

```bash
curl -s https://yourblog.ghost.io/ghost/api/admin/tiers/ \
  -H "Authorization: Ghost $JWT" | jq '.tiers[] | {id, name}'
```

(Or look at the URL when editing the tier in Ghost admin — the 24-hex ID is in the path.)

---

## Files

| File | Description |
|------|-------------|
| `ghost_algovoi.py` | Single-file adapter — `GhostAlgoVoi` class, `verify_webhook`, `process_payment`, `verify_payment`, `upgrade_member`, `flask_webhook_handler` |

---

## Supported chains

| Network key | Asset | Asset ID |
|-------------|-------|----------|
| `algorand_mainnet` | USDC | ASA 31566704 |
| `voi_mainnet` | aUSDC | ARC200 302190 |
| `hedera_mainnet` | USDC | HTS 0.0.456858 |
| `stellar_mainnet` | USDC | Circle |

---

## Security posture

Matches the April 2026 + pass-2 audit patterns applied to the Amazon / TikTok / Squarespace B2B webhook adapters:

| Protection | Where |
|---|---|
| **Cancel-bypass guard** | Webhook handler calls `verify_payment()` before `upgrade_member()` |
| **HMAC empty-secret reject** | `verify_webhook()` returns `None` when secret is unset |
| **Timing-safe HMAC compare** | `hmac.compare_digest()` on base64 HMAC-SHA256 |
| **Body size cap** | 64 KB (`MAX_WEBHOOK_BODY_BYTES`) before HMAC computation |
| **Type guards on signature / body** | bytes/None/int signature rejected — no `TypeError` crash |
| **https-only outbound** | Every API + Ghost Admin call gated on `https://` scheme; refuses to send admin JWT or API key over plaintext |
| **tx_id length cap** | `MAX_TX_ID_LEN = 200` on both webhook TX and `upgrade_member()` arg |
| **Email validation** | Loose RFC 5321 regex + `MAX_EMAIL_LEN = 254` before reader lookup / creation |
| **Ghost admin-key format guard** | `GHOST_ADMIN_KEY_RE` rejects malformed keys at construction time |
| **Amount sanity** | `math.isfinite() && > 0` before gateway call |
| **redirect_url scheme guard** | Only `https://` URLs accepted |
| **JWT key length / format check** | Key split + `binascii.unhexlify()` — catches bad hex early |

---

## Webhook payload shape

The adapter expects AlgoVoi to POST a JSON body like:

```json
{
  "tx_id":        "JW4OOGMKDI4SVMLZIJQ6STJ5CA5TJLOVA4GKQCXZWWTXKOE35VHA",
  "reader_email": "paying.reader@example.com",
  "token":        "abc123def456...",
  "network":      "algorand_mainnet",
  "amount":       "4.99"
}
```

Alternate field names are also accepted: `transaction_id` (instead of `tx_id`), `email` (instead of `reader_email`).

---

## Testing

Phase 1 — no real credentials needed:

```python
from ghost_algovoi import GhostAlgoVoi
adapter = GhostAlgoVoi(
    ghost_url="https://ignore.invalid",
    ghost_admin_key="0123456789abcdef01234567:" + "0"*64,  # placeholder of correct format
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_test", tenant_id="test", webhook_secret="test-secret",
)
# Bad email
assert adapter.process_payment("not-an-email", amount=1.0) is None
# Bad amount
assert adapter.process_payment("a@b.co", amount=float("nan")) is None
assert adapter.process_payment("a@b.co", amount=-1.0) is None
# Bad signature type
assert adapter.verify_webhook(b'{"x":1}', None) is None
assert adapter.verify_webhook(b'{"x":1}', b"bytes") is None
# Oversized body
assert adapter.verify_webhook(b'x' * 100_000, "sig") is None
```

Phase 2 (pay-then-grant-access) requires a real Ghost blog + a real AlgoVoi tenant + a real on-chain payment. Use the `gh-blog.ilovechicken.co.uk` test blog once the Ghost side of the demo is wired up.

---

## Dependencies

```
PyJWT >= 2.0   # pip install PyJWT
```

No other runtime dependencies. Python standard library handles HTTP, HMAC, JSON, base64, and SSL.

---

Licensed under the [Business Source License 1.1](../LICENSE).
