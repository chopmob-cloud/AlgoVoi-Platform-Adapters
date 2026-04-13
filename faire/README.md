# Faire — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI for Faire wholesale orders as an alternative settlement layer for brands that accept stablecoin payment outside the standard Faire checkout.

Full integration guide: [faire.md](../faire.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `faire_algovoi.py` | Adapter — receives Faire order webhooks and creates AlgoVoi payment links |
| `test_faire.py` | Integration test suite |

---

## Quick start

```python
from faire_algovoi import FaireAlgoVoi

adapter = FaireAlgoVoi(
    api_key="YOUR_FAIRE_API_KEY",
    webhook_secret="YOUR_WEBHOOK_SECRET",
    api_base="https://api1.ilovechicken.co.uk",
    algovoi_api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
