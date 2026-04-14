"""
Tests for AlgoVoi OpenAI Adapter (openai_algovoi.py)

Run:
    python test_openai.py

No live network calls — all AlgoVoi/OpenAI API calls are mocked.
"""

import base64
import importlib
import json
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")

import openai_algovoi as mod
from openai_algovoi import (
    AlgoVoiOpenAI,
    NETWORKS,
    PROTOCOLS,
    _CAIP2,
    _ASSET_ID,
    _SNAKE,
    _X402Gate,
    _build_gate,
)

# ── helpers ───────────────────────────────────────────────────────────────────

ALGOVOI_KEY  = "algv_test_key"
TENANT_ID    = "00000000-0000-0000-0000-000000000001"
PAYOUT_ADDR  = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM"
OPENAI_KEY   = "sk-test"


def _gate(protocol="x402", network="algorand-mainnet", amount=10000):
    return AlgoVoiOpenAI(
        openai_key=OPENAI_KEY,
        algovoi_key=ALGOVOI_KEY,
        tenant_id=TENANT_ID,
        payout_address=PAYOUT_ADDR,
        protocol=protocol,
        network=network,
        amount_microunits=amount,
    )


def ok(label, cond):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {label}")
    return cond


# ── Section 1: Constants ──────────────────────────────────────────────────────

def test_constants():
    print("\n1. Constants")
    results = []
    results.append(ok("NETWORKS has 4 entries", len(NETWORKS) == 4))
    results.append(ok("algorand-mainnet in NETWORKS", "algorand-mainnet" in NETWORKS))
    results.append(ok("voi-mainnet in NETWORKS", "voi-mainnet" in NETWORKS))
    results.append(ok("hedera-mainnet in NETWORKS", "hedera-mainnet" in NETWORKS))
    results.append(ok("stellar-mainnet in NETWORKS", "stellar-mainnet" in NETWORKS))
    results.append(ok("PROTOCOLS has 3 entries", len(PROTOCOLS) == 3))
    results.append(ok("x402 in PROTOCOLS", "x402" in PROTOCOLS))
    results.append(ok("mpp in PROTOCOLS", "mpp" in PROTOCOLS))
    results.append(ok("ap2 in PROTOCOLS", "ap2" in PROTOCOLS))
    results.append(ok("_CAIP2[algorand-mainnet] == algorand:mainnet", _CAIP2["algorand-mainnet"] == "algorand:mainnet"))
    results.append(ok("_CAIP2[voi-mainnet] == voi:mainnet", _CAIP2["voi-mainnet"] == "voi:mainnet"))
    results.append(ok("_CAIP2[hedera-mainnet] == hedera:mainnet", _CAIP2["hedera-mainnet"] == "hedera:mainnet"))
    results.append(ok("_CAIP2[stellar-mainnet] == stellar:pubnet", _CAIP2["stellar-mainnet"] == "stellar:pubnet"))
    results.append(ok("_ASSET_ID[algorand-mainnet] == 31566704", _ASSET_ID["algorand-mainnet"] == "31566704"))
    results.append(ok("_ASSET_ID[voi-mainnet] == 302190", _ASSET_ID["voi-mainnet"] == "302190"))
    results.append(ok("_ASSET_ID[hedera-mainnet] == 0.0.456858", _ASSET_ID["hedera-mainnet"] == "0.0.456858"))
    results.append(ok("_SNAKE[algorand-mainnet] == algorand_mainnet", _SNAKE["algorand-mainnet"] == "algorand_mainnet"))
    results.append(ok("_SNAKE[voi-mainnet] == voi_mainnet", _SNAKE["voi-mainnet"] == "voi_mainnet"))
    return results


# ── Section 2: x402 gate construction ────────────────────────────────────────

