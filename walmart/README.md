# Walmart Marketplace — AlgoVoi Payment Adapter

Connects AlgoVoi to the Walmart Marketplace API to create on-chain USDC settlement links for Walmart orders settled outside the standard Walmart Pay checkout.

Full integration guide: [walmart.md](../walmart.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `walmart_algovoi.py` | Adapter — polls the Walmart Marketplace Orders API and creates AlgoVoi payment links |
| `test_walmart.py` | Integration test suite |

---

## Quick start

```python
from walmart_algovoi import WalmartAlgoVoi

adapter = WalmartAlgoVoi(
    client_id="YOUR_WALMART_CLIENT_ID",
    client_secret="YOUR_WALMART_CLIENT_SECRET",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
adapter.poll_and_notify()
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
