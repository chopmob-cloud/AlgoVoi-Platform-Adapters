# AP2 — Agent Payment Protocol v2 Adapter for AlgoVoi

Drop-in server middleware implementing the AP2 v0.1 CartMandate / PaymentMandate flow with the **AlgoVoi crypto-algo extension** for Algorand and VOI on-chain payments.

Extension URI:  `https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1`
Schema:         `https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1/schema.json`
Extensions API: `https://api1.ilovechicken.co.uk/ap2/extensions`

> AP2 (Agent Payment Protocol v2) is an open standard for agent-to-merchant payments based on W3C Payment Request API structures and ed25519-signed mandates. This adapter implements the AP2 v0.1 CartMandate/PaymentMandate flow via an AlgoVoi-published extension that adds Algorand and VOI as supported payment methods. The extension is not part of the official AP2 v0.1 specification (which is cards-only) but is fully interoperable with AP2-compliant agents that support extension URIs.

---

## How it works

```
Agent requests resource
            |
            v
Ap2Gate.check() -- no X-AP2-Mandate header found
            |
            v
HTTP 402 + X-AP2-Cart-Mandate header
  CartMandate (AP2 v0.1):
    contents.payment_request.payment_methods:
      [ { supported_methods: "<extension-uri>",
          data: { network, receiver, amount_microunits, asset_id,
                  min_confirmations, memo_required } } ]
            |
            v
Agent pays on-chain (Algorand or VOI USDC)
Agent signs PaymentMandate (ed25519) with network + tx_id
            |
            v
Ap2Gate: verify ed25519 sig locally (no central API)
         verify tx on-chain via Algonode / Nodely indexer
            |
            v
HTTP 200 -- result.mandate.{payer_address, network, tx_id}
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
    amount_microunits=10000,           # 0.01 USDC
    networks=["algorand-mainnet", "voi-mainnet"],
    payout_address="<your-algorand-address>",
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

## CartMandate format

When no valid mandate is present, the adapter responds:

```
HTTP/1.1 402 Payment Required
X-AP2-Cart-Mandate: <base64 JSON>
Content-Type: application/json
```

Decoded `X-AP2-Cart-Mandate` (AP2 v0.1 CartMandate with crypto-algo extension):

```json
{
  "ap2_version": "0.1",
  "type": "CartMandate",
  "merchant_id": "shop42",
  "request_id": "ap2_1234567890_4321",
  "contents": {
    "payment_request": {
      "payment_methods": [
        {
          "supported_methods": "https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1",
          "data": {
            "network": "algorand-mainnet",
            "receiver": "<payout-address>",
            "amount_microunits": 10000,
            "asset_id": 31566704,
            "min_confirmations": 1,
            "memo_required": true
          }
        },
        {
          "supported_methods": "https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1",
          "data": {
            "network": "voi-mainnet",
            "receiver": "<payout-address>",
            "amount_microunits": 10000,
            "asset_id": 302190,
            "min_confirmations": 1,
            "memo_required": true
          }
        }
      ]
    }
  },
  "expires_at": 1744390000
}
```

The `data` field conforms to the `PaymentMethodData` schema at `https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1/schema.json`.

---

## PaymentMandate format

The agent signs and submits:

```
X-AP2-Mandate: <base64-encoded JSON>
```

Or in the request body as `ap2_mandate`. Raw JSON string (non-base64) is also accepted.

PaymentMandate structure:

```json
{
  "ap2_version": "0.1",
  "type": "PaymentMandate",
  "merchant_id": "shop42",
  "payer_address": "<algorand-ed25519-address>",
  "payment_response": {
    "method_name": "https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1",
    "details": {
      "network":     "algorand-mainnet",
      "tx_id":       "<on-chain-tx-id>",
      "note_field":  "<sha256hex-of-cart-mandate-optional>"
    }
  },
  "signature": "<base64-ed25519-signature>"
}
```

The `details` field conforms to `PaymentResponseDetails` in the extension schema. The `signature` is an ed25519 signature over the canonical JSON of all fields except `signature` (keys sorted, no spaces).

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

## Live test status — v2.0.0 (2026-04-13)

| Test | Result |
|------|--------|
| No credentials → HTTP 402 + `X-AP2-Cart-Mandate` header | Pass |
| CartMandate: `ap2_version=0.1`, `type=CartMandate` | Pass |
| CartMandate: `payment_methods` with extension URI | Pass |
| PaymentMethodData: `network`, `receiver`, `amount_microunits`, `asset_id`, `min_confirmations`, `memo_required` | Pass |
| Invalid base64 mandate → 402 with encoding error | Pass |
| Merchant ID mismatch → 402 with error | Pass |
| Missing `payer_address` → 402 with error | Pass |
| Missing `signature` → 402 with error | Pass |
| Fake signature → verification fails | Pass |
| `tx_id` length guard (>200 chars rejected) | Pass |
| Mandate in request body (`ap2_mandate`) parsed | Pass |
| JSON mandate (non-base64) accepted | Pass |
| Flask response: status 402, `X-AP2-Cart-Mandate` header | Pass |
| WSGI response: status, headers, body | Pass |
| **Real PyNaCl ed25519 key pair — valid PaymentMandate accepted** | **Pass** |
| **Tampered mandate (network changed) — sig rejected** | **Pass** |
| **Wrong signature (different key) — rejected** | **Pass** |
| **cryptography package fallback verification** | **Pass** |
| Replay protection (`tx_id` reuse rejected) | Pass |
| 2-network CartMandate (algorand-mainnet + voi-mainnet) | Pass |
| Extension URI in source | Pass |
| Unit tests (81/81) | Pass |

## Smoke test — 13 April 2026

### ed25519 verification
| Scenario | Key source | Result |
|----------|-----------|--------|
| Valid PaymentMandate, fake tx_id | PyNaCl `SigningKey.generate()` | ✅ Sig accepted, on-chain verification attempted |
| Tampered mandate (network changed) | PyNaCl (original sig, different fields) | ✅ Sig rejected |
| Wrong signature | PyNaCl (different key, correct address) | ✅ Sig rejected |
| Valid PaymentMandate | `cryptography` `Ed25519PrivateKey` | ✅ Fallback path confirmed |

### 4-chain live payments — 0.01 USDC (13 April 2026)

Real ed25519 key pair generated per chain. PaymentMandate signed and verified end-to-end (sig + on-chain):

| Chain | TX ID | Result |
|-------|-------|--------|
| Algorand mainnet (USDC ASA 31566704) | `SDIX4LHMRGX5E2JJ5XTZ7WEKIZB6AVSLIRWUPTQ3FYKRSSVDMHWQ` | ✅ Pass |
| VOI mainnet (aUSDC ARC200 302190) | `WQIO2BHWFDWBSDHBBZDOLOYIFQ2ITH4OQKFGHMDEIHUU3TDOTY6A` | ✅ Pass |
| Hedera mainnet (USDC HTS 0.0.456858) | `0.0.10376692@1776113910.019442287` | ✅ Pass |
| Stellar pubnet (USDC Circle) | `a6288f502789073abafec698e3d543396367d9efa1618de62bafbb93c6791a58` | ✅ Pass |

## Verification architecture

Per the AP2 spec, there is no central verification API — verification is local using the agent's ed25519 public key. `Ap2Gate._verify_mandate()`:

1. Derives the 32-byte ed25519 public key from the agent's Algorand address (Algorand uses ed25519 natively — the address *is* the public key, base32-encoded)
2. Reconstructs the canonical signing message: `json.dumps(mandate_fields_minus_signature, sort_keys=True, separators=(",",":"))`
3. Verifies the signature using PyNaCl (preferred) with cryptography package as fallback

Both verification paths confirmed working as of 2026-04-13.
