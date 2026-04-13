# OnBuy — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI for OnBuy marketplace orders via polling-based order detection, as OnBuy does not currently support push webhooks.

Full integration guide: [onbuy.md](../onbuy.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `onbuy_algovoi.py` | Adapter — polls the OnBuy Orders API for new orders and creates AlgoVoi payment links |
| `test_onbuy.py` | Integration test suite |

---

## Quick start

```python
from onbuy_algovoi import OnBuyAlgoVoi

adapter = OnBuyAlgoVoi(
    consumer_key="YOUR_CONSUMER_KEY",
    secret_key="YOUR_SECRET_KEY",
    site_id=2000,  # 2000 = UK
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
adapter.poll_and_notify()
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
