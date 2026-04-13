# Mercado Libre — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI for Mercado Libre orders across Latin America (Argentina, Brazil, Mexico, Colombia, Chile, and other LATAM countries).

Full integration guide: [mercadolibre.md](../mercadolibre.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `mercadolibre_algovoi.py` | Adapter — receives Mercado Libre order webhooks and creates AlgoVoi payment links |
| `test_mercadolibre.py` | Integration test suite |

---

## Quick start

```python
from mercadolibre_algovoi import MercadoLibreAlgoVoi

adapter = MercadoLibreAlgoVoi(
    client_id="YOUR_ML_CLIENT_ID",
    client_secret="YOUR_ML_CLIENT_SECRET",
    access_token="YOUR_ACCESS_TOKEN",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