def test_x402_gate_construction():
    print("\n2. x402 gate construction")
    results = []

    gate = _X402Gate(
        api_base=mod._API_BASE,
        api_key=ALGOVOI_KEY,
        tenant_id=TENANT_ID,
        payout_address=PAYOUT_ADDR,
        network="algorand-mainnet",
        amount_microunits=10000,
    )
    results.append(ok("_X402Gate constructs", gate is not None))
    results.append(ok("_caip2 set correctly", gate._caip2 == "algorand:mainnet"))
    results.append(ok("_asset_id set correctly", gate._asset_id == "31566704"))
    results.append(ok("_amount set correctly", gate._amount == 10000))
    results.append(ok("_payout_address set correctly", gate._payout_address == PAYOUT_ADDR))

    # Payment required header
    header = gate._payment_required_header()
    decoded = json.loads(base64.b64decode(header))
    results.append(ok("x402Version == 1", decoded["x402Version"] == 1))
    results.append(ok("accepts is list", isinstance(decoded["accepts"], list)))
    results.append(ok("accepts has 1 entry", len(decoded["accepts"]) == 1))
    accept = decoded["accepts"][0]
    results.append(ok("accept.network == algorand:mainnet", accept["network"] == "algorand:mainnet"))
    results.append(ok("accept.asset == 31566704", accept["asset"] == "31566704"))
    results.append(ok("accept.amount == 10000", accept["amount"] == "10000"))
    results.append(ok("accept.payTo == payout_address", accept["payTo"] == PAYOUT_ADDR))
    return results


# ── Section 3: x402 gate — no payment header → 402 ───────────────────────────

def test_x402_no_payment():
    print("\n3. x402 — no payment header -> 402")
    results = []

    gate = _X402Gate(
        api_base=mod._API_BASE, api_key=ALGOVOI_KEY, tenant_id=TENANT_ID,
        payout_address=PAYOUT_ADDR, network="algorand-mainnet", amount_microunits=10000,
    )
    result = gate.check({})
    results.append(ok("requires_payment is True", result.requires_payment))
    body, status, headers = result.as_flask_response()
    results.append(ok("status == 402", status == 402))
    results.append(ok("X-PAYMENT-REQUIRED in headers", "X-PAYMENT-REQUIRED" in headers))
    results.append(ok("Content-Type in headers", "Content-Type" in headers))
    parsed = json.loads(body)
    results.append(ok("error key in body", "error" in parsed))

    # WSGI response
    status_str, header_list, body_bytes = result.as_wsgi_response()
    results.append(ok("WSGI status starts with 402", status_str.startswith("402")))
    results.append(ok("WSGI headers is list", isinstance(header_list, list)))
    results.append(ok("WSGI body is bytes", isinstance(body_bytes, bytes)))
    return results


# ── Section 4: x402 gate — payment verified ───────────────────────────────────

def test_x402_payment_verified():
    print("\n4. x402 — payment header present and verified")
    results = []

    gate = _X402Gate(
        api_base=mod._API_BASE, api_key=ALGOVOI_KEY, tenant_id=TENANT_ID,
        payout_address=PAYOUT_ADDR, network="algorand-mainnet", amount_microunits=10000,
    )

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"verified": True}).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("openai_algovoi.urlopen", return_value=mock_response):
        result = gate.check({"X-Payment": "dGVzdA=="})

    results.append(ok("requires_payment is False", not result.requires_payment))
    return results


# ── Section 5: x402 gate — payment rejected ───────────────────────────────────

def test_x402_payment_rejected():
    print("\n5. x402 — payment header present but rejected")
    results = []

    gate = _X402Gate(
        api_base=mod._API_BASE, api_key=ALGOVOI_KEY, tenant_id=TENANT_ID,
        payout_address=PAYOUT_ADDR, network="algorand-mainnet", amount_microunits=10000,
    )

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"verified": False, "error": "Invalid proof"}).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("openai_algovoi.urlopen", return_value=mock_response):
        result = gate.check({"x-payment": "dGVzdA=="})

    results.append(ok("requires_payment is True", result.requires_payment))
    results.append(ok("error message set", result.error is not None))
    return results


# ── Section 6: x402 gate — all 4 networks ─────────────────────────────────────

