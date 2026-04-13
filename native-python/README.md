# Native Python — AlgoVoi Payment Adapter

Zero-dependency Python library for integrating AlgoVoi payments (hosted checkout, in-page wallet, and webhook verification) into any Python web application without pip dependencies.

Full integration guide: [native-python — see root README](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `algovoi.py` | Client library — hosted checkout, extension payment, webhook HMAC verification |
| `example.py` | Usage examples for Flask and Django |

---

## Quick start

```python
from algovoi import AlgoVoi

av = AlgoVoi(
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
    webhook_secret="YOUR_WEBHOOK_SECRET",
)

link = av.create_payment_link(amount=9.99, currency="USD", order_ref="ORDER-001")
# redirect customer to link["url"]
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
