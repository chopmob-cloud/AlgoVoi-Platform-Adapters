# Telegram — AlgoVoi Payment Adapter

Enables your Telegram bot to accept USDC on Algorand and aUSDC on VOI by sending AlgoVoi hosted checkout URLs to customers directly within the Telegram conversation.

Full integration guide: [telegram.md](../telegram.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `telegram_algovoi.py` | Adapter — handles Telegram Bot API webhooks and creates AlgoVoi payment links |
| `test_telegram.py` | Integration test suite |

---

## Quick start

```python
from telegram_algovoi import TelegramAlgoVoi

adapter = TelegramAlgoVoi(
    bot_token="YOUR_TELEGRAM_BOT_TOKEN",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
