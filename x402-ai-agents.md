# x402 — AI Agent Payments via AlgoVoi

AlgoVoi's gateway implements the **x402 protocol v1** — the open standard for autonomous machine-to-machine payments over HTTP. AI agents pay for resources, APIs, and data feeds in **USDC on Algorand, VOI, Hedera, or Stellar**, without human intervention.

> x402 is co-developed by Coinbase, Cloudflare, Google, Stripe, AWS, Circle, Anthropic, and Vercel.
> AlgoVoi implements x402 natively on Algorand, VOI, Hedera, and Stellar.

---

## How it works

```
AI Agent makes HTTP request to a protected resource
            ↓
AlgoVoi Gateway responds: HTTP 402 Payment Required
  → X-PAYMENT-REQUIRED header (base64 JSON) describes what to pay
            ↓
Agent reads payment requirement:
  accepts array, amount (microunits), asset ID, payTo address, network (CAIP-2)
            ↓
Agent signs and submits on-chain transaction
            ↓
Agent retries request with X-PAYMENT header (base64 proof: signature/tx_id)
            ↓
AlgoVoi Gateway: Facilitator verifies tx on-chain
            ↓
HTTP 200 OK + resource body + X-PAYMENT-RECEIPT (JWT)
```

No wallets to set up per user. No OAuth flows. No API keys passed around.
Payment is settled on-chain in seconds.

---

## For AI service providers — gating your API

Register your endpoint as a **resource definition** in AlgoVoi:

```http
POST /internal/tenants/{tenant_id}/resources
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "resource_id": "my-inference-api",
  "networks": ["algorand_mainnet"],
  "amount_microunits": 10000,
  "asset_id": "31566704",
  "payment_network": "algorand_mainnet",
  "access_ttl_secs": 3600,
  "note_binding_required": true
}
```

| Field | Description |
|-------|-------------|
| `amount_microunits` | Price per call in USDC microunits (1 USDC = 1,000,000) |
| `asset_id` | String asset identifier — see network table below |
| `access_ttl_secs` | How long the JWT receipt grants access (e.g. 3600 = 1 hour) |
| `note_binding_required` | Require payment tx note to include tenant/resource ID |

Your resource is now live at:

```
GET https://<your-api-host>/protected/my-inference-api
```

Any client without payment receives HTTP 402 with the payment requirement.

---

## For AI agents — paying for resources

### Step 1 — Discover what to pay

```http
GET https://<your-api-host>/protected/my-inference-api
```

**Response:**
```
HTTP 402 Payment Required
X-PAYMENT-REQUIRED: <base64-encoded JSON>
```

Decoded `X-PAYMENT-REQUIRED` (x402 spec v1 format):

```json
{
  "x402Version": 1,
  "accepts": [{
    "scheme": "exact",
    "network": "algorand:mainnet",
    "amount": "10000",
    "asset": "31566704",
    "payTo": "<provider-payout-address>",
    "maxTimeoutSeconds": 300,
    "extra": {
      "name": "USDC",
      "decimals": 6,
      "description": "AlgoVoi: my-inference-api",
      "payment_reference": "<tenant_id>:<resource_id>"
    }
  }],
  "resource": {
    "url": "https://<your-api-host>/protected/my-inference-api",
    "description": "AlgoVoi: my-inference-api"
  }
}
```

### Step 2 — Pay on-chain

Submit a transaction on the specified network:
- **Receiver**: `accepts[0].payTo` address
- **Amount**: `accepts[0].amount` microunits of the specified asset
- **Note**: `extra.payment_reference` value (required if `note_binding_required`)

### Step 3 — Retry with proof

```http
GET https://<your-api-host>/protected/my-inference-api
X-PAYMENT: <base64-encoded JSON>
```

`X-PAYMENT` payload:

```json
{
  "x402Version": 1,
  "scheme": "exact",
  "network": "algorand:mainnet",
  "payload": {
    "signature": "<on-chain-tx-id-or-checkout-token>",
    "authorization": {
      "from": "<payer-address>",
      "to": "<payTo-address>",
      "amount": "10000",
      "asset": "31566704"
    }
  }
}
```

