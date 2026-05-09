"""
AlgoVoi Tier 2 — Python merchant-side example.

This is a runnable reference showing the full Tier 2 lifecycle from
the merchant's perspective. The wallet-side flow (where the customer
actually signs the on-chain authorisation) is documented per chain in
../algorand/, ../voi/, ../evm/, ../solana/, ../hedera/, ../stellar/.

This example uses the native-python adapter at
../../native-python/algovoi.py (v1.2.0+) — the chain-agnostic merchant
HTTP wrapper. Zero pip dependencies beyond the adapter itself.

Requires:
    cp ../../native-python/algovoi.py .         # or add to PYTHONPATH

Run:
    python python.py

This is dry-running against a placeholder API key — replace
api_key + tenant_id + webhook_secret with real values, plus an
existing subscription_id, to actually exercise the flow.
"""
from __future__ import annotations

# Adjust import path as needed if you copy this file outside Recurr/:
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "native-python"))

from algovoi import AlgoVoi, RECURRING_NETWORKS, RECURRING_EVENT_TYPES

# ---------------------------------------------------------------------------
# Configure
# ---------------------------------------------------------------------------

av = AlgoVoi(
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_REPLACE_ME",
    tenant_id="REPLACE_ME_UUID",
    webhook_secret="whsec_REPLACE_ME",
)


# ---------------------------------------------------------------------------
# Step 1 — Create a Tier 2 standing authority for an existing subscription
#
# Pre-requisite: a Tier 1 subscription already exists. Create one via
# POST /v1/subscriptions or via the dashboard. Plug its id in below.
# ---------------------------------------------------------------------------

def example_create_authority(subscription_id: str, customer_wallet: str, chain: str):
    """Example: $10/month subscription, 12-month standing authority,
    on the customer's chosen chain."""
    if chain not in RECURRING_NETWORKS:
        raise ValueError(f"Unsupported chain: {chain}")

    # Cap amounts depend on chain decimals.
    # Most chains: 6 decimals. Stellar: 7 decimals.
    if chain.startswith("stellar_"):
        per_cycle = 10 * 10**7   # 10 USDC at 7 decimals
        total_cap = 120 * 10**7  # 12 months × 10
    else:
        per_cycle = 10 * 10**6   # 10 USDC at 6 decimals
        total_cap = 120 * 10**6

    response = av.create_recurring_authority(
        subscription_id=subscription_id,
        chain=chain,
        customer_wallet_address=customer_wallet,
        cap_amount_minor=total_cap,
        cap_period_seconds=365 * 86400,
        per_cycle_amount_minor=per_cycle,
        asset="USDC",
        metadata={"plan": "monthly_pro", "customer_email": "alice@example.com"},
    )

    if response is None:
        raise RuntimeError("Authority creation failed (check logs / API key)")

    authority_id = response["authority"]["id"]
    print(f"[create] authority_id = {authority_id}")
    print(f"[create] status       = {response['authority']['status']}")
    print(f"[create] template ver = {response['customer_signing_payload']['version']}")

    # Hand `response['customer_signing_payload']` to your frontend wallet
    # UI. The per-chain folders in this directory have wallet-side
    # reference implementations.
    return response


# ---------------------------------------------------------------------------
# Step 2 — After the customer's wallet signs and the on-chain auth lands,
#          confirm the authority
#
# Most tenants don't need to call this — the AlgoVoi widget does it
# automatically. Use this when self-hosting the wallet UI.
# ---------------------------------------------------------------------------

def example_confirm_authority(authority_id: str, on_chain_handle: str):
    """`on_chain_handle` format depends on the chain:
        Algorand / VOI : "app:<application_id>"
        EVM            : "0x<tx_hash>"
        Solana         : "<base58 tx signature>"
        Hedera         : "<account_id>@<seconds>.<nanos>" (Hedera tx id)
        Stellar        : "<G-address of customer>" (56-char base32 pubkey)

    Note: for Stellar, the signed SorobanAuthorizationEntry XDR is handled
    internally by the AlgoVoi gateway and does not need to be passed here.
    If using the hosted auth page (recurr.algovoi.co.uk) the gateway confirms
    automatically — tenants only call this when self-hosting the wallet UI.
    """
    confirmed = av.confirm_authority(
        authority_id=authority_id,
        on_chain_address=on_chain_handle,
    )
    if confirmed is None:
        raise RuntimeError("Confirmation failed")
    print(f"[confirm] status = {confirmed['status']}  (should be 'active')")
    return confirmed


# ---------------------------------------------------------------------------
# Step 3 — Read state any time
# ---------------------------------------------------------------------------

