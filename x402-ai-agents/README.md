# x402 AI Agent Payment Adapter

Drop-in Python middleware for accepting **x402 protocol v1** payments from autonomous AI agents. Implements the open standard for machine-to-machine payments over HTTP — agents discover, pay, and gain access without human intervention.

> x402 is co-developed by Coinbase, Cloudflare, Google, Stripe, AWS, Circle, Anthropic, and Vercel.  
> AlgoVoi implements x402 natively on Algorand, VOI, Hedera, and Stellar.

Full integration guide: [x402-ai-agents.md](../x402-ai-agents.md)  
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `x402_agents_algovoi.py` | Drop-in adapter — zero pip dependencies, stdlib only |
| `test_x402_agents.py` | Unit tests (76/76 passing) |

---

## How it works

```
AI Agent  →  GET /protected/resource  →  HTTP 402 + X-PAYMENT-REQUIRED
          ←  submits on-chain USDC tx
          →  GET /protected/resource + X-PAYMENT proof
          ←  HTTP 200 + X-PAYMENT-RECEIPT (JWT)
```

---

## Quick start

```python
from x402_agents_algovoi import AlgoVoiX402Gateway

gateway = AlgoVoiX402Gateway(
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_...",
    tenant_id="<your-tenant-uuid>",
    payout_address="<your-algorand-address>",
    networks=["algorand_mainnet"],
    amount_microunits=10000,   # 0.01 USDC per call
)
```

### Flask

```python
@app.before_request
def check_payment():
    result = gateway.check(dict(request.headers))
    if result.requires_payment:
        return result.as_flask_response()
```

### Manual (WSGI / FastAPI)

```python
result = gateway.check(request_headers)
if result.requires_payment:
    # Return 402 with X-PAYMENT-REQUIRED header
    headers, body = result.as_wsgi_response()
```

---

## Supported networks

| Network key | CAIP-2 ID | Asset | Asset ID |
|-------------|-----------|-------|----------|
| `algorand_mainnet` | `algorand:mainnet` | USDC | `31566704` |
| `voi_mainnet` | `voi:mainnet` | aUSDC | `302190` |
| `stellar_mainnet` | `stellar:pubnet` | USDC | `USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN` |
| `hedera_mainnet` | `hedera:mainnet` | USDC | `0.0.456858` |

---

## Payment requirement format (x402 spec v1)

```json
{
  "x402Version": 1,
  "accepts": [{
    "scheme": "exact",
    "network": "algorand:mainnet",
    "amount": "10000",
    "asset": "31566704",
    "payTo": "<payout-address>",
    "maxTimeoutSeconds": 300
  }],
  "resource": {
    "url": "https://<host>/protected/<resource>",
    "description": "AlgoVoi: <resource-id>"
  }
}
```

## Payment proof format

```json
{
  "x402Version": 1,
  "scheme": "exact",
  "network": "algorand:mainnet",
  "payload": {
    "signature": "<on-chain-tx-id>",
    "authorization": {
      "from": "<payer-address>",
      "to": "<payTo-address>",
      "amount": "10000",
      "asset": "31566704"
    }
  }
}
```

---

## Live test status — 13 April 2026

| Chain | Result |
|-------|--------|
| Algorand mainnet | Pass — `x402/verify` confirmed `verified:true` |
| VOI mainnet | Pass — `x402/verify` confirmed `verified:true` |
| Stellar pubnet | Pass — `x402/verify` confirmed `verified:true` |
| Hedera mainnet | Pass — `x402/verify` confirmed `verified:true` |
| Unit tests (76/76) | Pass |

---

## Resources

- [x402 Protocol specification](https://www.x402.org)
- [Coinbase x402 reference](https://docs.cdp.coinbase.com/x402/docs/welcome)
- [AlgoVoi Platform Adapters](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters)

---

Licensed under the Business Source License 1.1 — see LICENSE for details.
