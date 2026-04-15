# Squarespace Commerce — AlgoVoi Payment Adapter

Accepts USDC on Algorand, aUSDC on VOI, USDC on Hedera, and USDC on Stellar as
payment in your Squarespace store by receiving order webhooks and creating
AlgoVoi hosted checkout links. Squarespace itself does not allow custom payment
gateways at checkout, so this adapter is for post-order B2B / settlement flows.

Full integration guide: [squarespace.md](../squarespace.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `squarespace_algovoi.py` | Adapter — verifies signed Squarespace webhooks, creates AlgoVoi payment links, marks orders as fulfilled |
| `test_squarespace.py` | Integration test suite |
| `security_replay.py` | Security replay suite (HMAC, null fuzzing, amount sanity, replay) |

---

## Quick start

```python
from flask import Flask
from squarespace_algovoi import SquarespaceAlgoVoi

adapter = SquarespaceAlgoVoi(
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",                # AlgoVoi API key
    tenant_id="YOUR_TENANT_UUID",
    squarespace_api_key="YOUR_SQUARESPACE_API_KEY",  # Squarespace Commerce key
    webhook_secret="YOUR_SQUARESPACE_WEBHOOK_SECRET",
    default_network="algorand_mainnet",         # or voi_, hedera_, stellar_mainnet
    base_currency="GBP",
)

app = Flask(__name__)
app.add_url_rule(
    "/webhook/squarespace",
    view_func=adapter.flask_webhook_handler(),
    methods=["POST"],
)
```

After payment is confirmed on-chain, mark the Squarespace order as fulfilled
with the on-chain TX as the tracking reference:

```python
if adapter.verify_payment(token):
    adapter.fulfill_order(order_id="sq-order-123", tx_id="ON_CHAIN_TX_ID")
```

> **Security notes**
> - `api_key` is your **AlgoVoi** key (`algv_…`); `squarespace_api_key` is your
>   **Squarespace Commerce** key. Don't confuse them — AlgoVoi will reject
>   anything that doesn't start with `algv_`.
> - `verify_webhook` requires `webhook_secret` to be set; an empty secret
>   rejects every signature (no empty-key HMAC bypass).
> - The adapter does NOT dedupe webhook replays — track processed
>   `order_id` values in your persistence layer and reject duplicates.

---

Licensed under the [Business Source License 1.1](../LICENSE).
