# Tokopedia — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI for Tokopedia orders via webhook-driven order detection and AlgoVoi hosted checkout links.

Full integration guide: [tokopedia.md](../tokopedia.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `tokopedia_algovoi.py` | Adapter — receives Tokopedia order webhooks and creates AlgoVoi payment links |
| `test_tokopedia.py` | Integration test suite |

---

## Quick start

```python
from tokopedia_algovoi import TokopediaAlgoVoi

adapter = TokopediaAlgoVoi(
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    fs_id=1234567,
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
