# Discord — AlgoVoi Payment Adapter

Enables your Discord bot to accept USDC on Algorand and aUSDC on VOI as payment by responding to slash commands with AlgoVoi hosted checkout links.

Full integration guide: [discord.md](../discord.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `discord_algovoi.py` | Adapter — handles Discord Interactions webhooks and creates AlgoVoi payment links |
| `test_discord.py` | Integration test suite |

---

## Quick start

```python
from discord_algovoi import DiscordAlgoVoi

adapter = DiscordAlgoVoi(
    bot_token="YOUR_DISCORD_BOT_TOKEN",
    application_id="YOUR_APPLICATION_ID",
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
)
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
