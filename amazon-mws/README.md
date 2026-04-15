# Amazon Marketplace — AlgoVoi Payment Adapter

Connects AlgoVoi to the Amazon Selling Partner API to create on-chain USDC settlement links for Amazon Marketplace orders where stablecoin payment is agreed outside the standard Amazon Pay checkout.

Full integration guide: [amazon.md](../amazon.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `amazon_algovoi.py` | Adapter — receives signed AlgoVoi webhooks, creates payment links, and confirms shipment back to SP-API |
| `test_amazon.py` | Integration test suite |
| `security_replay.py` | Security replay suite (HMAC, SSRF, amount sanity, replay) |

---

## Quick start

The adapter is webhook-driven. Wire it into Flask (or any WSGI framework
that exposes a request body and headers) and AlgoVoi will POST signed
ORDER_CHANGE notifications to your endpoint.

```python
from flask import Flask
from amazon_algovoi import AmazonAlgoVoi

adapter = AmazonAlgoVoi(
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_UUID",
    webhook_secret="YOUR_WEBHOOK_SECRET",
    default_network="algorand_mainnet",   # or voi_, hedera_, stellar_mainnet
    base_currency="GBP",
)

app = Flask(__name__)
app.add_url_rule(
    "/webhook/amazon",
    view_func=adapter.flask_webhook_handler(),
    methods=["POST"],
)
```

After payment is confirmed on-chain you can post the on-chain TX back to
Amazon as the payment reference:

```python
if adapter.verify_payment(token):
    adapter.confirm_shipment(
        amazon_order_id="123-1234567-1234567",
        tx_id="ON_CHAIN_TX_ID",
        sp_api_token="LWA_ACCESS_TOKEN",
        marketplace_url=AmazonAlgoVoi.MARKETPLACES["UK"]["endpoint"],
    )
```

> **Security note** — `confirm_shipment()` will refuse any `marketplace_url`
> that is not one of Amazon's official SP-API endpoints. Always pass a
> value from `AmazonAlgoVoi.MARKETPLACES`. Callers MUST also dedupe by
> `amazon_order_id` in their persistence layer — the adapter does not
> guard against webhook replay.

---

Licensed under the [Business Source License 1.1](../LICENSE).
