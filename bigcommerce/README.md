# BigCommerce — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI as payment in your BigCommerce store by receiving order webhooks and creating AlgoVoi hosted checkout links.

Full integration guide: [bigcommerce.md](../bigcommerce.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `bigcommerce_algovoi.py` | Adapter — receives BigCommerce order webhooks and creates AlgoVoi payment links |
| `test_bigcommerce.py` | Integration test suite |

---

## Quick start

```python
from bigcommerce_algovoi import BigCommerceAlgoVoi

adapter = BigCommerceAlgoVoi(
    store_hash="YOUR_STORE_HASH",
    access_token="YOUR_ACCESS_TOKEN",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
    webhook_secret="YOUR_WEBHOOK_SECRET",
)
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
