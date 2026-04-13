# Instagram & Facebook Shops — AlgoVoi Payment Adapter

Enables AlgoVoi hosted checkout as the external payment destination for Instagram and Facebook Shops, redirecting customers from Meta's Commerce API to pay on-chain in USDC or aUSDC.

Full integration guide: [instagram-shops.md](../instagram-shops.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `instagram_algovoi.py` | Adapter — handles Meta Commerce webhooks and creates AlgoVoi payment links |
| `test_instagram.py` | Integration test suite |

---

## Quick start

```python
from instagram_algovoi import InstagramAlgoVoi

adapter = InstagramAlgoVoi(
    access_token="YOUR_META_ACCESS_TOKEN",
    app_secret="YOUR_APP_SECRET",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
