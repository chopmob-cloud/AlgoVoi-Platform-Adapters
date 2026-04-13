"""
MPP + AP2 Smoke Test
====================
Tests the complete payment acceptance path for both protocols
using real on-chain verification (MPP) and local ed25519 verification (AP2).

MPP: reuses the 0.01 USDC TX already confirmed on Algorand mainnet
     (DF2PQUPY6TVX3DD7GQSY7LEZNVGOEYC24NBIIHLKYM5RIA3UN4AQ)

AP2: generates a fresh ed25519 key pair, signs a mandate, verifies locally.
     No on-chain payment required for AP2 -- verification is purely cryptographic.
"""

import base64
import json
import os
import sys
import socket
import threading
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "mpp-adapter"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ap2-adapter"))

from mpp import MppGate, MppResult
from ap2 import Ap2Gate, Ap2Result

PASS = FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f" -- {detail}" if detail else ""))

def banner(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")

# ── Known on-chain TX from smoke test ───────────────────────────────────────
PAYOUT_ADDRESS = "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ"
PAYER_ADDRESS  = "GHSRL2SAY247LWE7HLUGEYKHC5JMDOGWECW5TMN6PTP73FT2Z5AWMADMWI"
TX_ID          = "DF2PQUPY6TVX3DD7GQSY7LEZNVGOEYC24NBIIHLKYM5RIA3UN4AQ"

# ── MPP Smoke Test ───────────────────────────────────────────────────────────

def smoke_mpp():
    banner("MPP Smoke Test — on-chain Algorand verification")

    gate = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test",
        tenant_id="test",
        resource_id="smoke-test",
        amount_microunits=10000,          # 0.01 USDC
        networks=["algorand_mainnet"],
        realm="Smoke Test",
        payout_address=PAYOUT_ADDRESS,
    )

    print(f"\n  TX:     {TX_ID}")
    print(f"  Payer:  {PAYER_ADDRESS}")
    print(f"  PayTo:  {PAYOUT_ADDRESS}")
    print(f"  Amount: 10000 microunits (0.01 USDC)\n")

    # Step 1: No credential -> 402 challenge
    print("[Step 1] No credential -> expect 402")
    result = gate.check({})
    check("requires_payment=True", result.requires_payment)
    check("challenge present", result.challenge is not None)

    # Step 2: Build real credential from the confirmed TX
    print("\n[Step 2] Submit real TX credential -> expect 200")
    proof = base64.b64encode(json.dumps({
        "network": "algorand-mainnet",
        "payload": {
            "txId": TX_ID,
            "payer": PAYER_ADDRESS,
        },
    }).encode()).decode()

    result2 = gate.check({"Authorization": f"Payment {proof}"})
    check("requires_payment=False (payment accepted)", not result2.requires_payment,
          f"error={result2.error}")
    if result2.receipt:
        check("receipt.tx_id matches", result2.receipt.tx_id == TX_ID)
        check("receipt.payer matches", result2.receipt.payer == PAYER_ADDRESS)
        check("receipt.amount >= 10000", result2.receipt.amount >= 10000,
              f"got {result2.receipt.amount}")
        print(f"\n  Receipt:")
        print(f"    tx_id:   {result2.receipt.tx_id}")
        print(f"    payer:   {result2.receipt.payer}")
        print(f"    amount:  {result2.receipt.amount} microunits")
        print(f"    network: {result2.receipt.network}")

    # Step 3: Wrong payout address -> rejected
    print("\n[Step 3] Wrong payout address -> expect rejection")
    gate_wrong = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test", tenant_id="test",
        resource_id="smoke-test",
        amount_microunits=10000,
        networks=["algorand_mainnet"],
        realm="Smoke Test",
        payout_address="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    )
    result3 = gate_wrong.check({"Authorization": f"Payment {proof}"})
    check("wrong payout -> requires_payment=True", result3.requires_payment,
          f"error={result3.error}")

    # Step 4: Amount too high -> rejected
    print("\n[Step 4] Required amount higher than TX amount -> rejected")
    gate_high = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test", tenant_id="test",
        resource_id="smoke-test",
        amount_microunits=999_000_000,   # 999 USDC -- TX only had 0.01
        networks=["algorand_mainnet"],
        realm="Smoke Test",
        payout_address=PAYOUT_ADDRESS,
    )
    result4 = gate_high.check({"Authorization": f"Payment {proof}"})
    check("underpaid -> requires_payment=True", result4.requires_payment,
          f"error={result4.error}")


