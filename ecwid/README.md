# Ecwid — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI as payment in your Ecwid store by receiving order webhooks and creating AlgoVoi hosted checkout links.

Full integration guide: [ecwid.md](../ecwid.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `ecwid_algovoi.py` | Adapter — receives Ecwid order webhooks and creates AlgoVoi payment links |
| `test_ecwid.py` | Integration test suite |

---

## Quick start

```python
from ecwid_algovoi import EcwidAlgoVoi

adapter = EcwidAlgoVoi(
    store_id="YOUR_STORE_ID",
    secret_token="YOUR_SECRET_TOKEN",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
    webhook_secret="YOUR_WEBHOOK_SECRET",
)
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
