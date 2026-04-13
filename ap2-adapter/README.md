# AP2 — Agent Payment Protocol v2 Adapter for AlgoVoi

Drop-in server middleware for accepting AP2 v0.1 payment mandates from AI agents. Implements the [AlgoVoi crypto-algo extension](https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1) to the AP2 v0.1 spec, adding Algorand and VOI on-chain payments to the CartMandate / PaymentMandate flow.

**v2.0.0 — 81/81 tests passing. Real ed25519 smoke-tested 2026-04-13.**

Extension URI:  `https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1`
Schema:         `https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1/schema.json`
Extensions API: `https://api1.ilovechicken.co.uk/ap2/extensions`

Full integration guide: [ap2-adapter.md](ap2-adapter.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Agent requests resource
        |
        v
Ap2Gate.check() -- no X-AP2-Mandate found
        |
        v
HTTP 402 + X-AP2-Cart-Mandate header
  CartMandate.contents.payment_request.payment_methods:
    [ { supported_methods: "https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1",
        data: { network, receiver, amount_microunits, asset_id, ... } } ]
        |
        v
Agent pays on-chain (Algorand or VOI USDC)
Agent signs PaymentMandate (ed25519) with tx_id
        |
        v
Ap2Gate: verify ed25519 sig + verify tx on-chain via indexer
        |
        v
HTTP 200 -- result.mandate has payer_address, network, tx_id
```

---

## Files

| File | Description |
|------|-------------|
| `ap2.py` | Adapter — `Ap2Gate`, `Ap2CartMandate`, `Ap2Mandate`, `Ap2Result` |
| `ap2-adapter.md` | Full integration guide |
| `test_ap2.py` | 81 unit tests |

---

## Supported chains

| Network key | Asset | Asset ID | Indexer |
|-------------|-------|----------|---------|
| `algorand-mainnet` | USDC | ASA 31566704 | Algonode |
| `voi-mainnet` | aUSDC | ARC200 302190 | Nodely |

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

# Flask
@app.route("/api/resource", methods=["POST"])
def resource():
    result = gate.check(dict(request.headers), request.get_json(silent=True))
    if result.requires_payment:
        return result.as_flask_response()
    # result.mandate.payer_address, .network, .tx_id
    return jsonify(data="premium content")
```

### PaymentMandate format (agent submits)

```json
{
  "ap2_version": "0.1",
  "type": "PaymentMandate",
  "merchant_id": "shop42",
  "payer_address": "<algorand-ed25519-address>",
  "payment_response": {
    "method_name": "https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1",
    "details": {
      "network":    "algorand-mainnet",
      "tx_id":      "<on-chain-tx-id>",
      "note_field": "<cart-mandate-hash-optional>"
    }
  },
  "signature": "<base64-ed25519-sig-over-canonical-json>"
}
```

---

## Smoke test — 13 April 2026

Real ed25519 key pair per chain. PaymentMandate signed + on-chain tx verified end-to-end:

| Chain | TX ID | Result |
|-------|-------|--------|
| Algorand | `SDIX4LHMRGX5E2JJ5XTZ7WEKIZB6AVSLIRWUPTQ3FYKRSSVDMHWQ` | ✅ Pass |
| VOI | `WQIO2BHWFDWBSDHBBZDOLOYIFQ2ITH4OQKFGHMDEIHUU3TDOTY6A` | ✅ Pass |
| Hedera | `0.0.10376692@1776113910.019442287` | ✅ Pass |
| Stellar | `a6288f502789073abafec698e3d543396367d9efa1618de62bafbb93c6791a58` | ✅ Pass |

| Sig test | Result |
|----------|--------|
| Tampered mandate — sig rejected | ✅ Pass |
| Wrong key — rejected | ✅ Pass |
| cryptography fallback | ✅ Pass |
| Replay protection | ✅ Pass |

---

Licensed under the [Business Source License 1.1](../LICENSE).
