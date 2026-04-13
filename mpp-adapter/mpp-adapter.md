# MPP — Machine Payments Protocol Adapter for AlgoVoi

Drop-in server middleware that gates APIs behind MPP payment challenges. Implements the HTTP Payment Authentication scheme per the IETF draft (`draft-ryan-httpauth-payment`) with the `"charge"` intent. Responds with `WWW-Authenticate: Payment` when a request lacks valid payment credentials, and verifies on-chain transactions directly via the chain indexer — no central verification API.

100% IETF `draft-ryan-httpauth-payment` compliant as of v2.1.0 (2026-04-13), verified live across all 4 chains (Algorand, VOI, Hedera, Stellar).

> MPP (Machine Payments Protocol) is an open standard for autonomous machine-to-machine payments using HTTP 401/Payment authentication. Spec: https://paymentauth.org

---

## How it works

```
AI Agent (or any HTTP client) makes request to protected endpoint
            ↓
MppGate.check() — no Authorization: Payment header found
            ↓
HTTP 401 Payment Required
  WWW-Authenticate: Payment realm="..." id="<hmac-id>" method="algorand"
                    intent="charge" request="<b64>" expires="<RFC3339>"
  X-Payment-Required: <base64 JSON with accepts array>
            ↓
Agent submits on-chain payment (USDC on Algorand, VOI, Hedera, or Stellar)
            ↓
Agent retries with Authorization: Payment <base64 proof>
  — includes challenge echo: {"challenge": {id, realm, method, intent}, "payload": {"txId": "..."}}
            ↓
MppGate validates challenge echo (id must match an issued, non-expired challenge)
            ↓
MppGate verifies tx directly on-chain via chain indexer (no central API)
            ↓
HTTP 200 — access granted, Payment-Receipt header available
```

Zero pip dependencies — uses only the Python standard library. Works with Flask, Django, FastAPI, or any WSGI/ASGI framework.

---

## Installation

Copy `mpp.py` into your project. No package install required.

---

## Quick start

```python
from mpp import MppGate

gate = MppGate(
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_...",
    tenant_id="<your-tenant-uuid>",
    resource_id="my-inference-api",
    amount_microunits=10000,          # 0.01 USDC
    networks=["algorand_mainnet", "voi_mainnet"],
    realm="My Inference API",
    payout_address="<your-algorand-address>",
)
```

### Flask

```python
@app.before_request
def check_payment():
    return gate.flask_guard()
```

### Django

```python
# settings.py
MIDDLEWARE = ["yourapp.middleware.mpp_middleware", ...]

# yourapp/middleware.py
from mpp import MppGate
gate = MppGate(...)
mpp_middleware = gate.django_middleware
```

### WSGI (manual)

```python
result = gate.check(request_headers)
if result.requires_payment:
    status, headers, body = result.as_wsgi_response()
    return start_response(status, headers), [body]
```

---

## Challenge response headers

When payment is required, the adapter returns:

```
HTTP/1.1 402 Payment Required
WWW-Authenticate: Payment realm="My Inference API" id="<hmac-id>"
                  method="algorand" intent="charge"
                  request="<base64>" expires="2026-04-13T10:35:00Z"
X-Payment-Required: <base64 JSON>
```

Decoded `WWW-Authenticate` `request=` field (charge intent):

```json
{
  "amount": "10000",
  "currency": "usdc",
  "recipient": "<payout-address>",
  "methodDetails": {
    "accepts": [
      {
        "network": "algorand-mainnet",
        "amount": "10000",
        "asset": "31566704",
        "payTo": "<payout-address>",
        "resource": "my-inference-api"
      }
    ],
    "resource": "my-inference-api"
  }
}
```

Decoded `X-Payment-Required`:

```json
{
  "accepts": [
    {
      "network": "algorand-mainnet",
      "asset": "31566704",
      "amount": "10000",
      "payTo": "<payout-address>",
      "resource": "my-inference-api"
    }
  ],
  "resource": "my-inference-api"
}
```

