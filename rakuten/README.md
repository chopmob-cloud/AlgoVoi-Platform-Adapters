# Rakuten Ichiba — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI for Rakuten Ichiba orders via polling-based order detection, as the Rakuten Merchant Server (RMS) API does not support outbound webhooks.

Full integration guide: [rakuten.md](../rakuten.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `rakuten_algovoi.py` | Adapter — polls the RMS Order API for new orders and creates AlgoVoi payment links |
| `test_rakuten.py` | Integration test suite |

---

## Quick start

```python
from rakuten_algovoi import RakutenAlgoVoi

adapter = RakutenAlgoVoi(
    service_secret="YOUR_SERVICE_SECRET",
    license_key="YOUR_LICENSE_KEY",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
adapter.poll_and_notify()
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
