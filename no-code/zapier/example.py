"""
AlgoVoi Zapier Adapter — Example Usage
=======================================
"""
import os
from zapier_algovoi import AlgoVoiZapier

# ── Initialise ────────────────────────────────────────────────────────────────
handler = AlgoVoiZapier(
    algovoi_key=    os.environ["ALGOVOI_API_KEY"],
    tenant_id=      os.environ["ALGOVOI_TENANT_ID"],
    payout_algorand=os.environ.get("ALGOVOI_PAYOUT_ALGORAND", ""),
    payout_voi=     os.environ.get("ALGOVOI_PAYOUT_VOI", ""),
    payout_hedera=  os.environ.get("ALGOVOI_PAYOUT_HEDERA", ""),
    payout_stellar= os.environ.get("ALGOVOI_PAYOUT_STELLAR", ""),
    webhook_secret= os.environ.get("ALGOVOI_WEBHOOK_SECRET", ""),
    zapier_hook_url=os.environ.get("ZAPIER_HOOK_URL", ""),
)

# ── 1. Create a payment link (Zapier Action) ──────────────────────────────────
result = handler.action_create_payment_link({
    "amount":   5.00,
    "currency": "USD",
    "label":    "Premium subscription",
    "network":  "algorand_mainnet",
    "redirect_url": "https://mysite.com/thank-you",
})
if result.success:
    print(f"Checkout URL: {result.data['checkout_url']}")
    print(f"Token:        {result.data['token']}")
else:
    print(f"Error: {result.error}")

# ── 2. Verify a payment (Zapier Action) ───────────────────────────────────────
verify = handler.action_verify_payment({"token": "tok_abc123"})
print(f"Paid: {verify.data.get('paid')}  Status: {verify.data.get('status')}")

# ── 3. List supported networks ────────────────────────────────────────────────
nets = handler.action_list_networks()
print(f"Supported networks: {nets.data['count']}")

# ── 4. Generate MPP challenge ─────────────────────────────────────────────────
mpp = handler.action_generate_challenge({
    "protocol":         "mpp",
    "resource_id":      "/premium-content",
    "amount_microunits": 1_000_000,
    "network":          "algorand_mainnet",
})
print(f"WWW-Authenticate: {mpp.data['header_value'][:80]}...")

# ── 5. Receive and forward webhook ────────────────────────────────────────────
import json, hmac as _hmac, hashlib
raw_body = json.dumps({"event_type": "payment.received", "token": "tok_abc", "status": "paid"})
secret   = os.environ.get("ALGOVOI_WEBHOOK_SECRET", "secret")
sig      = _hmac.new(secret.encode(), raw_body.encode(), hashlib.sha256).hexdigest()

webhook_result = handler.receive_and_forward(raw_body, sig)
print(f"Webhook forwarded: {webhook_result.success}  Event: {webhook_result.data.get('event', {}).get('event_type')}")
