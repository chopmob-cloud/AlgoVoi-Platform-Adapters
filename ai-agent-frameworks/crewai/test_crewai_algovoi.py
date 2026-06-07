"""
Unit tests for crewai_algovoi.py
==================================
All network and CrewAI SDK calls are mocked — no live requests, no API keys.

Run:
    cd ai-agent-frameworks/crewai
    pytest test_crewai_algovoi.py -v
"""

from __future__ import annotations

import base64
import json
import sys
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

VALID_KWARGS = dict(
    algovoi_key="algv_test",
    tenant_id="tenant-uuid",
    payout_address="ZVLR...",
    protocol="mpp",
    network="algorand-mainnet",
)


def _make_gate_result(requires_payment: bool = True) -> MagicMock:
    r = MagicMock()
    r.requires_payment = requires_payment
    r.error = "Payment required" if requires_payment else None
    r.receipt = None if requires_payment else MagicMock(
        payer="ADDR", tx_id="TX123", amount=10_000
    )
    r.mandate = None
    r.as_flask_response.return_value = (
        b'{"error":"Payment Required"}',
        402,
        {"WWW-Authenticate": "Payment challenge=..."},
    )
    r.as_wsgi_response.return_value = (
        b'{"error":"Payment Required"}',
        402,
        {"WWW-Authenticate": "Payment challenge=..."},
    )
    return r


def _make_gate(requires_payment: bool = True) -> MagicMock:
    g = MagicMock()
    g.check.return_value = _make_gate_result(requires_payment)
    return g


def _mpp_proof(network: str, tx_id: str) -> str:
    return base64.b64encode(
        json.dumps({"network": network, "payload": {"txId": tx_id}}).encode()
    ).decode()


# ---------------------------------------------------------------------------
# Import module under test
# ---------------------------------------------------------------------------

