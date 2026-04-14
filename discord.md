# Discord Integration — AlgoVoi Tenant Services

Accept **USDC on Algorand** and **aUSDC on VOI** as payment via your Discord bot using AlgoVoi.

> **Social Commerce integration.** Discord's Bot API and Interactions system allows bots to respond to slash commands with AlgoVoi checkout links. Customers pay on-chain directly from a Discord server.

---

## How it works

```
Customer runs /pay slash command in Discord server
            ↓
Discord sends interaction to your bot's interactions endpoint
            ↓
Bot calls AlgoVoi to create a checkout link for the order
            ↓
Bot responds with checkout URL as a button (ephemeral message)
            ↓
Customer clicks link → pays on-chain (USDC or aUSDC)
            ↓
AlgoVoi verifies transaction on-chain
            ↓
AlgoVoi fires webhook → bot sends follow-up confirmation to customer
```

---

## Prerequisites

- An active AlgoVoi tenant account
- A Discord application created at [discord.com/developers/applications](https://discord.com/developers/applications)
- A bot user added to your application
- A publicly accessible HTTPS interactions endpoint

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
  "preferred_asset_id": "302190",
  "preferred_asset_decimals": 6
}
```

---

## Step 2 — Create a Discord application

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** and give it a name
3. Under **General Information**, copy the **Application ID** and **Public Key**
4. Under **Bot**, click **Add Bot** and copy the **Bot Token**
5. Under **OAuth2 → URL Generator**, select scopes: `bot` and `applications.commands`
6. Use the generated URL to invite the bot to your server

---

## Step 3 — Connect the integration

```http
POST /internal/integrations/{tenant_id}/discord
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {
    "bot_token": "<discord-bot-token>",
    "application_id": "<discord-application-id>",
    "public_key": "<discord-application-public-key>"
  },
  "shop_identifier": "<your-server-id>",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

The response includes a `webhook_secret` and a `webhook_url` for AlgoVoi payment confirmations.

---

## Step 4 — Set up your interactions endpoint

1. In the Discord Developer Portal go to **General Information**
2. Set the **Interactions Endpoint URL** to your HTTPS endpoint (e.g. `https://your-backend.com/discord/interactions`)
3. Discord will send a `PING` interaction to verify — your endpoint must respond with `{"type": 1}`

### Interaction signature verification

Discord signs every interaction with Ed25519. Verify using the `X-Signature-Ed25519` and `X-Signature-Timestamp` headers and your application's **Public Key**:

```python
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

def verify_discord_signature(public_key: str, signature: str, timestamp: str, body: bytes) -> bool:
    try:
        vk = VerifyKey(bytes.fromhex(public_key))
        vk.verify(timestamp.encode() + body, bytes.fromhex(signature))
        return True
    except BadSignatureError:
        return False
```

Discord will reject your endpoint if it fails signature verification.

---

## Step 5 — Register slash commands

Register a `/pay` slash command globally:

```http
POST https://discord.com/api/v10/applications/{application_id}/commands
Authorization: Bot <bot_token>
Content-Type: application/json

{
  "name": "pay",
  "description": "Generate a USDC payment link",
  "options": [
    {
      "name": "amount",
      "description": "Amount in USD",
      "type": 10,
      "required": true
    },
    {
      "name": "reference",
      "description": "Order reference",
      "type": 3,
      "required": true
    }
  ]
}
```

---

## Step 6 — Handle interactions and send checkout links

When Discord sends a slash command interaction, respond with an AlgoVoi checkout button:

```python
import httpx

@app.post("/discord/interactions")
async def handle_interaction(request: Request):
    body = await request.body()
    sig = request.headers["X-Signature-Ed25519"]
    ts = request.headers["X-Signature-Timestamp"]

    if not verify_discord_signature(PUBLIC_KEY, sig, ts, body):
        return Response(status_code=401)

    payload = await request.json()

    # Respond to PING
    if payload["type"] == 1:
        return {"type": 1}

    # Handle /pay command
    if payload["type"] == 2 and payload["data"]["name"] == "pay":
        amount = payload["data"]["options"][0]["value"]
        reference = payload["data"]["options"][1]["value"]
        user_id = payload["member"]["user"]["id"]

        # Create AlgoVoi checkout link
        checkout = httpx.post(
            f"https://api.algovoi.com/checkout/{TENANT_ID}",
            headers={"Authorization": f"Bearer {TENANT_API_KEY}"},
            json={"amount_fiat": amount, "currency": "USD",
                  "reference": reference, "network": "algorand_mainnet"}
        ).json()

        # Respond with ephemeral checkout button (only visible to user)
        return {
            "type": 4,
            "data": {
                "content": f"Pay ${amount} in USDC on Algorand:",
                "flags": 64,  # ephemeral
                "components": [{
                    "type": 1,
                    "components": [{
                        "type": 2,
                        "style": 5,
                        "label": "Pay with USDC",
                        "url": checkout["checkout_url"]
                    }]
                }]
            }
        }
```

---

## Payment confirmation flow

When AlgoVoi confirms an on-chain payment it fires your `webhook_url`. Use the Discord webhook to follow up with the customer:

```python
@app.post("/algovoi/webhook")
async def algovoi_webhook(payload: dict):
    reference = payload["reference"]
    tx_id = payload["tx_id"]
    user_id = lookup_user_id(reference)

    # Send DM confirmation to customer
    channel = httpx.post(
        "https://discord.com/api/v10/users/@me/channels",
        headers={"Authorization": f"Bot {BOT_TOKEN}"},
        json={"recipient_id": user_id}
    ).json()

    httpx.post(
        f"https://discord.com/api/v10/channels/{channel['id']}/messages",
        headers={"Authorization": f"Bot {BOT_TOKEN}"},
        json={"content": f"Payment confirmed! TX: `{tx_id[:16]}...`"}
    )
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| Discord rejects interactions endpoint | Signature verification failing — check `public_key` matches Developer Portal |
| Slash command not appearing | Command not registered or bot not in server with `applications.commands` scope |
| HTTP 422 "No network config" | Network config missing for `preferred_network` |
| Checkout link not generating | AlgoVoi tenant credentials incorrect |
| Bot cannot DM customer | Customer has DMs from server members disabled |

---

---

## Live test status

Confirmed end-to-end on **2026-04-14** against `api1.ilovechicken.co.uk`:

| Test | Network | Result |
|------|---------|--------|
| Webhook → checkout link | `algorand_mainnet` (USDC (ASA 31566704)) | Skip |
| Webhook → checkout link | `voi_mainnet` (WAD (ARC200 app ID 47138068)) | Skip |
| Webhook → checkout link | `hedera_mainnet` (USDC (token 0.0.456858)) | Skip |
| Webhook → checkout link | `stellar_mainnet` (USDC (Circle)) | Skip |

Cannot auto-test: Ed25519 — requires real Discord application keypair.

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Requires ASA opt-in on payout wallet |
| `voi_mainnet` | WAD (ARC200 app ID 47138068) |  |
| `algorand_testnet` | Test USDC | For development and testing |
| `voi_testnet` | Test aUSDC | For development and testing |
