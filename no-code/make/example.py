"""
AlgoVoi Make (Integromat) Adapter — Example Usage
==================================================
"""
import os
from make_algovoi import AlgoVoiMake

# ── Initialise ────────────────────────────────────────────────────────────────
handler = AlgoVoiMake(
    algovoi_key=    os.environ["ALGOVOI_API_KEY"],
    tenant_id=      os.environ["ALGOVOI_TENANT_ID"],
    payout_algorand=os.environ.get("ALGOVOI_PAYOUT_ALGORAND", ""),
    payout_stellar= os.environ.get("ALGOVOI_PAYOUT_STELLAR", ""),
    webhook_secret= os.environ.get("ALGOVOI_WEBHOOK_SECRET", ""),
)

# ── 1. Create a payment link (Make Module) ────────────────────────────────────
bundle = handler.module_create_payment_link({
    "amount":   10.00,
    "currency": "USD",
    "label":    "API access — 30 days",
    "network":  "stellar_mainnet",
})
if bundle.get("data"):
    print(f"Checkout URL: {bundle['data']['checkout_url']}")
    print(f"Token:        {bundle['data']['token']}")
else:
    print(f"Error: {bundle['error']['message']}")

# ── 2. Verify a payment ───────────────────────────────────────────────────────
bundle = handler.module_verify_payment({"token": "tok_xyz"})
print(f"Paid: {bundle.get('data', {}).get('paid')}")

# ── 3. List networks ──────────────────────────────────────────────────────────
bundle = handler.module_list_networks()
print(f"Networks: {bundle['data']['count']}")

# ── 4. Generate x402 challenge ────────────────────────────────────────────────
bundle = handler.module_generate_challenge({
    "protocol":         "x402",
    "resource_id":      "/api/v1/data",
    "amount_microunits": 500_000,
    "network":          "stellar_mainnet",
})
print(f"X-Payment-Required header ready: {'data' in bundle}")

# ── 5. Receive webhook ────────────────────────────────────────────────────────
import json, hmac as _hmac, hashlib
raw  = json.dumps({"event_type": "payment.received", "token": "tok_abc", "status": "paid"})
sig  = _hmac.new(os.environ.get("ALGOVOI_WEBHOOK_SECRET","secret").encode(), raw.encode(), hashlib.sha256).hexdigest()
b    = handler.receive_webhook(raw, sig)
print(f"Webhook valid: {'data' in b}  Event: {b.get('data', {}).get('event_type')}")