### Step 4 — Use the receipt

**Response:**
```
HTTP 200 OK
X-PAYMENT-RECEIPT: <JWT>
```

The JWT receipt can be cached and replayed within `access_ttl_secs` — no need to pay again for every request within the window.

---

## Live test status

Confirmed end-to-end on **2026-04-13** against `api1.ilovechicken.co.uk`:

| Test | Result |
|------|--------|
| Algorand: checkout paid, x402/verify `verified:true` | Pass |
| VOI: checkout paid, x402/verify `verified:true` | Pass |
| Stellar: checkout paid, x402/verify `verified:true` | Pass |
| Hedera: checkout paid, x402/verify `verified:true` | Pass |
| `create_payment_requirement` — spec format, all 4 networks | Pass |
| `header_value` decodes to `x402Version: 1`, `accepts` array | Pass |
| `decode_payment_requirement` roundtrip | Pass |
| `verify_x402_payment` — `payload.signature` and legacy `payload.tx_id` | Pass |
| Unit tests (76/76) | Pass |

## Supported networks and assets

| Network key | CAIP-2 ID | Asset | Asset ID |
|-------------|-----------|-------|----------|
| `algorand_mainnet` | `algorand:mainnet` | USDC | `31566704` |
| `voi_mainnet` | `voi:mainnet` | aUSDC | `302190` |
| `stellar_mainnet` | `stellar:pubnet` | USDC | `USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN` |
| `hedera_mainnet` | `hedera:mainnet` | USDC | `0.0.456858` |

---

## Example: Python AI agent paying for an API call

```python
import base64
import json
import httpx
from algosdk.v2client import algod
from algosdk import transaction

RESOURCE_URL = "https://<your-api-host>/protected/my-inference-api"

def b64_json(obj: dict) -> str:
    return base64.b64encode(json.dumps(obj).encode()).decode()

def fetch_with_payment(agent_private_key: str, agent_address: str) -> dict:
    # Step 1: probe for payment requirement
    resp = httpx.get(RESOURCE_URL)
    if resp.status_code != 402:
        return resp.json()

    requirement = json.loads(base64.b64decode(resp.headers["X-Payment-Required"]))
    accept = requirement["accepts"][0]

    # Step 2: submit on-chain payment
    client = algod.AlgodClient("", "https://mainnet-api.algonode.cloud")
    params = client.suggested_params()

    txn = transaction.AssetTransferTxn(
        sender=agent_address,
        sp=params,
        receiver=accept["payTo"],
        amt=int(accept["amount"]),
        index=int(accept["asset"]),
        note=accept["extra"]["payment_reference"].encode(),
    )
    signed = txn.sign(agent_private_key)
    tx_id = client.send_transaction(signed)
    transaction.wait_for_confirmation(client, tx_id, 4)

    # Step 3: retry with proof
    proof = b64_json({
        "x402Version": 1,
        "scheme": "exact",
        "network": accept["network"],
        "payload": {
            "signature": tx_id,
            "authorization": {
                "from": agent_address,
                "to": accept["payTo"],
                "amount": accept["amount"],
                "asset": accept["asset"],
            },
        },
    })
    result = httpx.get(RESOURCE_URL, headers={"X-Payment": proof})
    result.raise_for_status()
    return result.json()
```

---

## How x402 and e-commerce adapters coexist

AlgoVoi serves two distinct payment flows from the same infrastructure:

| Flow | Who pays | Trigger | Settlement |
|------|----------|---------|-----------|
| **x402** | AI agent (autonomous) | HTTP 402 response | Per-call, real-time, on-chain |
| **E-commerce adapters** | Human customer | Shopify/WooCommerce/etc. order webhook | Per-order, hosted checkout |

Both flows use the same tenant network configs, payout addresses, and on-chain verification via the Facilitator. Only the entry point differs.

---

## Resources

- [x402 Protocol specification](https://www.x402.org)
- [Coinbase x402 reference](https://docs.cdp.coinbase.com/x402/docs/welcome)
- [AlgoVoi hosted checkout](https://av.ilc-n.xyz)
