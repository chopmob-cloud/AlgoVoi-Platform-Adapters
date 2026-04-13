# MPP — Machine Payments Protocol Adapter for AlgoVoi

Drop-in server middleware that gates APIs behind MPP payment challenges, implementing the HTTP Payment Authentication scheme per the IETF draft with on-chain verification via the Algorand or VOI indexer.

Full integration guide: [mpp-adapter.md](mpp-adapter.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `mpp.py` | Adapter — `MppGate` middleware class for Flask, Django, FastAPI, or any WSGI/ASGI framework |
| `mpp-adapter.md` | Integration guide |
| `test_mpp.py` | Unit and integration tests |
| `smoke_test_mpp.py` | End-to-end smoke test against live AlgoVoi API |

---

## Quick start

```python
from mpp import MppGate

gate = MppGate(
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_...",
    tenant_id="uuid",
    resource_id="my-api",
    price_usdc=0.01,
)

@app.route("/api/resource", methods=["GET"])
def resource():
    result = gate.check(request.headers)
    if result.requires_payment:
        return result.as_flask_response()
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
