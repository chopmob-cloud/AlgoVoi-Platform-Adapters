# Etsy — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI for Etsy orders as an additional payment option for custom commissions and international orders settled outside the standard Etsy Payments checkout.

Full integration guide: [etsy.md](../etsy.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `etsy_algovoi.py` | Adapter — polls the Etsy Open API for new orders and creates AlgoVoi payment links |
| `test_etsy.py` | Integration test suite |

---

## Quick start

```python
from etsy_algovoi import EtsyAlgoVoi

adapter = EtsyAlgoVoi(
    keystring="YOUR_ETSY_API_KEYSTRING",
    access_token="YOUR_OAUTH_ACCESS_TOKEN",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
adapter.poll_and_notify()
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
