"""
AlgoVoi Demo Data Capture
=========================
Drives the real Claude, OpenAI, and Gemini adapters against the live AlgoVoi
API to capture authentic HTTP responses for use in the demo GIFs.

Writes demo_data.json in the same directory.

Usage:
    python capture_demo_data.py

Credentials are read from the same places as the smoke tests:
    ../../openai.txt        — OPENAI_KEY (sk-...), ANTHROPIC_KEY (sk-ant-...), ALGOVOI_KEY (algv_...)
    GEMINI_KEY env var      — Google Gemini API key

TX IDs (previously smoke-tested and verified on-chain):
    Set these via environment variables or edit KNOWN_TXS below.

    DEMO_TX_ALGO      Algorand mainnet TX (for MPP / Claude demo)
    DEMO_TX_ALGO_X402 Algorand mainnet TX (for x402 / OpenAI demo)
    DEMO_TX_ALGO_AP2  Algorand mainnet TX (for AP2 / Gemini demo)

Output:
    demo_data.json  — loaded by make_demo_gif.py when present
"""

from __future__ import annotations

import base64
import json
import os
import sys

_HERE  = os.path.dirname(os.path.abspath(__file__))
_ROOT  = os.path.dirname(os.path.dirname(_HERE))   # platform-adapters/

sys.path.insert(0, os.path.join(_HERE, "..", "claude"))
sys.path.insert(0, os.path.join(_HERE, "..", "openai"))
sys.path.insert(0, os.path.join(_HERE, "..", "gemini"))
sys.path.insert(0, os.path.join(_ROOT, "mpp-adapter"))
sys.path.insert(0, os.path.join(_ROOT, "ap2-adapter"))


# -- Credentials ---------------------------------------------------------------