def test_x402_all_networks():
    print("\n6. x402 — all 4 networks construct correctly")
    results = []

    for network in NETWORKS:
        gate = _X402Gate(
            api_base=mod._API_BASE, api_key=ALGOVOI_KEY, tenant_id=TENANT_ID,
            payout_address=PAYOUT_ADDR, network=network, amount_microunits=10000,
        )
        header = gate._payment_required_header()
        decoded = json.loads(base64.b64decode(header))
        accept = decoded["accepts"][0]
        results.append(ok(f"{network} caip2 set", accept["network"] == _CAIP2[network]))
        results.append(ok(f"{network} asset_id set", accept["asset"] == _ASSET_ID[network]))

    return results


# ── Section 7: AlgoVoiOpenAI — construction with x402 ────────────────────────

def test_algovoi_openai_x402():
    print("\n7. AlgoVoiOpenAI construction with x402")
    results = []

    gate = _gate(protocol="x402", network="algorand-mainnet")
    results.append(ok("AlgoVoiOpenAI constructs", gate is not None))
    results.append(ok("gate._gate is _X402Gate", isinstance(gate._gate, _X402Gate)))
    results.append(ok("gate._openai_key set", gate._openai_key == OPENAI_KEY))
    results.append(ok("gate._model is gpt-4o", gate._model == "gpt-4o"))
    results.append(ok("gate._base_url is None by default", gate._base_url is None))
    return results


# ── Section 8: AlgoVoiOpenAI — construction with MPP (mocked import) ─────────

def test_algovoi_openai_mpp():
    print("\n8. AlgoVoiOpenAI construction with MPP (mocked)")
    results = []

    mock_mpp_gate = MagicMock()
    mock_mpp_module = types.ModuleType("mpp")
    mock_mpp_module.MppGate = MagicMock(return_value=mock_mpp_gate)

    with patch.dict(sys.modules, {"mpp": mock_mpp_module}):
        gate = _gate(protocol="mpp", network="algorand-mainnet")

    results.append(ok("AlgoVoiOpenAI constructs with mpp", gate is not None))
    results.append(ok("MppGate was called", mock_mpp_module.MppGate.called))
    call_kwargs = mock_mpp_module.MppGate.call_args[1]
    results.append(ok("networks=[algorand_mainnet]", call_kwargs["networks"] == ["algorand_mainnet"]))
    results.append(ok("payout_address passed", call_kwargs["payout_address"] == PAYOUT_ADDR))
    results.append(ok("amount_microunits passed", call_kwargs["amount_microunits"] == 10000))
    return results


# ── Section 9: AlgoVoiOpenAI — construction with AP2 (mocked import) ─────────

def test_algovoi_openai_ap2():
    print("\n9. AlgoVoiOpenAI construction with AP2 (mocked)")
    results = []

    mock_ap2_gate = MagicMock()
    mock_ap2_module = types.ModuleType("ap2")
    mock_ap2_module.Ap2Gate = MagicMock(return_value=mock_ap2_gate)

    with patch.dict(sys.modules, {"ap2": mock_ap2_module}):
        gate = _gate(protocol="ap2", network="voi-mainnet")

    results.append(ok("AlgoVoiOpenAI constructs with ap2", gate is not None))
    results.append(ok("Ap2Gate was called", mock_ap2_module.Ap2Gate.called))
    call_kwargs = mock_ap2_module.Ap2Gate.call_args[1]
    results.append(ok("networks=[voi-mainnet] (hyphenated)", call_kwargs["networks"] == ["voi-mainnet"]))
    results.append(ok("merchant_id == tenant_id", call_kwargs["merchant_id"] == TENANT_ID))
    return results


# ── Section 10: AlgoVoiOpenAI — all 4 networks x402 ─────────────────────────

def test_all_networks_x402():
    print("\n10. AlgoVoiOpenAI — all 4 networks construct with x402")
    results = []

    for network in NETWORKS:
        g = _gate(protocol="x402", network=network)
        results.append(ok(f"{network} constructs", g is not None))
        results.append(ok(f"{network} inner gate caip2 correct", g._gate._caip2 == _CAIP2[network]))

    return results


# ── Section 11: AlgoVoiOpenAI — check() wraps gate ───────────────────────────

