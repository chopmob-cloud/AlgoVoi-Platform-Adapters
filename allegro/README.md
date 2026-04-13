# Allegro — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI for Allegro marketplace orders via AlgoVoi, the dominant e-commerce platform in Poland and Central/Eastern Europe.

Full integration guide: [allegro.md](../allegro.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `allegro_algovoi.py` | Adapter — polls the Allegro REST API for new orders and creates AlgoVoi payment links |
| `test_allegro.py` | Integration test suite |

---

## Quick start

```python
from allegro_algovoi import AllegroAlgoVoi

adapter = AllegroAlgoVoi(
    client_id="YOUR_ALLEGRO_CLIENT_ID",
    client_secret="YOUR_ALLEGRO_CLIENT_SECRET",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
adapter.poll_and_notify()
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