def _load_key(prefix: str, exclude: str = "") -> str:
    txt = os.path.join(_ROOT, "openai.txt")
    with open(txt, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith(prefix) and (not exclude or not line.startswith(exclude)):
                return line
    raise RuntimeError(f"Key with prefix {prefix!r} not found in openai.txt")


ANTHROPIC_KEY = _load_key("sk-ant-")
OPENAI_KEY    = _load_key("sk-", exclude="sk-ant-")   # OpenAI key, not Anthropic
ALGOVOI_KEY   = _load_key("algv_")
GEMINI_KEY    = os.environ.get("GEMINI_KEY", "")
TENANT_ID     = "YOUR_TENANT_ID"

PAYOUT_ALGO   = "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ"

# -- Known TX IDs (from previous smoke tests) ----------------------------------
#
# These are real verified Algorand mainnet TXs.  Provide your own via env vars
# if you want fresher data.

KNOWN_TXS = {
    "mpp":  os.environ.get("DEMO_TX_ALGO",       ""),   # Claude  MPP  demo
    "x402": os.environ.get("DEMO_TX_ALGO_X402",  ""),   # OpenAI  x402 demo
    "ap2":  os.environ.get("DEMO_TX_ALGO_AP2",   ""),   # Gemini  AP2  demo
}


# -- Helpers -------------------------------------------------------------------

def _mpp_proof(tx_id: str) -> str:
    return base64.b64encode(json.dumps({
        "network": "algorand-mainnet",
        "payload": {"txId": tx_id},
    }).encode()).decode()


def _x402_proof(tx_id: str) -> str:
    return base64.b64encode(json.dumps({
        "payload": {"tx_id": tx_id},
    }).encode()).decode()


def _capture_402_header(result, protocol: str) -> str:
    """Extract the challenge header value from a 402 result."""
    _, _status, headers = result.as_flask_response()
    if protocol == "mpp":
        return next((v for k, v in headers.items()
                     if k.lower() == "www-authenticate"), "")
    elif protocol == "x402":
        return next((v for k, v in headers.items()
                     if k.lower() == "x-payment-required"), "")
    elif protocol == "ap2":
        return next((v for k, v in headers.items()
                     if k.lower() == "x-ap2-cart-mandate"), "")
    return ""


# -- Capture per adapter -------------------------------------------------------

def capture_claude(data: dict) -> None:
    from claude_algovoi import AlgoVoiClaude

    print("\n-- Claude (MPP / Algorand) ------------------------------")
    gate = AlgoVoiClaude(
        anthropic_key=ANTHROPIC_KEY, algovoi_key=ALGOVOI_KEY,
        tenant_id=TENANT_ID, payout_address=PAYOUT_ALGO,
        protocol="mpp", network="algorand-mainnet",
        amount_microunits=10000, model="claude-haiku-4-5",
    )

    # Phase 1 — real 402
    result_402 = gate.check({})
    header_val = _capture_402_header(result_402, "mpp")
    print(f"  402 WWW-Authenticate: {header_val[:80]}...")
    data["claude"]["challenge_header"] = header_val

    # Phase 2 — real 200
    tx_id = KNOWN_TXS["mpp"]
    if not tx_id:
        print("  [SKIP] No DEMO_TX_ALGO set — skipping 200 capture")
        return

    proof  = _mpp_proof(tx_id)
    result = gate.check({"Authorization": f"Payment {proof}"})
    if result.requires_payment:
        print(f"  [FAIL] Payment rejected: {result.error}")
        return

    reply = gate.complete([
        {"role": "system", "content": "You are a helpful assistant. Reply in one sentence."},
        {"role": "user",   "content": "Payment verified. Say hello and confirm you are Claude."},
    ])
    print(f"  200 reply: {reply}")
    data["claude"]["tx_id"]     = tx_id
    data["claude"]["proof"]     = proof[:40] + "..."
    data["claude"]["ai_reply"]  = reply
    if result.receipt:
        data["claude"]["payer"]  = result.receipt.payer
        data["claude"]["amount"] = result.receipt.amount


def capture_openai(data: dict) -> None:
    from openai_algovoi import AlgoVoiOpenAI

    print("\n-- OpenAI (x402 / Algorand) -----------------------------")
    gate = AlgoVoiOpenAI(
        openai_key=OPENAI_KEY, algovoi_key=ALGOVOI_KEY,
        tenant_id=TENANT_ID, payout_address=PAYOUT_ALGO,
        protocol="x402", network="algorand-mainnet",
        amount_microunits=10000, model="gpt-4o-mini",
    )

    # Phase 1 — real 402
    result_402 = gate.check({})
    header_val = _capture_402_header(result_402, "x402")
    print(f"  402 X-PAYMENT-REQUIRED: {header_val[:80]}...")
    data["openai"]["challenge_header"] = header_val

    # Phase 2 — real 200
    tx_id = KNOWN_TXS["x402"] or KNOWN_TXS["mpp"]   # x402 accepts same Algorand TX
    if not tx_id:
        print("  [SKIP] No TX set — skipping 200 capture")
        return

    proof  = _x402_proof(tx_id)
    result = gate.check({"X-PAYMENT": proof})
    if result.requires_payment:
        print(f"  [FAIL] Payment rejected: {result.error}")
        return

    reply = gate.complete([
        {"role": "system", "content": "You are a helpful assistant. Reply in one sentence."},
        {"role": "user",   "content": "Payment verified. Say hello and confirm you are GPT-4o."},
    ])
    print(f"  200 reply: {reply}")
    data["openai"]["tx_id"]    = tx_id
    data["openai"]["proof"]    = proof[:40] + "..."
    data["openai"]["ai_reply"] = reply


def capture_gemini(data: dict) -> None:
    if not GEMINI_KEY:
        print("\n-- Gemini [SKIP] — set GEMINI_KEY env var ---------------")
        return

    from gemini_algovoi import AlgoVoiGemini

    print("\n-- Gemini (AP2 / Algorand) ------------------------------")
    gate = AlgoVoiGemini(
        gemini_key=GEMINI_KEY, algovoi_key=ALGOVOI_KEY,
        tenant_id=TENANT_ID, payout_address=PAYOUT_ALGO,
        protocol="ap2", network="algorand-mainnet",
        amount_microunits=10000, model="gemini-2.0-flash",
    )

    # Phase 1 — real 402
    result_402 = gate.check({}, {})
    header_val = _capture_402_header(result_402, "ap2")
    print(f"  402 X-AP2-Cart-Mandate: {header_val[:80]}...")
    data["gemini"]["challenge_header"] = header_val

    # Phase 2 — AP2 uses its own mandate/receipt flow; skip if no billing key
    print("  [INFO] AP2 Phase 2 requires a funded billing key — skipping AI call")


# -- Main ----------------------------------------------------------------------

def main() -> None:
    data = {
        "claude": {},
        "openai": {},
        "gemini": {},
    }

    capture_claude(data)
    capture_openai(data)
    capture_gemini(data)

    out = os.path.join(_HERE, "demo_data.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"\n✓ Saved {out}")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