### Challenge ID

The `id=` parameter in `WWW-Authenticate` is an HMAC-SHA256 value bound to `(realm, method, intent, request, expires)`. This prevents tampering with challenge parameters and allows single-use enforcement.

---

## Payment credential format

The agent submits payment proof as:

```
Authorization: Payment <base64-encoded JSON>
```

Or equivalently via `X-Payment` header:

```
X-Payment: <base64-encoded JSON>
```

Payload structure (with challenge echo — full spec compliance):

```json
{
  "challenge": {
    "id":     "<challenge-id-from-WWW-Authenticate>",
    "realm":  "<realm>",
    "method": "algorand",
    "intent": "charge"
  },
  "payload": {
    "txId": "<on-chain-transaction-id>",
    "payer": "<optional-sender-address>"
  }
}
```

The `challenge` object echoes back the challenge issued in the `WWW-Authenticate` header. The `id` must match a non-expired challenge issued by this gate. Credentials without a `challenge` object are still accepted for backward compatibility.

CAIP-2 network IDs are also accepted in `challenge.method` and resolved automatically:

| CAIP-2 | Internal |
|--------|----------|
| `algorand:mainnet` | `algorand-mainnet` |
| `voi:mainnet` | `voi-mainnet` |
| `hedera:mainnet` | `hedera-mainnet` |
| `stellar:pubnet` | `stellar-mainnet` |

---

## Payment-Receipt

After successful verification, the receipt is available via `result.receipt.as_header_value()`:

```
Payment-Receipt: <base64 JSON>
```

```json
{
  "status": "success",
  "method": "algorand",
  "timestamp": "2026-04-13T10:35:13Z",
  "reference": "<on-chain-tx-id>",
  "payer": "<sender-address>",
  "amount": 10000,
  "network": "algorand-mainnet"
}
```

---

## Replay protection

The adapter maintains an in-memory set of used `tx_id` values. Each payment proof is accepted exactly once per `MppGate` instance — subsequent attempts with the same `tx_id` are rejected with `"Payment proof already used"`.

> For multi-process deployments, replace `_used_tx_ids` with a shared store (Redis, DB).

## Challenge echo validation

Per IETF `draft-ryan-httpauth-payment` Table 3, the client must echo the issued challenge back in the credential. The adapter:

- Stores issued challenge IDs with expiry timestamps in `_issued_challenges`
- Validates `challenge.id` on submission — rejects unknown or expired IDs with `"Invalid or expired challenge"` and issues a fresh challenge
- Prunes expired entries on every `_build_challenge()` call to prevent unbounded growth
- Challenge IDs are HMAC-SHA256 values bound to `(realm, method, intent, request, expires)` — tamper-evident and stateless-compatible

---

## Network and asset mapping

| Config key | Wire format | Asset | Asset ID |
|-----------|-------------|-------|----------|
| `algorand_mainnet` | `algorand-mainnet` | USDC | 31566704 |
| `voi_mainnet` | `voi-mainnet` | aUSDC | 302190 |
| `hedera_mainnet` | `hedera-mainnet` | USDC HTS | 0.0.456858 |
| `stellar_mainnet` | `stellar-mainnet` | USDC Circle | `USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN` |

---

## Live test status

Confirmed end-to-end on **2026-04-13** (v2.1.0):