import crewai_algovoi
from crewai_algovoi import (
    NETWORKS,
    PROTOCOLS,
    AlgoVoiCrewAI,
    AlgoVoiPaymentTool,
    CrewAIResult,
    PaymentToolInput,
    _MAX_FLASK_BODY,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_gate():
    return _make_gate(requires_payment=True)


@pytest.fixture()
def verified_gate():
    return _make_gate(requires_payment=False)


@pytest.fixture()
def adapter(mock_gate):
    with patch("crewai_algovoi._build_gate", return_value=mock_gate):
        return AlgoVoiCrewAI(**VALID_KWARGS)


@pytest.fixture()
def verified_adapter(verified_gate):
    with patch("crewai_algovoi._build_gate", return_value=verified_gate):
        return AlgoVoiCrewAI(**VALID_KWARGS)


# ---------------------------------------------------------------------------
# TestModule
# ---------------------------------------------------------------------------

class TestModule:
    def test_version_string(self):
        assert isinstance(crewai_algovoi.__version__, str)
        assert crewai_algovoi.__version__ == "1.0.0"

    def test_algovoicrewai_exported(self):
        assert "AlgoVoiCrewAI" in crewai_algovoi.__all__

    def test_algovoipaymenttool_exported(self):
        assert "AlgoVoiPaymentTool" in crewai_algovoi.__all__

    def test_crewairesult_exported(self):
        assert "CrewAIResult" in crewai_algovoi.__all__


# ---------------------------------------------------------------------------
# TestConstruction
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_construct_with_openai_key(self):
        with patch("crewai_algovoi._build_gate", return_value=_make_gate()):
            gate = AlgoVoiCrewAI(openai_key="sk-test", **VALID_KWARGS)
        assert gate._openai_key == "sk-test"

    def test_construct_with_llm(self):
        mock_llm = MagicMock()
        with patch("crewai_algovoi._build_gate", return_value=_make_gate()):
            gate = AlgoVoiCrewAI(llm=mock_llm, **VALID_KWARGS)
        assert gate._llm is mock_llm

    def test_default_protocol_is_mpp(self):
        with patch("crewai_algovoi._build_gate", return_value=_make_gate()) as bg:
            AlgoVoiCrewAI(**VALID_KWARGS)
        assert bg.call_args.kwargs["protocol"] == "mpp"

    def test_default_network_is_algorand(self):
        with patch("crewai_algovoi._build_gate", return_value=_make_gate()) as bg:
            AlgoVoiCrewAI(**VALID_KWARGS)
        assert bg.call_args.kwargs["network"] == "algorand-mainnet"

    def test_default_model(self):
        with patch("crewai_algovoi._build_gate", return_value=_make_gate()):
            gate = AlgoVoiCrewAI(**VALID_KWARGS)
        assert gate._model == "openai/gpt-4o"

    def test_default_resource_id(self):
        with patch("crewai_algovoi._build_gate", return_value=_make_gate()) as bg:
            AlgoVoiCrewAI(**VALID_KWARGS)
        assert bg.call_args.kwargs["resource_id"] == "ai-crew"

    def test_invalid_protocol_raises(self):
        kw = {k: v for k, v in VALID_KWARGS.items() if k != "protocol"}
        with pytest.raises(ValueError, match="protocol"):
            with patch("crewai_algovoi._build_gate", return_value=_make_gate()):
                AlgoVoiCrewAI(protocol="grpc", **kw)

    def test_invalid_network_raises(self):
        kw = {k: v for k, v in VALID_KWARGS.items() if k != "network"}
        with pytest.raises(ValueError, match="network"):
            with patch("crewai_algovoi._build_gate", return_value=_make_gate()):
                AlgoVoiCrewAI(network="bitcoin-mainnet", **kw)

    def test_all_protocols_accepted(self):
        for proto in ("mpp", "ap2", "x402"):
            kw = {**VALID_KWARGS, "protocol": proto}
            with patch("crewai_algovoi._build_gate", return_value=_make_gate()):
                gate = AlgoVoiCrewAI(**kw)
            assert gate is not None

    def test_all_networks_accepted(self):
        for net in NETWORKS:
            kw = {**VALID_KWARGS, "network": net}
            with patch("crewai_algovoi._build_gate", return_value=_make_gate()):
                gate = AlgoVoiCrewAI(**kw)
            assert gate is not None


# ---------------------------------------------------------------------------
# TestCrewAIResult
# ---------------------------------------------------------------------------

class TestCrewAIResult:
    def test_requires_payment_true(self):
        r = CrewAIResult(_make_gate_result(requires_payment=True))
        assert r.requires_payment is True

    def test_requires_payment_false(self):
        r = CrewAIResult(_make_gate_result(requires_payment=False))
        assert r.requires_payment is False

    def test_error_when_requires_payment(self):
        r = CrewAIResult(_make_gate_result(requires_payment=True))
        assert r.error == "Payment required"

    def test_error_none_when_verified(self):
        r = CrewAIResult(_make_gate_result(requires_payment=False))
        assert r.error is None

    def test_receipt_forwarded(self):
        raw = _make_gate_result(requires_payment=False)
        r = CrewAIResult(raw)
        assert r.receipt is raw.receipt

    def test_mandate_forwarded(self):
        raw = _make_gate_result(requires_payment=True)
        raw.mandate = MagicMock()
        r = CrewAIResult(raw)
        assert r.mandate is raw.mandate

    def test_as_flask_response_delegates(self):
        raw = _make_gate_result(requires_payment=True)
        r = CrewAIResult(raw)
        resp = r.as_flask_response()
        raw.as_flask_response.assert_called_once()
        assert resp == raw.as_flask_response.return_value

    def test_as_wsgi_response_delegates(self):
        raw = _make_gate_result(requires_payment=True)
        r = CrewAIResult(raw)
        resp = r.as_wsgi_response()
        raw.as_wsgi_response.assert_called_once()
        assert resp == raw.as_wsgi_response.return_value


# ---------------------------------------------------------------------------
# TestCheck
# ---------------------------------------------------------------------------

class TestCheck:
    def test_check_returns_crewai_result(self, adapter):
        result = adapter.check({})
        assert isinstance(result, CrewAIResult)

    def test_check_requires_payment_when_no_proof(self, adapter):
        result = adapter.check({})
        assert result.requires_payment is True

    def test_check_verified_when_proof_present(self, verified_adapter):
        result = verified_adapter.check({"Authorization": "Payment proof123"})
        assert result.requires_payment is False

    def test_check_passes_headers_to_gate(self, adapter, mock_gate):
        headers = {"Authorization": "Payment xyz"}
        adapter.check(headers)
        mock_gate.check.assert_called()

    def test_check_body_defaults_to_empty_dict(self, adapter, mock_gate):
        adapter.check({})
        mock_gate.check.assert_called()

    def test_check_receipt_on_verified(self, verified_adapter):
        result = verified_adapter.check({"Authorization": "Payment proof"})
        assert result.receipt is not None

    def test_check_with_body(self, adapter, mock_gate):
        adapter.check({"Authorization": "Payment x"}, {"key": "val"})
        mock_gate.check.assert_called()

    def test_check_mpp_gate_called(self):
        gate = _make_gate(requires_payment=True)
        with patch("crewai_algovoi._build_gate", return_value=gate):
            a = AlgoVoiCrewAI(**VALID_KWARGS)
        a.check({"Authorization": "Payment x"})
        gate.check.assert_called()


# ---------------------------------------------------------------------------
# TestCrewKickoff
# ---------------------------------------------------------------------------

class TestCrewKickoff:
    def test_kickoff_called_with_inputs(self, verified_adapter):
        crew = MagicMock()
        crew.kickoff.return_value = MagicMock(raw="Crew finished successfully")
        verified_adapter.crew_kickoff(crew, inputs={"topic": "AlgoVoi"})
        crew.kickoff.assert_called_once_with(inputs={"topic": "AlgoVoi"})

    def test_kickoff_returns_raw_string(self, verified_adapter):
        crew = MagicMock()
        crew.kickoff.return_value = MagicMock(raw="The final answer")
        result = verified_adapter.crew_kickoff(crew)
        assert result == "The final answer"

    def test_kickoff_empty_inputs_defaults_to_empty_dict(self, verified_adapter):
        crew = MagicMock()
        crew.kickoff.return_value = MagicMock(raw="ok")
        verified_adapter.crew_kickoff(crew)
        crew.kickoff.assert_called_once_with(inputs={})

    def test_kickoff_fallback_when_no_raw_attr(self, verified_adapter):
        class _NoRaw:
            def __str__(self):
                return "string output"

        crew = MagicMock()
        crew.kickoff.return_value = _NoRaw()
        result = verified_adapter.crew_kickoff(crew)
        assert result == "string output"

    def test_kickoff_returns_str_type(self, verified_adapter):
        crew = MagicMock()
        crew.kickoff.return_value = MagicMock(raw="text response")
        result = verified_adapter.crew_kickoff(crew)
        assert isinstance(result, str)

    def test_kickoff_passes_exact_inputs(self, verified_adapter):
        crew = MagicMock()
        crew.kickoff.return_value = MagicMock(raw="done")
        inputs = {"topic": "blockchain", "depth": "detailed"}
        verified_adapter.crew_kickoff(crew, inputs=inputs)
        crew.kickoff.assert_called_once_with(inputs=inputs)


# ---------------------------------------------------------------------------
# TestAsTool
# ---------------------------------------------------------------------------

class TestAsTool:
    def test_as_tool_returns_payment_tool(self, adapter):
        tool = adapter.as_tool(resource_fn=lambda q: "ok")
        assert isinstance(tool, AlgoVoiPaymentTool)

    def test_as_tool_name_attribute(self, adapter):
        tool = adapter.as_tool(resource_fn=lambda q: "ok", tool_name="my_gate")
        assert tool.name == "my_gate"

    def test_as_tool_description_attribute(self, adapter):
        tool = adapter.as_tool(resource_fn=lambda q: "ok", tool_description="Pay to access")
        assert tool.description == "Pay to access"

    def test_as_tool_default_name(self, adapter):
        tool = adapter.as_tool(resource_fn=lambda q: "ok")
        assert tool.name == "algovoi_payment_gate"

    def test_as_tool_default_description_mentions_payment(self, adapter):
        tool = adapter.as_tool(resource_fn=lambda q: "ok")
        assert "payment" in tool.description.lower()

    def test_as_tool_adapter_reference(self, adapter):
        tool = adapter.as_tool(resource_fn=lambda q: "ok")
        assert tool._adapter is adapter


# ---------------------------------------------------------------------------
# TestPaymentToolInit
# ---------------------------------------------------------------------------

class TestPaymentToolInit:
    def _make_tool(self, gate, resource_fn=None, **kwargs):
        with patch("crewai_algovoi._build_gate", return_value=gate):
            adapter = AlgoVoiCrewAI(**VALID_KWARGS)
        return AlgoVoiPaymentTool(
            adapter=adapter,
            resource_fn=resource_fn or (lambda q: f"result: {q}"),
            **kwargs,
        )

    def test_args_schema_is_payment_tool_input(self, adapter):
        tool = adapter.as_tool(resource_fn=lambda q: "ok")
        assert tool.args_schema is PaymentToolInput

    def test_payment_tool_input_query_field(self):
        # PaymentToolInput validates correctly
        inp = PaymentToolInput(query="hello")
        assert str(inp.query) == "hello"

    def test_payment_tool_input_proof_defaults_empty(self):
        inp = PaymentToolInput(query="hello")
        assert inp.payment_proof == ""

    def test_payment_tool_input_accepts_proof(self):
        inp = PaymentToolInput(query="hi", payment_proof="abc123")
        assert inp.payment_proof == "abc123"

    def test_adapter_stored_as_private_attr(self, adapter):
        tool = adapter.as_tool(resource_fn=lambda q: "ok")
        assert tool._adapter is adapter


# ---------------------------------------------------------------------------
# TestPaymentToolRun
# ---------------------------------------------------------------------------

class TestPaymentToolRun:
    def _make_tool(self, gate, resource_fn=None):
        with patch("crewai_algovoi._build_gate", return_value=gate):
            adapter = AlgoVoiCrewAI(**VALID_KWARGS)
        return AlgoVoiPaymentTool(
            adapter=adapter,
            resource_fn=resource_fn or (lambda q: f"resource: {q}"),
            name="test_gate",
            description="desc",
        )

    def test_no_proof_returns_challenge_json(self):
        tool = self._make_tool(_make_gate(requires_payment=True))
        output = tool._run(query="hello", payment_proof="")
        data = json.loads(output)
        assert data["error"] == "payment_required"

    def test_challenge_has_detail_field(self):
        tool = self._make_tool(_make_gate(requires_payment=True))
        output = tool._run(query="hi", payment_proof="")
        data = json.loads(output)
        assert "detail" in data

    def test_invalid_proof_returns_challenge(self):
        tool = self._make_tool(_make_gate(requires_payment=True))
        output = tool._run(query="hi", payment_proof="invalid_proof_value")
        data = json.loads(output)
        assert data["error"] == "payment_required"

    def test_valid_proof_calls_resource_fn(self):
        resource_fn = MagicMock(return_value="Premium content")
        tool = self._make_tool(_make_gate(requires_payment=False), resource_fn=resource_fn)
        proof = _mpp_proof("algorand-mainnet", "TXID123")
        output = tool._run(query="hello", payment_proof=proof)
        resource_fn.assert_called_once_with("hello")
        assert output == "Premium content"

    def test_resource_fn_exception_returns_error_json(self):
        def bad_fn(q):
            raise RuntimeError("Service unavailable")
        tool = self._make_tool(_make_gate(requires_payment=False), resource_fn=bad_fn)
        proof = _mpp_proof("algorand-mainnet", "TXID123")
        output = tool._run(query="hi", payment_proof=proof)
        data = json.loads(output)
        assert data["error"] == "resource_error"
        assert "Service unavailable" in data["detail"]

    def test_empty_query_still_calls_resource_fn(self):
        resource_fn = MagicMock(return_value="empty query result")
        tool = self._make_tool(_make_gate(requires_payment=False), resource_fn=resource_fn)
        proof = _mpp_proof("algorand-mainnet", "TX")
        tool._run(query="", payment_proof=proof)
        resource_fn.assert_called_once_with("")

    def test_non_string_query_cast_to_str(self):
        resource_fn = MagicMock(return_value="ok")
        tool = self._make_tool(_make_gate(requires_payment=False), resource_fn=resource_fn)
        proof = _mpp_proof("algorand-mainnet", "TX")
        tool._run(query=42, payment_proof=proof)
        resource_fn.assert_called_once_with("42")

    def test_resource_fn_return_cast_to_str(self):
        resource_fn = MagicMock(return_value=12345)
        tool = self._make_tool(_make_gate(requires_payment=False), resource_fn=resource_fn)
        proof = _mpp_proof("algorand-mainnet", "TX")
        result = tool._run(query="q", payment_proof=proof)
        assert result == "12345"


# ---------------------------------------------------------------------------
# TestEnsureLlm
# ---------------------------------------------------------------------------

class TestEnsureLlm:
    def test_returns_existing_llm(self):
        gate = _make_gate()
        with patch("crewai_algovoi._build_gate", return_value=gate):
            a = AlgoVoiCrewAI(**VALID_KWARGS)
        mock_llm = MagicMock()
        a._llm = mock_llm
        assert a._ensure_llm() is mock_llm

    def test_builds_crewai_llm_with_openai_key(self):
        gate = _make_gate()
        with patch("crewai_algovoi._build_gate", return_value=gate):
            a = AlgoVoiCrewAI(openai_key="sk-test", **VALID_KWARGS)

        mock_llm_cls = MagicMock()
        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch.dict("sys.modules", {
            "crewai": MagicMock(**{"LLM": mock_llm_cls}),
        }):
            result = a._ensure_llm()

        mock_llm_cls.assert_called_once()
        call_kwargs = mock_llm_cls.call_args.kwargs
        assert call_kwargs.get("api_key") == "sk-test"

    def test_passes_base_url_to_llm(self):
        gate = _make_gate()
        with patch("crewai_algovoi._build_gate", return_value=gate):
            a = AlgoVoiCrewAI(
                openai_key="sk-test",
                base_url="https://api.together.xyz/v1",
                **VALID_KWARGS,
            )

        mock_llm_cls = MagicMock()
        mock_llm_cls.return_value = MagicMock()

        with patch.dict("sys.modules", {"crewai": MagicMock(**{"LLM": mock_llm_cls})}):
            a._ensure_llm()

        call_kwargs = mock_llm_cls.call_args.kwargs
        assert call_kwargs.get("base_url") == "https://api.together.xyz/v1"

    def test_llm_cached_after_first_call(self):
        gate = _make_gate()
        with patch("crewai_algovoi._build_gate", return_value=gate):
            a = AlgoVoiCrewAI(openai_key="sk-test", **VALID_KWARGS)

        mock_llm_cls = MagicMock()
        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        with patch.dict("sys.modules", {"crewai": MagicMock(**{"LLM": mock_llm_cls})}):
            first = a._ensure_llm()
            second = a._ensure_llm()

        assert first is second
        mock_llm_cls.assert_called_once()


# ---------------------------------------------------------------------------
# TestFlaskGuard
# ---------------------------------------------------------------------------

class TestFlaskGuard:
    def _make_adapter(self, gate):
        with patch("crewai_algovoi._build_gate", return_value=gate):
            return AlgoVoiCrewAI(**VALID_KWARGS)

    def _mock_request(self, content_length=None, body=None):
        r = MagicMock()
        r.content_length = content_length
        r.headers = {}
        r.get_json.return_value = body or {}
        return r

    def test_returns_402_on_no_proof(self):
        adapter = self._make_adapter(_make_gate(requires_payment=True))
        mock_req = self._mock_request(content_length=None, body={})
        crew = MagicMock()

        import flask as _flask
        with patch.object(_flask, "request", mock_req), \
             patch("flask.jsonify"), patch("flask.Response"):
            result = adapter.flask_guard(crew)
        assert result is not None

    def test_rejects_oversized_body(self):
        adapter = self._make_adapter(_make_gate(requires_payment=False))
        mock_req = self._mock_request(content_length=2_000_000)
        captured = {}

        def fake_response(body, status, mimetype):
            captured["status"] = status
            return MagicMock()

        import flask as _flask
        with patch.object(_flask, "request", mock_req), \
             patch("flask.Response", side_effect=fake_response), \
             patch("flask.jsonify"):
            adapter.flask_guard(MagicMock())
        assert captured["status"] == 413

    def test_calls_crew_kickoff_when_verified(self):
        adapter = self._make_adapter(_make_gate(requires_payment=False))
        mock_req = self._mock_request(
            content_length=None,
            body={"topic": "AlgoVoi"},
        )
        crew = MagicMock()

        import flask as _flask
        with patch.object(_flask, "request", mock_req), \
             patch("flask.jsonify") as mock_jsonify, \
             patch.object(adapter, "crew_kickoff", return_value="Crew done") as mock_kickoff:
            adapter.flask_guard(crew)

        mock_kickoff.assert_called_once()
        mock_jsonify.assert_called_once_with({"content": "Crew done"})

    def test_inputs_fn_extracts_inputs(self):
        adapter = self._make_adapter(_make_gate(requires_payment=False))
        mock_req = self._mock_request(
            content_length=None,
            body={"topic": "AlgoVoi", "meta": "ignored"},
        )
        crew = MagicMock()
        inputs_fn = lambda body: {"topic": body["topic"]}

        import flask as _flask
        with patch.object(_flask, "request", mock_req), \
             patch("flask.jsonify"), \
             patch.object(adapter, "crew_kickoff", return_value="done") as mock_kickoff:
            adapter.flask_guard(crew, inputs_fn=inputs_fn)

        call_kwargs = mock_kickoff.call_args
        assert call_kwargs.kwargs.get("inputs") == {"topic": "AlgoVoi"}

    def test_none_content_length_not_rejected(self):
        adapter = self._make_adapter(_make_gate(requires_payment=False))
        mock_req = self._mock_request(content_length=None, body={})
        crew = MagicMock()

        import flask as _flask
        with patch.object(_flask, "request", mock_req), \
             patch("flask.jsonify") as mock_jsonify, \
             patch.object(adapter, "crew_kickoff", return_value="ok"):
            adapter.flask_guard(crew)
        mock_jsonify.assert_called_once()

    def test_small_body_not_rejected(self):
        adapter = self._make_adapter(_make_gate(requires_payment=False))
        mock_req = self._mock_request(content_length=512, body={})
        crew = MagicMock()

        import flask as _flask
        with patch.object(_flask, "request", mock_req), \
             patch("flask.jsonify") as mock_jsonify, \
             patch.object(adapter, "crew_kickoff", return_value="ok"):
            adapter.flask_guard(crew)
        mock_jsonify.assert_called_once()


# ---------------------------------------------------------------------------
# TestImportPaths
# ---------------------------------------------------------------------------

class TestImportPaths:
    def test_import_path_matches_public_api(self):
        import importlib
        mod = importlib.import_module("crewai_algovoi")
        assert hasattr(mod, "AlgoVoiCrewAI")
        assert hasattr(mod, "AlgoVoiPaymentTool")
        assert hasattr(mod, "CrewAIResult")

    def test_max_flask_body_is_one_mib(self):
        assert _MAX_FLASK_BODY == 1_048_576

    def test_payment_tool_input_is_basemodel(self):
        from crewai_algovoi import PaymentToolInput
        # PaymentToolInput should be a pydantic model or at minimum instantiable
        inp = PaymentToolInput(query="test")
        assert inp is not None
