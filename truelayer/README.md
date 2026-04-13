# TrueLayer — AlgoVoi Payment Adapter

Accepts bank transfers via TrueLayer open banking (Faster Payments / SEPA Instant) and settles the fiat inbound leg as USDC on Algorand or aUSDC on VOI via AlgoVoi.

Full integration guide: [truelayer.md](../truelayer.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `truelayer_algovoi.py` | Adapter — verifies TrueLayer payment webhooks (Tl-Signature) and creates AlgoVoi settlement links |
| `test_truelayer.py` | Integration test suite |

---

## Quick start

```python
from truelayer_algovoi import TrueLayerAlgoVoi

adapter = TrueLayerAlgoVoi(
    client_id="YOUR_TRUELAYER_CLIENT_ID",
    client_secret="YOUR_TRUELAYER_CLIENT_SECRET",
    webhook_signing_key="YOUR_WEBHOOK_PUBLIC_KEY",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
