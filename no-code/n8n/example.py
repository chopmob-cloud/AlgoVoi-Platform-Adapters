"""
AlgoVoi n8n Adapter — Example Usage
=====================================
"""
import os
from n8n_algovoi import AlgoVoiN8n

# ── Initialise ────────────────────────────────────────────────────────────────
handler = AlgoVoiN8n(
    algovoi_key=    os.environ["ALGOVOI_API_KEY"],
    tenant_id=      os.environ["ALGOVOI_TENANT_ID"],
    payout_algorand=os.environ.get("ALGOVOI_PAYOUT_ALGORAND", ""),
    payout_hedera=  os.environ.get("ALGOVOI_PAYOUT_HEDERA", ""),
    webhook_secret= os.environ.get("ALGOVOI_WEBHOOK_SECRET", ""),
)

# ── 1. Create a payment link ──────────────────────────────────────────────────
item = handler.execute_create_payment_link({
    "amount":   2.50,
    "currency": "USD",
    "label":    "Agent service call",
    "network":  "hedera_mainnet",
})
if item["json"].get("success"):
    print(f"Checkout URL: {item['json']['checkout_url']}")
    print(f"Token:        {item['json']['token']}")
else:
    print(f"Error: {item['json']['error']}")

# ── 2. Verify a payment ───────────────────────────────────────────────────────
item = handler.execute_verify_payment({"token": "tok_abc"})
print(f"Paid: {item['json'].get('paid')}  Status: {item['json'].get('status')}")

# ── 3. List networks ──────────────────────────────────────────────────────────
item = handler.execute_list_networks()
print(f"Networks: {item['json']['count']}")

# ── 4. Generate MPP challenge ─────────────────────────────────────────────────
item = handler.execute_generate_mpp_challenge({
    "resource_id":      "/api/premium",
    "amount_microunits": 1_000_000,
    "network":          "hedera_mainnet",
})
print(f"Header: {item['json'].get('header_name')} — {item['json'].get('header_value','')[:60]}...")

# ── 5. Generate x402 challenge ────────────────────────────────────────────────
item = handler.execute_generate_x402_challenge({
    "resource_id":      "/api/data",
    "amount_microunits": 500_000,
    "network":          "algorand_mainnet",
})
print(f"x402 mandate_id: {item['json'].get('mandate_id')}")

# ── 6. Generate AP2 mandate ───────────────────────────────────────────────────
item = handler.execute_generate_ap2_mandate({
    "resource_id":      "/service/invoke",
    "amount_microunits": 2_000_000,
    "network":          "voi_mainnet",
})
print(f"AP2 mandate_id: {item['json'].get('mandate_id')}")

# ── 7. Verify webhook signature ───────────────────────────────────────────────
import json, hmac as _hmac, hashlib
raw    = json.dumps({"event_type": "payment.received", "token": "tok_abc", "status": "paid"})
secret = os.environ.get("ALGOVOI_WEBHOOK_SECRET", "secret")
sig    = _hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
item   = handler.execute_verify_webhook_signature({"raw_body": raw, "signature": sig})
print(f"Webhook valid: {item['json'].get('valid')}")
