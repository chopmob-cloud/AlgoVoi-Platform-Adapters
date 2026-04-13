# Shopee — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI for Shopee orders across Southeast Asia and Brazil, with all API requests signed via HMAC-SHA256 using your Partner Key.

Full integration guide: [shopee.md](../shopee.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `shopee_algovoi.py` | Adapter — receives Shopee order push notifications and creates AlgoVoi payment links |
| `test_shopee.py` | Integration test suite |

---

## Quick start

```python
from shopee_algovoi import ShopeeAlgoVoi

adapter = ShopeeAlgoVoi(
    partner_id=1234567,
    partner_key="YOUR_PARTNER_KEY",
    shop_id=9876543,
    access_token="YOUR_ACCESS_TOKEN",
    api_base="https://api1.ilovechicken.co.uk",
    algovoi_api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