# ── AP2 Smoke Test ───────────────────────────────────────────────────────────

def smoke_ap2():
    banner("AP2 Smoke Test -- local ed25519 signature verification")

    # Generate a fresh ed25519 key pair using algosdk / nacl
    from algosdk import account as _acct
    from nacl.signing import SigningKey

    signing_key = SigningKey.generate()
    verify_key  = signing_key.verify_key
    pubkey_bytes = bytes(verify_key)

    # Build an Algorand address from the public key
    from algosdk import encoding as _enc
    agent_address = _enc.encode_address(pubkey_bytes)

    print(f"\n  Agent address: {agent_address}")
    print(f"  (freshly generated ed25519 key pair -- no funds needed)\n")

    gate = Ap2Gate(
        merchant_id="smoke-merchant",
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test",
        tenant_id="test",
        amount_usd=0.01,
        currency="USD",
        networks=["algorand_mainnet"],
        items=[{"label": "Smoke test", "amount": "0.01"}],
    )

    # Step 1: No mandate -> 402
    print("[Step 1] No mandate -> expect 402")
    result = gate.check({})
    check("requires_payment=True", result.requires_payment)
    check("payment_request present", result.payment_request is not None)

    # Step 2: Build and sign a valid mandate
    print("\n[Step 2] Sign mandate with ed25519 key -> expect acceptance")
    mandate_fields = {
        "merchant_id":   "smoke-merchant",
        "payer_address": agent_address,
        "network":       "algorand-mainnet",
        "amount":        {"value": "0.01", "currency": "USD"},
    }
    # Sign canonical JSON (keys sorted, no spaces) -- same format as _verify_mandate
    message = json.dumps(mandate_fields, sort_keys=True, separators=(",", ":")).encode()
    signed   = signing_key.sign(message)
    signature_b64 = base64.b64encode(signed.signature).decode()

    mandate = {**mandate_fields, "signature": signature_b64}
    mandate_header = base64.b64encode(json.dumps(mandate).encode()).decode()

    result2 = gate.check({"X-AP2-Mandate": mandate_header})
    check("requires_payment=False (mandate accepted)", not result2.requires_payment,
          f"error={result2.error}")
    if result2.mandate:
        check("mandate.payer_address matches", result2.mandate.payer_address == agent_address)
        check("mandate.merchant_id matches", result2.mandate.merchant_id == "smoke-merchant")
        print(f"\n  Mandate:")
        print(f"    payer:    {result2.mandate.payer_address}")
        print(f"    merchant: {result2.mandate.merchant_id}")
        print(f"    network:  {result2.mandate.network}")
        print(f"    amount:   {result2.mandate.amount} {result2.mandate.currency}")

    # Step 3: Tampered mandate -> signature mismatch -> rejected
    print("\n[Step 3] Tampered mandate (wrong merchant) -> expect rejection")
    tampered = {**mandate_fields, "merchant_id": "evil-merchant", "signature": signature_b64}
    tampered_header = base64.b64encode(json.dumps(tampered).encode()).decode()
    result3 = gate.check({"X-AP2-Mandate": tampered_header})
    check("tampered mandate -> requires_payment=True", result3.requires_payment,
          f"error={result3.error}")

    # Step 4: Wrong merchant_id in gate -> rejected before sig check
    print("\n[Step 4] Right signature, wrong gate merchant -> rejected")
    gate_other = Ap2Gate(
        merchant_id="other-merchant",
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test", tenant_id="test",
        amount_usd=0.01, currency="USD",
        networks=["algorand_mainnet"],
    )
    result4 = gate_other.check({"X-AP2-Mandate": mandate_header})
    check("merchant mismatch -> requires_payment=True", result4.requires_payment)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    smoke_mpp()
    smoke_ap2()

    print(f"\n{'=' * 60}")
    print(f"  Smoke test results: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 60}\n")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
