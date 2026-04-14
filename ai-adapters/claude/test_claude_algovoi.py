"""
AlgoVoi Claude Adapter — Tests
================================
All tests are unit tests — no live network calls, all external I/O mocked.
"""

import base64
import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mpp-adapter"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ap2-adapter"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "openai"))

import claude_algovoi as mod
from claude_algovoi import AlgoVoiClaude, ClaudeAiResult

PASS = FAIL = 0

def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
        return True
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))
        return False


# ── Shared constants ──────────────────────────────────────────────────────────

ANTHROPIC_KEY = "sk-ant-test-key"
ALGOVOI_KEY   = "algv_testkey"
TENANT_ID     = "YOUR_TENANT_ID"
PAYOUT_ADDR   = "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ"


def _make_gate(**kwargs):
    defaults = dict(
        anthropic_key=ANTHROPIC_KEY, algovoi_key=ALGOVOI_KEY,
        tenant_id=TENANT_ID, payout_address=PAYOUT_ADDR,
    )
    defaults.update(kwargs)
    return AlgoVoiClaude(**defaults)


# ── Section 1: construction — MPP (default) ───────────────────────────────────

def test_construction_mpp():
    print("\n1. AlgoVoiClaude construction — MPP (default)")
    results = []

    gate = _make_gate()
    results.append(ok("gate constructs", gate is not None))
    results.append(ok("anthropic_key stored", gate._anthropic_key == ANTHROPIC_KEY))
    results.append(ok("model default claude-sonnet-4-5", gate._model == "claude-sonnet-4-5"))
    results.append(ok("max_tokens default 1024", gate._max_tokens == 1024))
    results.append(ok("inner MppGate created", gate._gate is not None))
    results.append(ok("resource_id default ai-chat", gate._gate.resource_id == "ai-chat"))
    results.append(ok("amount_microunits passed", gate._gate.amount_microunits == 10000))
    results.append(ok("payout_address passed", gate._gate.payout_address == PAYOUT_ADDR))
    results.append(ok("algorand_mainnet in networks",
                      "algorand_mainnet" in gate._gate.networks))

    return results


# ── Section 2: construction — AP2 ─────────────────────────────────────────────

def test_construction_ap2():
    print("\n2. AlgoVoiClaude construction — AP2")
    results = []

    gate = _make_gate(protocol="ap2", network="algorand-mainnet")
    results.append(ok("gate constructs", gate is not None))
    results.append(ok("inner Ap2Gate created", gate._gate is not None))
    results.append(ok("merchant_id == tenant_id", gate._gate.merchant_id == TENANT_ID))
    results.append(ok("payout_address passed", gate._gate.payout_address == PAYOUT_ADDR))
    results.append(ok("algorand-mainnet in networks",
                      "algorand-mainnet" in gate._gate.networks))

    return results


# ── Section 3: construction — x402 ────────────────────────────────────────────

def test_construction_x402():
    print("\n3. AlgoVoiClaude construction — x402")
    results = []

    gate = _make_gate(protocol="x402", network="algorand-mainnet")
    results.append(ok("gate constructs", gate is not None))
    results.append(ok("inner gate created", gate._gate is not None))

    return results


# ── Section 4: invalid protocol / network raises ──────────────────────────────

def test_invalid_args():
    print("\n4. Invalid protocol / network raises ValueError")
    results = []

    try:
        _make_gate(protocol="bogus")
        results.append(ok("bad protocol raises", False, "no error"))
    except ValueError:
        results.append(ok("bad protocol raises", True))

    try:
        _make_gate(network="solana-mainnet")
        results.append(ok("bad network raises", False, "no error"))
    except ValueError:
        results.append(ok("bad network raises", True))

    return results


# ── Section 5: check() — MPP no credential → 402 ──────────────────────────────

