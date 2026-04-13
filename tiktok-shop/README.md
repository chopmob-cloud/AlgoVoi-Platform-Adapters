# TikTok Shop — AlgoVoi Payment Adapter

Connects AlgoVoi to the TikTok Shop Open Platform API to create on-chain USDC settlement links for TikTok Shop orders settled outside the standard TikTok Shop consumer checkout.

Full integration guide: [tiktok-shop.md](../tiktok-shop.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `tiktok_algovoi.py` | Adapter — receives TikTok Shop order webhooks and creates AlgoVoi payment links |
| `test_tiktok.py` | Integration test suite |

---

## Quick start

```python
from tiktok_algovoi import TikTokAlgoVoi

adapter = TikTokAlgoVoi(
    app_key="YOUR_APP_KEY",
    app_secret="YOUR_APP_SECRET",
    access_token="YOUR_ACCESS_TOKEN",
    api_base="https://api1.ilovechicken.co.uk",
    algovoi_api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
