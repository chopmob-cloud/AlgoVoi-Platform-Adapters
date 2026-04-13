# Lazada — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI for Lazada orders across six Southeast Asian countries (MY, TH, PH, SG, ID, VN) from a single seller account integration.

Full integration guide: [lazada.md](../lazada.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `lazada_algovoi.py` | Adapter — polls the Lazada Open Platform API for new orders and creates AlgoVoi payment links |
| `test_lazada.py` | Integration test suite |

---

## Quick start

```python
from lazada_algovoi import LazadaAlgoVoi

adapter = LazadaAlgoVoi(
    app_key="YOUR_APP_KEY",
    app_secret="YOUR_APP_SECRET",
    access_token="YOUR_ACCESS_TOKEN",
    region="MY",  # MY, TH, PH, SG, ID, VN
    api_base="https://api1.ilovechicken.co.uk",
    algovoi_api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
adapter.poll_and_notify()
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
