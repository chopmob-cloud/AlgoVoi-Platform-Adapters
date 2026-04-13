# Printful — AlgoVoi Payment Adapter

Pays Printful print-on-demand production costs in USDC on Algorand or aUSDC on VOI via AlgoVoi, triggered automatically when a new order arrives on your storefront.

Full integration guide: [printful.md](../printful.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `printful_algovoi.py` | Adapter — receives Printful order webhooks and creates AlgoVoi settlement links |
| `test_printful.py` | Integration test suite |

---

## Quick start

```python
from printful_algovoi import PrintfulAlgoVoi

adapter = PrintfulAlgoVoi(
    printful_api_key="YOUR_PRINTFUL_API_KEY",
    webhook_secret="YOUR_WEBHOOK_SECRET",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
