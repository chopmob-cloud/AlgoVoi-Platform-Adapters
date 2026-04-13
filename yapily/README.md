# Yapily — AlgoVoi Payment Adapter

Accepts bank transfers via Yapily open banking (Faster Payments / SEPA Instant, covering 2,000+ banks across 46+ countries) and settles the fiat inbound leg as USDC on Algorand or aUSDC on VOI via AlgoVoi.

Full integration guide: [yapily.md](../yapily.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `yapily_algovoi.py` | Adapter — verifies Yapily payment webhooks (X-Yapily-Signature) and creates AlgoVoi settlement links |
| `test_yapily.py` | Integration test suite |

---

## Quick start

```python
from yapily_algovoi import YapilyAlgoVoi

adapter = YapilyAlgoVoi(
    application_id="YOUR_YAPILY_APPLICATION_ID",
    application_secret="YOUR_YAPILY_APPLICATION_SECRET",
    webhook_secret="YOUR_WEBHOOK_SECRET",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
