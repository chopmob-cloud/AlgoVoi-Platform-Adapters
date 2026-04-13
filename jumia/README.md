# Jumia — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI for Jumia orders across Africa's leading e-commerce platform, covering Nigeria, Kenya, Egypt, Ghana, and seven other countries.

Full integration guide: [jumia.md](../jumia.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `jumia_algovoi.py` | Adapter — polls the Jumia SellerCenter API for new orders and creates AlgoVoi payment links |
| `test_jumia.py` | Integration test suite |

---

## Quick start

```python
from jumia_algovoi import JumiaAlgoVoi

adapter = JumiaAlgoVoi(
    api_key="YOUR_JUMIA_API_KEY",
    api_secret="YOUR_JUMIA_API_SECRET",
    country="ng",  # ng, ke, eg, gh, sn, ci, ug, tz, ma, tn
    api_base="https://api1.ilovechicken.co.uk",
    algovoi_api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
adapter.poll_and_notify()
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
