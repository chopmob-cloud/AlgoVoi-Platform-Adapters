# TikTok Shop — AlgoVoi Payment Adapter

Connects AlgoVoi to the TikTok Shop Open Platform API to create on-chain USDC settlement links for TikTok Shop orders settled outside the standard TikTok Shop consumer checkout.

Full integration guide: [tiktok-shop.md](../tiktok-shop.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `tiktok_algovoi.py` | Adapter — verifies signed TikTok Shop webhooks, creates AlgoVoi payment links, updates shipping back to the Open Platform |
| `test_tiktok.py` | Integration test suite |
| `security_replay.py` | Security replay suite (HMAC, SSRF, amount sanity, replay) |

---

## Quick start

```python
from flask import Flask
from tiktok_algovoi import TikTokAlgoVoi

adapter = TikTokAlgoVoi(
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_UUID",
    webhook_secret="YOUR_ALGOVOI_WEBHOOK_SECRET",
    tiktok_app_secret="YOUR_TIKTOK_APP_SECRET",
    default_network="algorand_mainnet",   # or voi_, hedera_, stellar_mainnet
    base_currency="GBP",
)

app = Flask(__name__)
app.add_url_rule(
    "/webhook/tiktok",
    view_func=adapter.flask_webhook_handler(),
    methods=["POST"],
)
```

After payment is confirmed on-chain you can post the on-chain TX back
to TikTok Shop as the shipping reference:

```python
if adapter.verify_payment(token):
    adapter.update_shipping(
        order_id="TT-12345",
        tx_id="ON_CHAIN_TX_ID",
        access_token="TIKTOK_OPEN_PLATFORM_TOKEN",
        api_base="https://open-api.tiktokglobalshop.com",  # or -sg / -eu
    )
```

> **Security notes**
> - `update_shipping()` will refuse any `api_base` that is not one of
>   `ALLOWED_TIKTOK_HOSTS` (open-api{,sg,eu}.tiktokglobalshop.com).
> - The HMAC verifier covers the request body only. If your shop is
>   configured to sign over `(timestamp + body)`, wrap or replace
>   `verify_tiktok_webhook` with the correct concatenation.
> - The adapter does NOT dedupe webhook replays — track processed
>   `order_id` values in your persistence layer and reject duplicates.

---

Licensed under the [Business Source License 1.1](../LICENSE).
