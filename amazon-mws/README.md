# Amazon Marketplace — AlgoVoi Payment Adapter

Connects AlgoVoi to the Amazon Selling Partner API to create on-chain USDC settlement links for Amazon Marketplace orders where stablecoin payment is agreed outside the standard Amazon Pay checkout.

Full integration guide: [amazon.md](../amazon.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `amazon_algovoi.py` | Adapter — polls the SP-API Orders endpoint and creates AlgoVoi payment links |
| `test_amazon.py` | Integration test suite |

---

## Quick start

```python
from amazon_algovoi import AmazonAlgoVoi

adapter = AmazonAlgoVoi(
    refresh_token="YOUR_LWA_REFRESH_TOKEN",
    client_id="YOUR_LWA_CLIENT_ID",
    client_secret="YOUR_LWA_CLIENT_SECRET",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
adapter.poll_and_notify()
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
