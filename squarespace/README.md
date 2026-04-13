# Squarespace Commerce — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI as payment in your Squarespace store by receiving order webhooks and creating AlgoVoi hosted checkout links.

Full integration guide: [squarespace.md](../squarespace.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `squarespace_algovoi.py` | Adapter — receives Squarespace order webhooks and creates AlgoVoi payment links |
| `test_squarespace.py` | Integration test suite |

---

## Quick start

```python
from squarespace_algovoi import SquarespaceAlgoVoi

adapter = SquarespaceAlgoVoi(
    api_key="YOUR_SQUARESPACE_API_KEY",
    webhook_secret="YOUR_WEBHOOK_SECRET",
    api_base="https://api1.ilovechicken.co.uk",
    algovoi_api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
