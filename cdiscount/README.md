# Cdiscount — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI for Cdiscount marketplace orders via AlgoVoi, integrating with France's second-largest e-commerce marketplace through the Octopia REST API.

Full integration guide: [cdiscount.md](../cdiscount.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `cdiscount_algovoi.py` | Adapter — polls the Octopia REST API for new orders and creates AlgoVoi payment links |
| `test_cdiscount.py` | Integration test suite |

---

## Quick start

```python
from cdiscount_algovoi import CdiscountAlgoVoi

adapter = CdiscountAlgoVoi(
    api_key="YOUR_OCTOPIA_API_KEY",
    api_base="https://api1.ilovechicken.co.uk",
    algovoi_api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
adapter.poll_and_notify()
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