def test_check_wraps_gate():
    print("\n11. AlgoVoiOpenAI.check() wraps inner gate")
    results = []

    gate = _gate(protocol="x402")
    result = gate.check({})
    results.append(ok("result.requires_payment is True", result.requires_payment))
    results.append(ok("result has as_flask_response", hasattr(result, "as_flask_response")))
    results.append(ok("result has as_wsgi_response", hasattr(result, "as_wsgi_response")))

    body, status, headers = result.as_flask_response()
    results.append(ok("flask status 402", status == 402))
    results.append(ok("X-PAYMENT-REQUIRED in headers", "X-PAYMENT-REQUIRED" in headers))

    status_str, header_list, body_bytes = result.as_wsgi_response()
    results.append(ok("wsgi status starts with 402", status_str.startswith("402")))
    return results


# ── Section 12: AlgoVoiOpenAI — complete() calls OpenAI ──────────────────────

def test_complete_calls_openai():
    print("\n12. AlgoVoiOpenAI.complete() calls OpenAI SDK")
    results = []

    gate = _gate(protocol="x402")

    mock_client_instance = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "Hello from AI!"
    mock_client_instance.chat.completions.create.return_value = mock_completion

    mock_openai = MagicMock()
    mock_openai.return_value = mock_client_instance

    with patch.dict(sys.modules, {"openai": MagicMock(OpenAI=mock_openai)}):
        result = gate.complete([{"role": "user", "content": "Hi"}])

    results.append(ok("complete() returns string", isinstance(result, str)))
    results.append(ok("complete() returns AI content", result == "Hello from AI!"))
    results.append(ok("OpenAI client was created with api_key", mock_openai.call_args[1]["api_key"] == OPENAI_KEY))
    results.append(ok("chat.completions.create was called", mock_client_instance.chat.completions.create.called))
    call_kwargs = mock_client_instance.chat.completions.create.call_args[1]
    results.append(ok("model=gpt-4o passed", call_kwargs["model"] == "gpt-4o"))
    results.append(ok("messages passed correctly", call_kwargs["messages"] == [{"role": "user", "content": "Hi"}]))
    return results


# ── Section 13: AlgoVoiOpenAI — complete() model override ────────────────────

def test_complete_model_override():
    print("\n13. AlgoVoiOpenAI.complete() model override")
    results = []

    gate = _gate(protocol="x402")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "Hi"
    mock_client.chat.completions.create.return_value = mock_resp

    mock_openai_mod = MagicMock()
    mock_openai_mod.OpenAI.return_value = mock_client

    with patch.dict(sys.modules, {"openai": mock_openai_mod}):
        gate.complete([{"role": "user", "content": "test"}], model="gpt-3.5-turbo")

    call_kwargs = mock_client.chat.completions.create.call_args[1]
    results.append(ok("overridden model used", call_kwargs["model"] == "gpt-3.5-turbo"))
    return results


# ── Section 14: AlgoVoiOpenAI — base_url for compatible APIs ─────────────────

def test_base_url_override():
    print("\n14. base_url override for OpenAI-compatible APIs")
    results = []

    for provider, url in [
        ("mistral",     "https://api.mistral.ai/v1"),
        ("together",    "https://api.together.xyz/v1"),
        ("groq",        "https://api.groq.com/openai/v1"),
        ("perplexity",  "https://api.perplexity.ai"),
    ]:
        gate = AlgoVoiOpenAI(
            openai_key=OPENAI_KEY, algovoi_key=ALGOVOI_KEY,
            tenant_id=TENANT_ID, payout_address=PAYOUT_ADDR,
            protocol="x402", network="algorand-mainnet",
            base_url=url,
        )
        results.append(ok(f"{provider} base_url stored", gate._base_url == url))

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "ok"
        mock_client.chat.completions.create.return_value = mock_resp

        mock_openai_mod = MagicMock()
        mock_openai_mod.OpenAI.return_value = mock_client

        with patch.dict(sys.modules, {"openai": mock_openai_mod}):
            gate.complete([{"role": "user", "content": "test"}])

        results.append(ok(f"{provider} base_url passed to OpenAI()", mock_openai_mod.OpenAI.call_args[1]["base_url"] == url))

    return results