def test_check_mpp_no_credential():
    print("\n5. check() — MPP no credential -> 402")
    results = []

    gate = _make_gate()
    result = gate.check({})

    results.append(ok("requires_payment True", result.requires_payment))
    results.append(ok("result is ClaudeAiResult", isinstance(result, ClaudeAiResult)))
    results.append(ok("receipt is None", result.receipt is None))
    results.append(ok("has as_flask_response", hasattr(result, "as_flask_response")))
    results.append(ok("has as_wsgi_response", hasattr(result, "as_wsgi_response")))

    body, status, headers = result.as_flask_response()
    results.append(ok("flask status 402", status == 402))
    results.append(ok("WWW-Authenticate in headers",
                      any("www-authenticate" == k.lower() for k in headers)))

    wsgi_status, wsgi_headers, wsgi_body = result.as_wsgi_response()
    results.append(ok("wsgi status starts 402", wsgi_status.startswith("402")))
    results.append(ok("wsgi body is bytes", isinstance(wsgi_body, bytes)))

    return results


# ── Section 6: check() — MPP valid credential → receipt ───────────────────────

def test_check_mpp_valid():
    print("\n6. check() — MPP valid credential -> receipt")
    results = []

    gate = _make_gate()
    tx_id = "DF2PQUPY6TVX3DD7GQSY7LEZNVGOEYC24NBIIHLKYM5RIA3UN4AQ"

    indexer_data = json.dumps({"transaction": {
        "confirmed-round": 12345678,
        "sender": "PAYER_ADDR",
        "asset-transfer-transaction": {
            "receiver": PAYOUT_ADDR,
            "amount": 10000,
            "asset-id": 31566704,
        },
    }}).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = indexer_data
    mock_resp.status = 200
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    proof = base64.b64encode(json.dumps({
        "network": "algorand-mainnet",
        "payload": {"txId": tx_id},
    }).encode()).decode()

    with patch("mpp.urlopen", return_value=mock_resp):
        result = gate.check({"Authorization": f"Payment {proof}"})

    results.append(ok("requires_payment False", not result.requires_payment))
    results.append(ok("receipt present", result.receipt is not None))
    if result.receipt:
        results.append(ok("receipt.tx_id matches", result.receipt.tx_id == tx_id))
        results.append(ok("receipt.amount set", result.receipt.amount >= 10000))

    return results


# ── Section 7: check() — AP2 no mandate → 402 with CartMandate ────────────────

def test_check_ap2_no_mandate():
    print("\n7. check() — AP2 no mandate -> 402 CartMandate")
    results = []

    gate = _make_gate(protocol="ap2", network="algorand-mainnet")
    result = gate.check({}, {})

    results.append(ok("requires_payment True", result.requires_payment))
    results.append(ok("result is ClaudeAiResult", isinstance(result, ClaudeAiResult)))
    results.append(ok("mandate is None", result.mandate is None))

    body, status, headers = result.as_flask_response()
    results.append(ok("flask status 402", status == 402))
    results.append(ok("X-AP2-Cart-Mandate in headers",
                      any("x-ap2-cart-mandate" == k.lower() for k in headers)))

    wsgi_status, wsgi_headers, wsgi_body = result.as_wsgi_response()
    results.append(ok("wsgi status starts 402", wsgi_status.startswith("402")))
    results.append(ok("wsgi body is bytes", isinstance(wsgi_body, bytes)))

    return results


# ── Section 8: check() — AP2 valid mandate ────────────────────────────────────