def example_inspect(authority_id: str):
    auth = av.get_authority(authority_id)
    if auth is None:
        print("[inspect] not found")
        return
    print(f"[inspect] status              = {auth['status']}")
    print(f"[inspect] cycles_pulled       = {auth.get('cycles_pulled', 0)}")
    print(f"[inspect] cycles_failed       = {auth.get('cycles_failed', 0)}")
    print(f"[inspect] cap_remaining_minor = {auth.get('cap_remaining_minor', 0)}")
    if auth.get("last_error"):
        print(f"[inspect] last_error          = {auth['last_error']}")


def example_list_active():
    auths = av.list_authorities(status="active", limit=50)
    if auths is None:
        print("[list] failed")
        return
    print(f"[list] {len(auths)} active authorities")
    for a in auths:
        print(f"    {a['id']}  chain={a['chain']}  cycles={a.get('cycles_pulled', 0)}")


# ---------------------------------------------------------------------------
# Step 4 — Lifecycle controls
# ---------------------------------------------------------------------------

def example_pause(authority_id: str):
    """Off-chain pause — no chain transaction, stops cycle pulls."""
    av.pause_authority(authority_id)


def example_resume(authority_id: str):
    """Off-chain resume."""
    av.resume_authority(authority_id)


def example_revoke(authority_id: str):
    """On-chain revoke — gateway constructs the revocation transaction;
    customer's wallet signs it. Authority transitions to 'revoking'
    until the on-chain landing, then 'revoked'."""
    revoked = av.revoke_authority(authority_id)
    if revoked is None:
        print("[revoke] failed")
        return
    print(f"[revoke] status = {revoked['status']}")


def example_manual_pull(authority_id: str, amount_minor: int):
    """Trigger a one-off catch-up pull. Most pulls fire automatically
    via the cycle reaper — only use this for prorated billing or
    manual catch-ups after dunning."""
    result = av.manual_pull(
        authority_id=authority_id,
        amount_minor=amount_minor,
        note=f"manual catch-up pull",
    )
    if result is None:
        print("[pull] failed (check per-cycle cap)")
        return
    print(f"[pull] accepted; status = {result.get('status')}")


# ---------------------------------------------------------------------------
# Step 5 — Webhook handler
#
# Tier 2 emits these event types alongside Tier 1's payment.* events.
# verify_webhook + is_recurring_event let you fork the handler.
# ---------------------------------------------------------------------------

def example_webhook_handler(raw_body: bytes, signature: str):
    """Handle an incoming AlgoVoi webhook.

    Minimal example — wire this into your framework's POST handler
    (Flask: request.get_data() + request.headers; Django: request.body
    + request.META; FastAPI: await request.body() + request.headers).
    """
    payload = av.verify_webhook(raw_body, signature)
    if payload is None:
        return ("Unauthorized", 401)

    if av.is_recurring_event(payload):
        # Tier 2 events
        event_type = payload.get("event_type", "")
        authority_id = payload.get("authority_id")

        if event_type == "subscription.charged":
            # A cycle pull succeeded. Extend customer access.
            tx_id = payload.get("tx_id")
            print(f"[webhook] charged: authority={authority_id} tx={tx_id}")

        elif event_type == "subscription.payment_failed":
            # A cycle pull failed. Trigger dunning.
            reason = payload.get("failure_reason")
            print(f"[webhook] failed: authority={authority_id} reason={reason}")

        elif event_type == "recurring.authority_revoked":
            # Customer revoked. Cancel the subscription.
            print(f"[webhook] revoked: authority={authority_id}")

        elif event_type == "recurring.authority_expired":
            # Cap window or auth expiry hit. Notify the customer to renew.
            print(f"[webhook] expired: authority={authority_id}")

        # Other events: authority_created, authority_activated,
        # authority_paused, authority_resumed
        else:
            print(f"[webhook] {event_type}: authority={authority_id}")
    else:
        # Tier 1 one-shot events: payment.succeeded, payment.failed, etc.
        order_id = payload.get("order_id")
        print(f"[webhook] one-shot event for order={order_id}")

    return ("ok", 200)


# ---------------------------------------------------------------------------
# Smoke check (no network calls — just verifies the adapter is wired)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Tier 2 chains supported by this adapter:")
    for chain in sorted(RECURRING_NETWORKS):
        print(f"  - {chain}")

    print("\nTier 2 webhook event types:")
    for evt in sorted(RECURRING_EVENT_TYPES):
        print(f"  - {evt}")

    print(
        "\nReady to integrate. Replace the api_key / tenant_id / "
        "webhook_secret at the top of this file with real values, "
        "then call example_create_authority(...)."
    )
