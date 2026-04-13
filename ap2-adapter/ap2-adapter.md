# AP2 — Agent Payment Protocol v2 Adapter for AlgoVoi

Drop-in server middleware for accepting **AP2 payment mandates** from AI agents. AP2 uses ed25519-signed credentials — no on-chain transaction is required at the point of purchase. Settlement happens asynchronously.

> AP2 (Agent Payment Protocol v2) is Google's open standard for agent-to-merchant payments using signed mandates. AlgoVoi acts as the verifier and settlement layer.

---

## How it works

```
AI Agent prepares ed25519-signed AP2 mandate
  { merchant_id, payer_address, amount, network, signature }
            ↓
Agent sends X-AP2-Mandate header with base64-encoded mandate
            ↓
Ap2Gate.check() verifies mandate via AlgoVoi API (/v1/ap2/verify)
            ↓
If valid: access granted, mandate details in result.mandate
If invalid: HTTP 402 + X-AP2-Payment-Request header
```

Zero pip dependencies — uses only the Python standard library. Works with Flask, Django, FastAPI, or any WSGI/ASGI framework.

---

## Installation

Copy `ap2.py` into your project. No package install required.

---

## Quick start

```python
from ap2 import Ap2Gate

gate = Ap2Gate(
    merchant_id="shop42",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_...",
    tenant_id="<your-tenant-uuid>",
    amount_usd=1.99,
    currency="USD",
    networks=["algorand_mainnet", "voi_mainnet"],
    items=[
        {"label": "API access — 1h", "amount": "1.99"},
    ],
)
```

### Flask

```python
@app.route("/api/premium", methods=["POST"])
def premium():
    result = gate.check(dict(request.headers), request.get_json(silent=True))
    if result.requires_payment:
        return result.as_flask_response()
    # result.mandate has: payer_address, amount, currency, network
    return jsonify(data="premium content")
```

### Flask guard shortcut

```python
@app.route("/api/premium", methods=["POST"])
def premium():
    guard = gate.flask_guard(request.get_json(silent=True))
    if guard:
        return guard
    return jsonify(data="premium content")
```

### Django

```python
@gate.django_decorator
def premium_view(request):
    return JsonResponse({"data": "premium"})
```

---

## Payment request format

When no valid mandate is present, the adapter responds:

```
HTTP/1.1 402 Payment Required
X-AP2-Payment-Request: <base64 JSON>
Content-Type: application/json
```

Decoded `X-AP2-Payment-Request`:

```json
{
  "protocol": "ap2",
  "version": "1",
  "merchant_id": "shop42",
  "request_id": "ap2_1234567890_4321",
  "amount": {
    "value": "1.99",
    "currency": "USD"
  },
  "items": [
    {"label": "API access — 1h", "amount": "1.99"}
  ],
  "networks": ["algorand-mainnet", "voi-mainnet"],
  "signing": "ed25519",
  "expires_at": 1744390000
}
```

---

## Mandate format

The agent signs and submits:

```
X-AP2-Mandate: <base64-encoded JSON>
```

Or in the request body as `ap2_mandate`. JSON mandates (not base64) are also accepted.

Mandate structure:

```json
{
  "merchant_id": "shop42",
  "payer_address": "<agent-wallet-address>",
  "signature": "<base64-ed25519-signature>",
  "network": "algorand-mainnet",
  "amount": {
    "value": "1.99",
    "currency": "USD"
  }
}
```

---

## Network and asset mapping

| Config key | Wire format | Asset |
|-----------|-------------|-------|
| `algorand_mainnet` | `algorand-mainnet` | USDC (ASA 31566704) |
| `voi_mainnet` | `voi-mainnet` | aUSDC (ARC200 302190) |
| `hedera_mainnet` | `hedera-mainnet` | USDC (0.0.456858) |
| `stellar_mainnet` | `stellar-mainnet` | USDC (Circle) |

Note: Config keys use underscores; wire format uses hyphens (AP2 spec).

---

## Live test status

Confirmed end-to-end on **2026-04-12** against `api1.ilovechicken.co.uk`:

| Test | Result |
|------|--------|
| No credentials → HTTP 402 + `X-AP2-Payment-Request` header | Pass |
| Payment request: `protocol=ap2`, `signing=ed25519` | Pass |
| Payment request: correct `merchant_id`, `amount`, `currency` | Pass |
| Payment request: networks in hyphenated wire format | Pass |
| Invalid base64 mandate → 402 with encoding error | Pass |
| Merchant ID mismatch → 402 with error | Pass |
| Missing `payer_address` → 402 with error | Pass |
| Missing `signature` → 402 with error | Pass |
| Fake mandate → verification fails | Pass |
| Mandate in request body (`ap2_mandate`) parsed | Pass |
| JSON mandate (non-base64) accepted | Pass |
| Flask response: status 402, `X-AP2-Payment-Request` header | Pass |
| Unit tests (29/29) | Pass |

## Verification architecture

Per the [AP2 spec](https://github.com/tempoxyz/mpp-specs), there is no central verification API — verification is local using the agent's ed25519 public key. `Ap2Gate._verify_mandate()`:

1. Derives the 32-byte ed25519 public key from the agent's Algorand address (Algorand uses ed25519 natively — the address *is* the public key)
2. Reconstructs the canonical signing message: `json.dumps(mandate_fields_minus_signature, sort_keys=True, separators=(",",":"))`
3. Verifies the signature using PyNaCl (available via algosdk) with cryptography package as fallback

**Smoke tested 13 April 2026** — fresh ed25519 key pair generated, mandate signed and accepted end-to-end. Tampered mandate and merchant mismatch both correctly rejected. 15/15 passed.
