# AP2 — Agent Payment Protocol v2 Adapter for AlgoVoi

Drop-in server middleware for accepting AP2 payment mandates from AI agents using ed25519-signed credentials. No on-chain transaction required at point of purchase — settlement is asynchronous.

**Smoke tested 2026-04-13 — real ed25519 key pair, valid mandate accepted, tampered mandates rejected. 55/55 tests passing.**

Full integration guide: [ap2-adapter.md](ap2-adapter.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `ap2.py` | Adapter — `Ap2Gate` middleware class for Flask, Django, FastAPI, or any WSGI/ASGI framework |
| `ap2-adapter.md` | Integration guide |
| `test_ap2.py` | 55 unit tests including real ed25519 signature verification |

---

## Supported chains

| Config key | Wire format | Asset |
|-----------|-------------|-------|
| `algorand_mainnet` | `algorand-mainnet` | USDC (ASA 31566704) |
| `voi_mainnet` | `voi-mainnet` | aUSDC (ARC200 302190) |
| `hedera_mainnet` | `hedera-mainnet` | USDC (HTS 0.0.456858) |
| `stellar_mainnet` | `stellar-mainnet` | USDC (Circle) |

---

## Quick start

Copy `ap2.py` into your project. No package install required.

```python
from ap2 import Ap2Gate

gate = Ap2Gate(
    merchant_id="shop42",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_...",
    tenant_id="<your-tenant-uuid>",
    amount_usd=1.99,
    networks=["algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet"],
)

# Flask
@app.route("/api/resource", methods=["POST"])
def resource():
    result = gate.check(dict(request.headers), request.get_json(silent=True))
    if result.requires_payment:
        return result.as_flask_response()
    # result.mandate.payer_address, .amount, .network
    return jsonify(data="premium content")
```

---

## Smoke test — 13 April 2026

| Test | Result |
|------|--------|
| Real ed25519 key pair — valid mandate accepted | ✅ Pass |
| Tampered mandate (amount changed) — rejected | ✅ Pass |
| Wrong signature (different key) — rejected | ✅ Pass |
| cryptography package fallback verification | ✅ Pass |
| 4-network payment request (ALGO, VOI, HBAR, XLM) | ✅ Pass |

---

Licensed under the [Business Source License 1.1](../LICENSE).