# ── Section 15: AlgoVoiOpenAI — invalid protocol/network ──────────────────────

def test_invalid_inputs():
    print("\n15. Invalid protocol / network raises ValueError")
    results = []

    try:
        _gate(protocol="lightning")
        results.append(ok("invalid protocol raises ValueError", False))
    except ValueError as e:
        results.append(ok("invalid protocol raises ValueError", "protocol" in str(e)))

    try:
        _gate(network="ethereum-mainnet")
        results.append(ok("invalid network raises ValueError", False))
    except ValueError as e:
        results.append(ok("invalid network raises ValueError", "network" in str(e)))

    return results


# ── Section 16: _Result WSGI/Flask pass-through ───────────────────────────────

def test_result_passthrough():
    print("\n16. _Result delegates as_flask/as_wsgi to inner gate")
    results = []

    from openai_algovoi import _Result

    mock_inner = MagicMock()
    mock_inner.requires_payment = True
    mock_inner.as_flask_response.return_value = ('{"error":"x"}', 402, {"X-Test": "1"})
    mock_inner.as_wsgi_response.return_value = ("402 Payment Required", [("X-Test", "1")], b'{"error":"x"}')

    result = _Result(requires_payment=True, inner=mock_inner)

    flask_resp = result.as_flask_response()
    results.append(ok("flask delegates to inner", flask_resp[1] == 402))
    results.append(ok("flask header passed through", flask_resp[2].get("X-Test") == "1"))

    wsgi_resp = result.as_wsgi_response()
    results.append(ok("wsgi delegates to inner", wsgi_resp[0].startswith("402")))
    results.append(ok("wsgi body is bytes", isinstance(wsgi_resp[2], bytes)))

    return results


# ── Section 17: x402 verify — urlopen error handled gracefully ────────────────

def test_x402_verify_network_error():
    print("\n17. x402 verify — network error handled gracefully")
    results = []
    from urllib.error import URLError

    gate = _X402Gate(
        api_base=mod._API_BASE, api_key=ALGOVOI_KEY, tenant_id=TENANT_ID,
        payout_address=PAYOUT_ADDR, network="algorand-mainnet", amount_microunits=10000,
    )

    with patch("openai_algovoi.urlopen", side_effect=URLError("timeout")):
        result = gate.check({"X-Payment": "dGVzdA=="})

    results.append(ok("requires_payment True on network error", result.requires_payment))
    results.append(ok("error message set", "Verification error" in (result.error or "")))
    return results


# ── Section 18: complete() — openai not installed ─────────────────────────────

def test_complete_no_openai():
    print("\n18. complete() raises ImportError when openai not installed")
    results = []

    gate = _gate(protocol="x402")

    real_modules = dict(sys.modules)
    sys.modules.pop("openai", None)

    try:
        with patch.dict(sys.modules, {"openai": None}):
            try:
                gate.complete([{"role": "user", "content": "test"}])
                results.append(ok("ImportError raised", False))
            except ImportError as e:
                results.append(ok("ImportError raised", "openai" in str(e)))
    finally:
        sys.modules.update(real_modules)

    return results


# ── Runner ────────────────────────────────────────────────────────────────────

def main():
    sections = [
        test_constants,
        test_x402_gate_construction,
        test_x402_no_payment,
        test_x402_payment_verified,
        test_x402_payment_rejected,
        test_x402_all_networks,
        test_algovoi_openai_x402,
        test_algovoi_openai_mpp,
        test_algovoi_openai_ap2,
        test_all_networks_x402,
        test_check_wraps_gate,
        test_complete_calls_openai,
        test_complete_model_override,
        test_base_url_override,
        test_invalid_inputs,
        test_result_passthrough,
        test_x402_verify_network_error,
        test_complete_no_openai,
    ]

    all_results = []
    for fn in sections:
        all_results.extend(fn())

    passed = sum(all_results)
    total  = len(all_results)
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} passed", "PASS" if passed == total else "FAIL")
    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
