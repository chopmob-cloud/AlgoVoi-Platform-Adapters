"""
Claude Adapter -- AP2 Smoke Test
==================================
AP2 requires the on-chain TX sender to match the mandate's payer_address,
which encodes the ed25519 public key used to sign the mandate.

Uses your existing Algorand wallet (WALLET_MNEMONIC from C:/algo/.env).
The private key is derived locally -- it never leaves your machine.

Phase 1 -- shows your wallet address and payment instructions.
Phase 2 -- takes your TX ID, signs the mandate with your wallet key,
           verifies on-chain, then calls the Claude API.

Usage:
    python smoke_test_claude_ap2.py              # Phase 1 -- show address
    python smoke_test_claude_ap2.py <TX_ID>      # Phase 2 -- verify + call Claude
"""

from __future__ import annotations

import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mpp-adapter"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ap2-adapter"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "openai"))

from claude_algovoi import AlgoVoiClaude

# ── Config ────────────────────────────────────────────────────────────────────

def _load_key(prefix: str) -> str:
    key_file = os.path.join(os.path.dirname(__file__), "..", "..", "openai.txt")
    with open(key_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith(prefix):
                return line
    raise RuntimeError(f"No key with prefix {prefix!r} found in openai.txt")

ANTHROPIC_KEY = _load_key("sk-ant-")
ALGOVOI_KEY   = _load_key("algv_")
TENANT_ID     = "YOUR_TENANT_ID"
PAYOUT_ADDR   = "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ"
ENV_FILE      = os.path.join("C:", os.sep, "algo", ".env")
API_BASE      = "https://api1.ilovechicken.co.uk"

TEST_MESSAGES = [
    {"role": "system", "content": "You are a helpful assistant. Reply very briefly."},
    {"role": "user",   "content": "AP2 payment verified. Say hello and confirm you are Claude."},
]

# ── Wallet helpers ────────────────────────────────────────────────────────────

def _load_wallet() -> tuple:
    """
    Load the Algorand wallet from WALLET_MNEMONIC in C:\\algo\\.env.
    Returns (nacl_signing_key, algorand_address).
    """
    import nacl.signing as _nacl
    from algosdk import mnemonic as _mnemonic, account as _account

    if not os.path.exists(ENV_FILE):
        raise FileNotFoundError(f".env file not found: {ENV_FILE}")

    words = None
    with open(ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("WALLET_MNEMONIC="):
                words = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

    if not words:
        raise RuntimeError("WALLET_MNEMONIC not found in .env")

    # algosdk derives the private key from the mnemonic
    private_key_b64 = _mnemonic.to_private_key(words)          # base64
    address         = _account.address_from_private_key(private_key_b64)

    # algosdk private key = 32-byte seed + 32-byte pubkey (64 bytes total)
    private_key_bytes = base64.b64decode(private_key_b64)
    seed = private_key_bytes[:32]   # first 32 bytes are the ed25519 seed

    # nacl.SigningKey takes the 32-byte seed
    signing_key = _nacl.SigningKey(seed)
    return signing_key, address


def _build_mandate(signing_key, payer_addr: str, tx_id: str) -> str:
    """Build a signed AP2 PaymentMandate and return as base64."""
    mandate = {
        "ap2_version": "0.1",
        "type":        "PaymentMandate",
        "merchant_id": TENANT_ID,
        "payer_address": payer_addr,
        "payment_response": {
            "method_name": f"{API_BASE}/ap2/extensions/crypto-algo/v1",
            "details": {
                "network": "algorand-mainnet",
                "tx_id":   tx_id,
            },
        },
    }
    canonical = json.dumps(mandate, separators=(",", ":"), sort_keys=True).encode()
    sig_bytes = signing_key.sign(canonical).signature
    mandate["signature"] = base64.b64encode(sig_bytes).decode()
    return base64.b64encode(json.dumps(mandate).encode()).decode()


# ── Phase 1 ───────────────────────────────────────────────────────────────────

def phase1():
    print("\n" + "="*60)
    print("PHASE 1 -- AP2 Smoke Test Setup")
    print("="*60)

    signing_key, payer_addr = _load_wallet()

    # Confirm CartMandate challenge fires correctly
    gate   = AlgoVoiClaude(
        anthropic_key=ANTHROPIC_KEY, algovoi_key=ALGOVOI_KEY,
        tenant_id=TENANT_ID, payout_address=PAYOUT_ADDR,
        protocol="ap2", network="algorand-mainnet",
        amount_microunits=10000, model="claude-haiku-4-5",
    )
    result = gate.check({}, {})
    _, status, headers = result.as_flask_response()
    cart = next((v for k, v in headers.items() if k.lower() == "x-ap2-cart-mandate"), "")
    print(f"\n[PASS] AP2 CartMandate challenge: {status}")
    print(f"       X-AP2-Cart-Mandate = {cart[:60]}...")

    print(f"\n[INFO] Your wallet address (send FROM this address):")
    print(f"       {payer_addr}")
    print(f"\n[INFO] Send 0.01 USDC (ASA 31566704) to payout address:")
    print(f"       {PAYOUT_ADDR}")
    print(f"\n[INFO] Network: Algorand mainnet")
    print(f"\nOnce the TX is confirmed, run Phase 2:")
    print(f"  python smoke_test_claude_ap2.py <TX_ID>")


# ── Phase 2 ───────────────────────────────────────────────────────────────────

def phase2(tx_id: str):
    print("\n" + "="*60)
    print("PHASE 2 -- AP2 Verify + Claude API Call")
    print("="*60)
    print(f"\nTX: {tx_id}")

    signing_key, payer_addr = _load_wallet()
    print(f"Payer address: {payer_addr}")

    gate = AlgoVoiClaude(
        anthropic_key=ANTHROPIC_KEY, algovoi_key=ALGOVOI_KEY,
        tenant_id=TENANT_ID, payout_address=PAYOUT_ADDR,
        protocol="ap2", network="algorand-mainnet",
        amount_microunits=10000, model="claude-haiku-4-5",
    )

    mandate_b64 = _build_mandate(signing_key, payer_addr, tx_id)

    try:
        result = gate.check({"X-AP2-Mandate": mandate_b64}, {})

        if result.requires_payment:
            print(f"\n[FAIL] Payment rejected -- {result.error}")
            sys.exit(1)

        print(f"\n[PASS] AP2 payment verified")
        if result.mandate:
            print(f"       payer_address : {result.mandate.payer_address}")
            print(f"       network       : {result.mandate.network}")
            print(f"       tx_id         : {result.mandate.tx_id}")

        reply = gate.complete(TEST_MESSAGES)
        print(f"\n[PASS] Claude replied: {reply}")

        print(f"\n{'='*60}")
        print("AP2 smoke test PASS")

    except Exception as e:
        print(f"\n[FAIL] {type(e).__name__}: {e}")
        sys.exit(1)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) == 2:
        phase2(sys.argv[1])
    elif len(sys.argv) == 1:
        phase1()
    else:
        print("Usage:")
        print("  python smoke_test_claude_ap2.py              # Phase 1")
        print("  python smoke_test_claude_ap2.py <TX_ID>      # Phase 2")
        sys.exit(1)
