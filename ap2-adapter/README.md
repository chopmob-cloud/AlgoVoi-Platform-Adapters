# AP2 — Agent Payment Protocol v2 Adapter for AlgoVoi

Drop-in server middleware for accepting AP2 payment mandates from AI agents using ed25519-signed credentials, with asynchronous settlement via AlgoVoi.

Full integration guide: [ap2-adapter.md](ap2-adapter.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `ap2.py` | Adapter — `Ap2Gate` middleware class for Flask, Django, FastAPI, or any WSGI/ASGI framework |
| `ap2-adapter.md` | Integration guide |
| `test_ap2.py` | Unit and integration tests |

---

## Quick start

```python
from ap2 import Ap2Gate

gate = Ap2Gate(
    merchant_id="shop42",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_...",
    tenant_id="uuid",
)

# Flask
@app.route("/api/resource", methods=["POST"])
def resource():
    result = gate.check(request.headers, request.get_json())
    if result.requires_payment:
        return result.as_flask_response()
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
