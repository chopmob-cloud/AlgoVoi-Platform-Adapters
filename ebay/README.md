# eBay — AlgoVoi Payment Adapter

Connects AlgoVoi to the eBay Sell APIs to create on-chain USDC settlement links for eBay orders where stablecoin payment is arranged outside the standard eBay Managed Payments flow.

Full integration guide: [ebay.md](../ebay.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `ebay_algovoi.py` | Adapter — polls or receives eBay order events and creates AlgoVoi payment links |
| `test_ebay.py` | Integration test suite |

---

## Quick start

```python
from ebay_algovoi import EbayAlgoVoi

adapter = EbayAlgoVoi(
    refresh_token="YOUR_EBAY_REFRESH_TOKEN",
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
adapter.poll_and_notify()
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
