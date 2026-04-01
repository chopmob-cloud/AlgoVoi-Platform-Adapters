# x402 — AI Agent Payments via AlgoVoi

AlgoVoi's gateway implements the **x402 protocol** — the open standard for autonomous machine-to-machine payments over HTTP. This allows AI agents to pay for resources, APIs, and data feeds in **USDC on Algorand** or **aUSDC on VOI**, without human intervention.

> x402 is co-developed by Coinbase, Cloudflare, Google, Stripe, AWS, Circle, Anthropic, and Vercel.
> AlgoVoi implements x402 natively on both the Algorand and VOI AVM networks.

---

## How it works

```
AI Agent makes HTTP request to a protected resource
            ↓
AlgoVoi Gateway responds: HTTP 402 Payment Required
  → X-PAYMENT-REQUIRED header (base64 JSON) describes what to pay
            ↓
Agent reads payment requirement:
  amount, asset (USDC/aUSDC), receiver address, network
            ↓
Agent signs and submits on-chain transaction (Algorand or VOI)
            ↓
Agent retries request with X-PAYMENT header (base64 proof: tx_id)
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
  "asset_id": 31566704,
  "payment_network": "algorand_mainnet",
  "access_ttl_secs": 3600,
  "note_binding_required": true
}
```

| Field | Description |
|-------|-------------|
| `amount_microunits` | Price per call in USDC microunits (1 USDC = 1,000,000) |
| `asset_id` | `31566704` = USDC on Algorand, `302190` = aUSDC on VOI |
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

Decoded `X-PAYMENT-REQUIRED`:

```json
{
  "version": 1,
  "accepts": [{
    "scheme": "exact",
    "network": "algorand-mainnet",
    "maxAmountRequired": "10000",
    "resource": "https://<your-api-host>/protected/my-inference-api",
    "description": "AlgoVoi: my-inference-api",
    "payTo": "<provider-payout-address>",
    "maxTimeoutSeconds": 300,
    "asset": "31566704",
    "extra": {
      "payment_reference": "<tenant_id>:<resource_id>"
    }
  }]
}
```

### Step 2 — Pay on-chain

Submit an Algorand or VOI transaction:
- **Receiver**: `payTo` address
- **Amount**: `maxAmountRequired` microunits of the specified asset
- **Note**: `payment_reference` value (required if `note_binding_required`)

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
  "network": "algorand-mainnet",
  "payload": {
    "tx_id": "<algorand-transaction-id>",
    "payer": "<optional-sender-address>"
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

---

## Live test status

Confirmed end-to-end on **2026-04-01** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook → checkout link | Webhook → checkout link | Webhook → checkout link | Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Skip |

Cannot auto-test: Protocol documentation — not a platform webhook adapter.

## Supported networks and assets

| Network | Asset | Asset ID | Notes |
|---------|-------|----------|-------|
| `algorand-mainnet` | USDC | ASA 31566704 | Native Circle USDC |
| `voi-mainnet` | aUSDC | ARC200 302190 | AlgoVoi network stablecoin |
| `algorand-testnet` | Test USDC | — | For development and testing |
| `voi-testnet` | Test aUSDC | — | For development and testing |

---

## Example: Python AI agent paying for an API call

```python
import base64
import json
import httpx
from algosdk.v2client import algod
from algosdk import transaction, encoding

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
        amt=int(accept["maxAmountRequired"]),
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
        "network": "algorand-mainnet",
        "payload": {"tx_id": tx_id, "payer": agent_address},
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
| Webhook → checkout link | Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Skip |

Both flows use the same tenant network configs, payout addresses, and on-chain verification via the Facilitator. Only the entry point differs.

---

## Resources

- [x402 Protocol specification](https://www.x402.org)
- [Coinbase x402 reference](https://docs.cdp.coinbase.com/x402/docs/welcome)
- [AlgoVoi hosted checkout](https://av.ilc-n.xyz)
