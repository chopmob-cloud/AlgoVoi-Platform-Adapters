# CeX (Computer Exchange) — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI for CeX Marketplace orders by generating AlgoVoi payment links, working around CeX's lack of a public Seller API via email/manual trigger.

Full integration guide: [cex.md](../cex.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `cex_algovoi.py` | Adapter — generates AlgoVoi payment links for CeX orders |
| `test_cex.py` | Integration test suite |

---

## Quick start

```python
from cex_algovoi import CexAlgoVoi

adapter = CexAlgoVoi(
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
link = adapter.create_payment_link(order_ref="CEX-12345", amount=49.99, currency="GBP")
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
