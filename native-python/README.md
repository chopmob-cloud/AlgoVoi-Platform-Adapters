# Native Python — AlgoVoi Payment Adapter

Single-file drop-in for any Python application. Zero pip dependencies beyond
the standard library. Works with Flask, Django, FastAPI, or plain WSGI/ASGI.

Covers both tiers:
- **Tier 1** — one-shot hosted checkout, in-page wallet flow, webhook verification
- **Tier 2** — standing-authority recurring payments across all 7 chains

---

## Files

| File | Description |
|------|-------------|
| `algovoi.py` | Client library — Tier 1 + Tier 2 merchant HTTP wrapper (v1.2.0) |
| `example.py` | Tier 1 usage examples for Flask and Django |
| `security_replay.py` | Webhook replay-protection helper |

---

## Quick start — Tier 1 (one-shot payment)

```python
from algovoi import AlgoVoi

av = AlgoVoi(
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_UUID",
    webhook_secret="whsec_YOUR_WEBHOOK_SECRET",
)

# Create a hosted checkout link and redirect the customer
result = av.hosted_checkout(
    amount=9.99,
    currency="USD",
    label="Order #001",
    network="algorand_mainnet",   # or base_mainnet, solana_mainnet, etc.
    redirect_url="https://yourapp.com/payment-return",
)
# result["checkout_url"] — redirect to this
# result["token"]        — store this to verify on return
```

---

## Quick start — Tier 2 (recurring / standing authority)

Tier 2 requires a Tier 1 subscription to exist first. Create one via the
dashboard or `POST /v1/subscriptions`, then:

```python
# Step 1: create a standing authority for an existing subscription
auth = av.create_recurring_authority(
    subscription_id="YOUR_SUBSCRIPTION_UUID",
    chain="algorand_mainnet",            # any of 14 chain IDs
    customer_wallet_address="ABCD...XYZ",
    cap_amount_minor=120_000_000,        # $120 USDC (6 decimals; Stellar uses 7)
    cap_period_seconds=365 * 86400,      # 1-year cap window
    per_cycle_amount_minor=10_000_000,   # $10 per pull
)

# Step 2: hand customer_signing_payload to your frontend wallet UI
#   → customer signs the on-chain authorisation (see Recurr/<chain>/README.md)
#   → or redirect to auth["authorisation_url"] (hosted page)
payload = auth["customer_signing_payload"]
hosted_url = auth["authorisation_url"]   # recurr.algovoi.co.uk/<token>

# Step 3: after on-chain landing, confirm (hosted page does this automatically)
av.confirm_authority(
    authority_id=auth["authority"]["id"],
    on_chain_address="app:12345678",     # chain-native handle; see per-chain README
)

# Step 4: lifecycle controls
av.pause_authority(authority_id)
av.resume_authority(authority_id)
av.revoke_authority(authority_id)
```

---

## Webhook handler (Tier 1 + Tier 2)

```python
# Flask example — wire this to your POST /webhook route
from flask import request, abort

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = av.verify_webhook(request.get_data(), request.headers.get("X-AlgoVoi-Signature", ""))
    if payload is None:
        abort(401)

    if av.is_recurring_event(payload):
        # Tier 2 events: subscription.charged, subscription.payment_failed,
        #                recurring.authority_revoked, recurring.authority_expired, …
        event = payload["event_type"]
        authority_id = payload.get("authority_id")
        if event == "subscription.charged":
            extend_customer_access(authority_id)
        elif event == "subscription.payment_failed":
            trigger_dunning(authority_id, payload.get("failure_reason"))
        elif event == "recurring.authority_revoked":
            cancel_subscription(authority_id)
    else:
        # Tier 1 one-shot events: payment.succeeded, payment.failed, …
        order_id = payload.get("order_id")
        handle_one_shot(order_id, payload)

    return "ok", 200
```

See [`example.py`](example.py) for full Tier 1 examples, and
[`../Recurr/merchant-examples/python.py`](../Recurr/merchant-examples/python.py)
for the complete Tier 2 lifecycle (inspect, list, manual pull).

---

## Supported chains (Tier 2)

`algorand_mainnet` · `algorand_testnet` · `voi_mainnet` · `voi_testnet` ·
`base_mainnet` · `base_sepolia` · `tempo_mainnet` · `tempo_testnet` ·
`solana_mainnet` · `solana_devnet` · `hedera_mainnet` · `hedera_testnet` ·
`stellar_mainnet` · `stellar_testnet`

---

Licensed under the [Business Source License 1.1](../LICENSE).
