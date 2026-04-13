# Printify — AlgoVoi Payment Adapter

Pays Printify print-on-demand production costs in USDC on Algorand or aUSDC on VOI via AlgoVoi, triggered automatically when a new order arrives on your storefront.

Full integration guide: [printify.md](../printify.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `printify_algovoi.py` | Adapter — receives Printify order webhooks and creates AlgoVoi settlement links |
| `test_printify.py` | Integration test suite |

---

## Quick start

```python
from printify_algovoi import PrintifyAlgoVoi

adapter = PrintifyAlgoVoi(
    printify_api_token="YOUR_PRINTIFY_API_TOKEN",
    webhook_secret="YOUR_WEBHOOK_SECRET",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