def test_check_ap2_valid():
    print("\n8. check() — AP2 valid mandate")
    results = []

    import nacl.signing as _nacl  # type: ignore
    signing_key = _nacl.SigningKey.generate()
    pubkey      = bytes(signing_key.verify_key)
    payer_addr  = base64.b32encode(pubkey + b'\x00' * 4).decode().rstrip('=')
    tx_id       = "SDIX4LHMRGX5E2JJ5XTZ7WEKIZB6AVSLIRWUPTQ3FYKRSSVDMHWQ"

    gate = _make_gate(protocol="ap2", network="algorand-mainnet")

    # Step 1: get cart mandate
    result_cart = gate.check({}, {})
    _, _, cart_headers = result_cart.as_flask_response()

    # Step 2: build PaymentMandate
    mandate_obj = {
        "ap2_version": "0.1",
        "type": "PaymentMandate",
        "merchant_id": TENANT_ID,
        "payer_address": payer_addr,
        "payment_response": {
            "method_name": "https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1",
            "details": {
                "network": "algorand-mainnet",
                "tx_id":   tx_id,
            },
        },
    }
    canonical  = json.dumps(mandate_obj, separators=(",", ":"), sort_keys=True).encode()
    sig_bytes  = signing_key.sign(canonical).signature
    mandate_obj["signature"] = base64.b64encode(sig_bytes).decode()

    # Step 3: mock indexer confirming the TX
    indexer_data = json.dumps({"transaction": {
        "confirmed-round": 12345678,
        "sender": payer_addr,
        "asset-transfer-transaction": {
            "receiver": PAYOUT_ADDR,
            "amount": 10000,
            "asset-id": 31566704,
        },
    }}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = indexer_data
    mock_resp.status = 200
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("ap2.urlopen", return_value=mock_resp):
        result = gate.check(
            {"X-AP2-Mandate": base64.b64encode(json.dumps(mandate_obj).encode()).decode()},
            {},
        )

    results.append(ok("requires_payment False", not result.requires_payment))
    results.append(ok("mandate present", result.mandate is not None))
    if result.mandate:
        results.append(ok("mandate.tx_id matches", result.mandate.tx_id == tx_id))
        results.append(ok("mandate.network set", result.mandate.network == "algorand-mainnet"))
        results.append(ok("mandate.payer_address set", result.mandate.payer_address == payer_addr))

    return results


# ── Section 9: complete() — system role extracted ─────────────────────────────

def test_complete_system_extraction():
    print("\n9. complete() — system role extracted correctly")
    results = []

    gate = _make_gate()

    mock_content = MagicMock()
    mock_content.text = "Hello from Claude!"
    mock_response = MagicMock()
    mock_response.content = [mock_content]

    messages = [
        {"role": "system",    "content": "You are a helpful assistant."},
        {"role": "user",      "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
        {"role": "user",      "content": "What can you do?"},
    ]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("anthropic.Anthropic", return_value=mock_client):
        reply = gate.complete(messages)

    results.append(ok("returns string", isinstance(reply, str)))
    results.append(ok("returns content", reply == "Hello from Claude!"))

    call_kwargs = mock_client.messages.create.call_args[1]
    results.append(ok("system extracted", call_kwargs.get("system") == "You are a helpful assistant."))
    results.append(ok("turns filtered", all(m["role"] in ("user", "assistant")
                                            for m in call_kwargs["messages"])))
    results.append(ok("3 turns (not 4)", len(call_kwargs["messages"]) == 3))

    return results


# ── Section 10: complete() — model / max_tokens override ──────────────────────

def test_complete_overrides():
    print("\n10. complete() — model and max_tokens override")
    results = []

    gate = _make_gate(model="claude-opus-4-5", max_tokens=512)
    results.append(ok("model stored", gate._model == "claude-opus-4-5"))
    results.append(ok("max_tokens stored", gate._max_tokens == 512))

    mock_content = MagicMock()
    mock_content.text = "ok"
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("anthropic.Anthropic", return_value=mock_client):
        gate.complete(
            [{"role": "user", "content": "hi"}],
            model="claude-haiku-3-5",
            max_tokens=256,
        )

    call_kwargs = mock_client.messages.create.call_args[1]
    results.append(ok("model override used", call_kwargs["model"] == "claude-haiku-3-5"))
    results.append(ok("max_tokens override used", call_kwargs["max_tokens"] == 256))

    return results


# ── Section 11: complete() — no system role ───────────────────────────────────

def test_complete_no_system():
    print("\n11. complete() — no system role in messages")
    results = []

    gate = _make_gate()

    mock_content = MagicMock()
    mock_content.text = "Hi!"
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("anthropic.Anthropic", return_value=mock_client):
        gate.complete([{"role": "user", "content": "Hello"}])

    call_kwargs = mock_client.messages.create.call_args[1]
    results.append(ok("system not in kwargs", "system" not in call_kwargs))
    results.append(ok("messages present", len(call_kwargs["messages"]) == 1))

    return results


# ── Section 12: ClaudeAiResult delegates correctly ────────────────────────────

def test_result_delegation():
    print("\n12. ClaudeAiResult delegates as_flask/wsgi to inner")
    results = []

    inner = MagicMock()
    inner.requires_payment = True
    inner.receipt  = None
    inner.mandate  = None
    inner.error    = "no payment"
    inner.as_flask_response.return_value = ("body", 402, {"WWW-Authenticate": "Payment x"})
    inner.as_wsgi_response.return_value  = (
        "402 Payment Required", [("WWW-Authenticate", "Payment x")], b"body"
    )

    result = ClaudeAiResult(inner)
    results.append(ok("requires_payment delegated", result.requires_payment))
    results.append(ok("error delegated", result.error == "no payment"))

    body, status, headers = result.as_flask_response()
    results.append(ok("flask delegates", status == 402))
    results.append(ok("WWW-Authenticate passed", "WWW-Authenticate" in headers))

    wsgi_status, _, wsgi_body = result.as_wsgi_response()
    results.append(ok("wsgi delegates", wsgi_status.startswith("402")))
    results.append(ok("wsgi body bytes", isinstance(wsgi_body, bytes)))

    return results


# ── Section 13: ClaudeAiResult fallback (no delegate methods) ─────────────────

def test_result_fallback():
    print("\n13. ClaudeAiResult fallback when inner has no response methods")
    results = []

    inner = MagicMock(spec=[])   # no methods
    inner.requires_payment = True
    inner.receipt  = None
    inner.mandate  = None
    inner.error    = "test error"

    result = ClaudeAiResult(inner)

    body, status, headers = result.as_flask_response()
    results.append(ok("flask fallback status 402", status == 402))
    results.append(ok("flask fallback content-type",
                      headers.get("Content-Type") == "application/json"))

    wsgi_status, wsgi_headers, wsgi_body = result.as_wsgi_response()
    results.append(ok("wsgi fallback status", wsgi_status.startswith("402")))
    results.append(ok("wsgi fallback bytes", isinstance(wsgi_body, bytes)))

    return results


# ── Section 14: ImportError when anthropic not installed ──────────────────────

def test_import_error():
    print("\n14. complete() raises ImportError when anthropic not installed")
    results = []

    gate = _make_gate()
    real_modules = dict(sys.modules)
    sys.modules["anthropic"] = None  # type: ignore

    try:
        gate.complete([{"role": "user", "content": "hi"}])
        results.append(ok("ImportError raised", False, "no error raised"))
    except ImportError:
        results.append(ok("ImportError raised", True))
    finally:
        sys.modules.clear()
        sys.modules.update(real_modules)

    return results


# ── Section 15: all supported models construct ────────────────────────────────

def test_all_models():
    print("\n15. all supported Claude models construct")
    results = []

    for model in ["claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-3-5"]:
        gate = _make_gate(model=model)
        results.append(ok(f"{model} stored", gate._model == model))

    return results


# ── Section 16: all networks construct for MPP ────────────────────────────────

def test_all_networks_mpp():
    print("\n16. all networks construct for MPP")
    results = []

    for net in ["algorand-mainnet", "voi-mainnet", "hedera-mainnet", "stellar-mainnet"]:
        gate = _make_gate(protocol="mpp", network=net)
        results.append(ok(f"{net} constructs", gate._gate is not None))

    return results


# ── Section 17: all networks construct for AP2 ────────────────────────────────

def test_all_networks_ap2():
    print("\n17. all networks construct for AP2")
    results = []

    for net in ["algorand-mainnet", "voi-mainnet", "hedera-mainnet", "stellar-mainnet"]:
        gate = _make_gate(protocol="ap2", network=net)
        results.append(ok(f"{net} constructs", gate._gate is not None))

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global PASS, FAIL
    PASS = FAIL = 0

    sections = [
        test_construction_mpp,
        test_construction_ap2,
        test_construction_x402,
        test_invalid_args,
        test_check_mpp_no_credential,
        test_check_mpp_valid,
        test_check_ap2_no_mandate,
        test_check_ap2_valid,
        test_complete_system_extraction,
        test_complete_overrides,
        test_complete_no_system,
        test_result_delegation,
        test_result_fallback,
        test_import_error,
        test_all_models,
        test_all_networks_mpp,
        test_all_networks_ap2,
    ]

    for fn in sections:
        fn()

    print(f"\n{'='*50}")
    print(f"Results: {PASS}/{PASS+FAIL} passed", "PASS" if FAIL == 0 else "FAIL")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
