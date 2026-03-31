# Telegram Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment via your Telegram bot using AlgoVoi.

> **Social Commerce integration.** Telegram's Bot API allows bots to send payment links and receive confirmations. AlgoVoi integrates via the **checkout link pattern** — your bot sends an AlgoVoi hosted checkout URL to the customer, who pays on-chain. No Telegram Payments provider registration is required.

---

## Important: Telegram payment model

Telegram has a native Payments API (via BotFather-registered providers such as Stripe), but **AlgoVoi is not a Telegram payment provider**. Instead, AlgoVoi operates in bypass mode:

- Your bot sends a message containing an AlgoVoi hosted checkout URL
- The customer taps the link, pays on-chain in USDC or aUSDC
- AlgoVoi notifies your backend via webhook on payment confirmation
- Your bot sends a confirmation message to the customer

This requires no Telegram Payments API registration and works in any Telegram chat, group, or channel.

---

## How it works

```
Customer sends /pay command to your Telegram bot
            ↓
Bot calls AlgoVoi to create a checkout link for the order
            ↓
Bot sends checkout URL as an inline button to the customer
            ↓
Customer taps link → pays on-chain (USDC or aUSDC)
            ↓
AlgoVoi verifies transaction on-chain
            ↓
AlgoVoi fires webhook → your bot sends confirmation message
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Telegram bot created via [@BotFather](https://t.me/BotFather)
- Your bot token from BotFather
- A publicly accessible HTTPS endpoint for receiving Telegram updates (or use long polling during development)

---

## Step 1 — Configure your network

### USDC on Algorand mainnet

```http
POST /internal/tenants/{tenant_id}/network-configs
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "network": "algorand_mainnet",
  "payout_address": "<your-algorand-address>",
  "preferred_asset_id": "31566704",
  "preferred_asset_decimals": 6
}
```

### aUSDC on VOI mainnet

```http
POST /internal/tenants/{tenant_id}/network-configs
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "network": "voi_mainnet",
  "payout_address": "<your-voi-address>",
  "preferred_asset_id": "311051",
  "preferred_asset_decimals": 6
}
```

---

## Step 2 — Create your Telegram bot

1. Open [@BotFather](https://t.me/BotFather) in Telegram
2. Send `/newbot` and follow the prompts
3. Copy the **bot token** (format: `123456789:ABCdef...`)
4. Optionally register commands with `/setcommands`:
   ```
   pay - Request a payment link
   status - Check payment status
   ```

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/telegram
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "bot_token": "<telegram-bot-token>"
  },
  "shop_identifier": "<your-bot-username>",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url` for AlgoVoi payment confirmations.

---

## Step 4 — Register your bot webhook with Telegram

Set your bot's webhook so Telegram delivers updates (messages, commands) to your backend:

```http
POST https://api.telegram.org/bot<BOT_TOKEN>/setWebhook
Content-Type: application/json

{
  "url": "https://your-backend.com/telegram/updates",
  "secret_token": "<a-secret-you-choose>"
}
```

Telegram will deliver all bot updates as HTTP POST requests to your URL with a `X-Telegram-Bot-Api-Secret-Token` header matching your `secret_token`.

---

## Step 5 — Handle /pay and send checkout links

When your bot receives a `/pay` command, create an AlgoVoi checkout link and send it as an inline button:

```python
import httpx

def handle_pay_command(chat_id: str, amount_usd: float, order_ref: str):
    # Create AlgoVoi checkout link
    checkout = httpx.post(
        f"https://api.algovoi.com/checkout/{TENANT_ID}",
        headers={"Authorization": f"Bearer {TENANT_API_KEY}"},
        json={
            "amount_fiat": amount_usd,
            "currency": "USD",
            "reference": order_ref,
            "network": "algorand_mainnet"
        }
    ).json()

    # Send to Telegram customer as inline button
    httpx.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": f"Pay ${amount_usd:.2f} in USDC on Algorand:",
            "reply_markup": {
                "inline_keyboard": [[
                    {"text": "Pay with USDC", "url": checkout["checkout_url"]}
                ]]
            }
        }
    )
```

---

## Payment confirmation flow

When AlgoVoi confirms an on-chain payment it fires your `webhook_url`. Use this to send a confirmation message back to the customer:

```python
@app.post("/algovoi/webhook")
async def algovoi_webhook(payload: dict):
    order_ref = payload["reference"]
    tx_id = payload["tx_id"]
    chat_id = lookup_chat_id(order_ref)

    await bot.send_message(
        chat_id=chat_id,
        text=f"Payment confirmed! TX: {tx_id[:16]}..."
    )
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| Bot not receiving updates | `setWebhook` URL not HTTPS or not publicly reachable |
| `X-Telegram-Bot-Api-Secret-Token` mismatch | `secret_token` in setWebhook doesn't match your handler |
| Checkout link not generating | AlgoVoi tenant credentials incorrect or network config missing |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Customer not receiving confirmation | `chat_id` lookup failed — ensure order reference maps to chat ID |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | aUSDC (ARC200 app ID 311051) | |
| `algorand_testnet` | Test USDC | For development and testing |
| `voi_testnet` | Test aUSDC | For development and testing |
