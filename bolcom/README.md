# Bol.com — AlgoVoi Payment Adapter

Connects AlgoVoi to the Bol.com Retailer API to create on-chain USDC settlement links for Bol.com marketplace orders settled outside the standard Bol.com checkout.

Full integration guide: [bolcom.md](../bolcom.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `bolcom_algovoi.py` | Adapter — polls the Bol.com Retailer API for new orders and creates AlgoVoi payment links |
| `test_bolcom.py` | Integration test suite |

---

## Quick start

```python
from bolcom_algovoi import BolcomAlgoVoi

adapter = BolcomAlgoVoi(
    client_id="YOUR_BOLCOM_CLIENT_ID",
    client_secret="YOUR_BOLCOM_CLIENT_SECRET",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
adapter.poll_and_notify()
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