| Test | Result |
|------|--------|
| No credentials → HTTP 401 + `WWW-Authenticate: Payment` | Pass |
| `WWW-Authenticate`: `realm`, `id`, `method`, `intent="charge"`, `request=`, `expires=` | Pass |
| `id=` is HMAC-SHA256 bound, 32-char hex | Pass |
| `request=` decodes to charge intent object (`amount`, `currency`, `recipient`, `methodDetails`) | Pass |
| `amount` field (not `maxAmountRequired`) | Pass |
| `resource` field inside each accepts entry | Pass |
| `X-Payment-Required` decodes with `accepts` array | Pass |
| Challenge echo: valid `challenge.id` accepted, reaches indexer | Pass |
| Challenge echo: unknown/expired `challenge.id` rejected, new challenge issued | Pass |
| CAIP-2 `challenge.method` (`algorand:mainnet`, `voi:mainnet`, etc.) resolved | Pass |
| No `challenge` object (backward compat) — reaches indexer | Pass |
| Invalid base64 credential → 401 with encoding error | Pass |
| Missing `txId` → 401 with error | Pass |
| Fake `txId` → verification fails | Pass |
| Replay protection: used `tx_id` rejected | Pass |
| `MppReceipt`: `status`, `method`, `timestamp`, `reference` | Pass |
| WSGI guard returns `402 Payment Required` tuple | Pass |
| Hedera TX ID normalisation (wallet `@` format → Mirror Node `-` format) | Pass |
| Unit tests (153/153) | Pass |

## Live smoke tests — 4 chains

### 13 April 2026 — v2.1.0 (challenge echo validation, CAIP-2 routing)

0.01 USDC paid on each chain and verified end-to-end via on-chain indexers:

| Chain | TX ID | Result |
|-------|-------|--------|
| Algorand mainnet (USDC ASA 31566704) | `PNN25O7E6WTOWFB36YVZHRLIHICPOWOYBRDFP3ZJKKJ32PKL472A` | Pass |
| VOI mainnet (aUSDC ARC200 302190) | `YOJTOMTW7K2VASM3N2OALPIDC66CMABDD2ZJE4SYTHGR2H2MKTYA` | Pass |
| Hedera mainnet (USDC HTS 0.0.456858) | `0.0.10376692@1776103661.888390747` | Pass |
| Stellar pubnet (USDC Circle) | `338b0061e81cf615631f7830e0a480f6beed0c333206c4366c14e6a761393153` | Pass |

### 13 April 2026 — v2.0.0 (initial 4-chain release)

| Chain | TX ID | Result |
|-------|-------|--------|
| Algorand mainnet (USDC ASA 31566704) | `SV7VF66V5I2FKZNU5I5BKS3GKUB532S4LIKQIPFTZEHB4ZHRRDZA` | Pass |
| VOI mainnet (aUSDC ARC200 302190) | `DKD3AKI3QLSPOJEM6VQ35RDAEA77ID6TBRKXA2VSJUHFPJY6NLGA` | Pass |
| Hedera mainnet (USDC HTS 0.0.456858) | `0.0.10376692@1776079396.144430081` | Pass |
| Stellar pubnet (USDC Circle) | `fc84ef8a88c363238fb69e3d7766dacf36eff7f6f0dbaf35f34bacb7791d8832` | Pass |

## Verification architecture

Per the [MPP spec](https://paymentauth.org), there is no central verification API — servers verify on-chain directly. `MppGate._verify_payment()` dispatches to chain-specific methods:

### Algorand / VOI (AVM)
Queries the Algonode or VOI Nodely indexer:
- `receiver` == `payout_address`
- `amount` >= `amount_microunits`
- `asset-id` matches the network's expected USDC asset
- `confirmed-round` is present (transaction is finalised)

### Hedera
Queries the Hedera Mirror Node (`mainnet-public.mirrornode.hedera.com`):
- `result` == `"SUCCESS"`
- `token_transfers` contains a transfer to `payout_address` with amount >= `amount_microunits`
- TX ID normalisation: wallet format `0.0.account@seconds.nanos` → Mirror Node format `0.0.account-seconds-nanos`

### Stellar
Queries Horizon (`horizon.stellar.org`):
- Payment operation type with matching `asset_code` / `asset_issuer`
- `to` == `payout_address`
- `int(float(amount) * 1_000_000)` >= `amount_microunits` (Horizon returns decimal string)
