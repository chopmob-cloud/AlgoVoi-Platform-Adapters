# WhatsApp Business — AlgoVoi Payment Adapter

Enables your WhatsApp Business bot to accept USDC on Algorand and aUSDC on VOI by replying to customer order messages with AlgoVoi hosted checkout payment buttons.

Full integration guide: [whatsapp.md](../whatsapp.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `whatsapp_algovoi.py` | Adapter — handles WhatsApp Cloud API webhooks and creates AlgoVoi payment links |
| `test_whatsapp.py` | Integration test suite |

---

## Quick start

```python
from whatsapp_algovoi import WhatsAppAlgoVoi

adapter = WhatsAppAlgoVoi(
    phone_number_id="YOUR_PHONE_NUMBER_ID",
    access_token="YOUR_META_ACCESS_TOKEN",
    webhook_verify_token="YOUR_VERIFY_TOKEN",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
