# Flipkart — AlgoVoi Payment Adapter

Connects AlgoVoi to the Flipkart Seller API to create on-chain USDC settlement links for Flipkart orders settled outside the standard Flipkart consumer checkout.

Full integration guide: [flipkart.md](../flipkart.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `flipkart_algovoi.py` | Adapter — polls the Flipkart Seller API for new orders and creates AlgoVoi payment links |
| `test_flipkart.py` | Integration test suite |

---

## Quick start

```python
from flipkart_algovoi import FlipkartAlgoVoi

adapter = FlipkartAlgoVoi(
    client_id="YOUR_FLIPKART_CLIENT_ID",
    client_secret="YOUR_FLIPKART_CLIENT_SECRET",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
adapter.poll_and_notify()
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
