"""
AlgoVoi Bedrock Adapter

Payment-gate the Amazon Bedrock API using x402, MPP, or AP2
— paid in USDC on Algorand, VOI, Hedera, or Stellar.

Usage:
    from bedrock_algovoi import AlgoVoiBedrock

    gate = AlgoVoiBedrock(
        aws_access_key_id     = "AKIA...",
        aws_secret_access_key = "wJal...",
        aws_region            = "us-east-1",
        algovoi_key           = "algv_...",
        tenant_id             = "your-tenant-uuid",
        payout_address        = "YOUR_ALGORAND_ADDRESS",
        protocol              = "mpp",               # "mpp" | "ap2" | "x402"
        network               = "algorand-mainnet",
        amount_microunits     = 10000,               # 0.01 USDC per call
    )

    # Flask
    @app.route("/ai/chat", methods=["POST"])
    def chat():
        result = gate.check(dict(request.headers), request.get_json())
        if result.requires_payment:
            return result.as_flask_response()
        return jsonify({"content": gate.complete(request.json["messages"])})

    # FastAPI
    @app.post("/ai/chat")
    async def chat(req: Request):
        body = await req.json()
        result = gate.check(dict(req.headers), body)
        if result.requires_payment:
            status, headers, body_bytes = result.as_wsgi_response()
            return Response(body_bytes, status_code=402, headers=dict(headers))
        return {"content": gate.complete(body["messages"])}

Messages (OpenAI format — system role extracted automatically):
    [
        {"role": "system",    "content": "You are a helpful assistant."},
        {"role": "user",      "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
        {"role": "user",      "content": "What can you do?"},
    ]

Models:
    amazon.nova-pro-v1:0                         (Amazon Nova Pro — default)
    amazon.nova-lite-v1:0                        (Amazon Nova Lite — fast)
    anthropic.claude-3-5-sonnet-20241022-v2:0    (Claude 3.5 Sonnet via Bedrock)
    meta.llama3-70b-instruct-v1:0                (Meta Llama 3 70B)
    amazon.titan-text-premier-v1:0               (Amazon Titan Premier)

AWS credentials:
    Pass directly OR set environment variables:
        AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION

Networks:
    "algorand-mainnet"  USDC  (ASA 31566704)
    "voi-mainnet"       aUSDC (ARC200 302190)
    "hedera-mainnet"    USDC  (HTS 0.0.456858)
    "stellar-mainnet"   USDC  (Circle)

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Licensed under the Business Source License 1.1 — see LICENSE for details.

Version: 1.1.0
"""

from __future__ import annotations

import os
import sys
import json
from typing import Any, Optional

__version__ = "1.1.0"

_API_BASE = "https://api1.ilovechicken.co.uk"

NETWORKS = [
    "algorand-mainnet",
    "voi-mainnet",
    "hedera-mainnet",
    "stellar-mainnet",
    "base-mainnet",
    "solana-mainnet",
    "tempo-mainnet",
]

PROTOCOLS = ["x402", "mpp", "ap2"]

_SNAKE = {
    "algorand-mainnet": "algorand_mainnet",
    "voi-mainnet":      "voi_mainnet",
    "hedera-mainnet":   "hedera_mainnet",
    "stellar-mainnet":  "stellar_mainnet",
    "base-mainnet":     "base_mainnet",
    "solana-mainnet":   "solana_mainnet",
    "tempo-mainnet":    "tempo_mainnet",
}

MODELS = [
    "amazon.nova-pro-v1:0",
    "amazon.nova-lite-v1:0",
    "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "meta.llama3-70b-instruct-v1:0",
    "amazon.titan-text-premier-v1:0",
]

_ADAPTERS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _add_path(subdir: str) -> None:
    p = os.path.join(_ADAPTERS_ROOT, subdir)
    if p not in sys.path:
        sys.path.insert(0, p)


# ── Result wrapper ────────────────────────────────────────────────────────────

class BedrockAiResult:
    """
    Unified payment check result for all three protocols.

    Attributes:
        requires_payment: True if caller must pay before proceeding
        receipt:          MppReceipt on MPP success (.payer, .tx_id, .amount)
        mandate:          Ap2Mandate on AP2 success (.payer_address, .network, .tx_id)
        error:            Error string if verification failed
    """

    def __init__(self, inner: Any):
        self._inner = inner
        self.requires_payment: bool = inner.requires_payment
        self.receipt  = getattr(inner, "receipt",  None)
        self.mandate  = getattr(inner, "mandate",  None)
        self.error: Optional[str] = getattr(inner, "error", None)

    def as_flask_response(self) -> tuple:
        if hasattr(self._inner, "as_flask_response"):
            return self._inner.as_flask_response()
        if hasattr(self._inner, "as_wsgi_response"):
            _, wsgi_headers, body_bytes = self._inner.as_wsgi_response()
            return body_bytes.decode(), 402, dict(wsgi_headers)
        body = json.dumps({"error": "Payment Required", "detail": self.error or ""})
        return body, 402, {"Content-Type": "application/json"}

    def as_wsgi_response(self) -> tuple[str, list, bytes]:
        if hasattr(self._inner, "as_wsgi_response"):
            return self._inner.as_wsgi_response()
        body = json.dumps({"error": "Payment Required", "detail": self.error or ""}).encode()
        return "402 Payment Required", [("Content-Type", "application/json")], body


# ── Gate factory ──────────────────────────────────────────────────────────────

def _build_gate(
    protocol: str,
    algovoi_key: str,
    tenant_id: str,
    payout_address: str,
    network: str,
    amount_microunits: int,
    resource_id: str,
) -> Any:
    if network not in NETWORKS:
        raise ValueError(f"network must be one of {NETWORKS} — got {network!r}")
    if protocol not in PROTOCOLS:
        raise ValueError(f"protocol must be one of {PROTOCOLS} — got {protocol!r}")

    if protocol == "x402":
        _add_path("ai-adapters/openai")
        from openai_algovoi import _X402Gate  # type: ignore
        return _X402Gate(
            api_base=_API_BASE, api_key=algovoi_key, tenant_id=tenant_id,
            payout_address=payout_address, network=network,
            amount_microunits=amount_microunits,
        )

    if protocol == "mpp":
        _add_path("mpp-adapter")
        from mpp import MppGate  # type: ignore
        return MppGate(
            api_base=_API_BASE, api_key=algovoi_key, tenant_id=tenant_id,
            resource_id=resource_id, payout_address=payout_address,
            networks=[_SNAKE[network]], amount_microunits=amount_microunits,
        )

    if protocol == "ap2":
        _add_path("ap2-adapter")
        from ap2 import Ap2Gate  # type: ignore
        return Ap2Gate(
            merchant_id=tenant_id, api_base=_API_BASE, api_key=algovoi_key,
            tenant_id=tenant_id, payout_address=payout_address,
            networks=[network], amount_microunits=amount_microunits,
        )


# ── Main adapter ──────────────────────────────────────────────────────────────

class AlgoVoiBedrock:
    """
    Payment-gated wrapper for the Amazon Bedrock Converse API.

    Supports x402, MPP, and AP2 payment protocols across
    Algorand, VOI, Hedera, and Stellar.

    Accepts any model available in your AWS account via the Bedrock
    Converse API, including Amazon Nova, Claude, Llama, and Titan.
    """

    def __init__(
        self,
        aws_access_key_id:     Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_region:            str = "us-east-1",
        algovoi_key:           str = "",
        tenant_id:             str = "",
        payout_address:        str = "",
        protocol:              str = "mpp",
        network:               str = "algorand-mainnet",
        amount_microunits:     int = 10000,
        model:                 str = "amazon.nova-pro-v1:0",
        max_tokens:            int = 1024,
        resource_id:           str = "ai-chat",
    ):
        """
        Args:
            aws_access_key_id:     AWS access key (or set AWS_ACCESS_KEY_ID env var)
            aws_secret_access_key: AWS secret key (or set AWS_SECRET_ACCESS_KEY env var)
            aws_region:            AWS region where Bedrock is enabled (default: us-east-1)
            algovoi_key:           AlgoVoi API key (algv_...)
            tenant_id:             AlgoVoi tenant UUID
            payout_address:        On-chain address to receive payments
            protocol:              Payment protocol — "mpp", "ap2", or "x402"
            network:               Chain — "algorand-mainnet", "voi-mainnet",
                                   "hedera-mainnet", or "stellar-mainnet"
            amount_microunits:     Price per call in USDC microunits (10000 = 0.01 USDC)
            model:                 Bedrock model ID (default: amazon.nova-pro-v1:0)
            max_tokens:            Max tokens in response (default: 1024)
            resource_id:           Resource identifier used in MPP challenges
        """
        self._aws_key    = aws_access_key_id
        self._aws_secret = aws_secret_access_key
        self._aws_region = aws_region
        self._model      = model
        self._max_tokens = max_tokens
        self._gate       = _build_gate(
            protocol, algovoi_key, tenant_id, payout_address,
            network, amount_microunits, resource_id,
        )

    # ── Payment check ─────────────────────────────────────────────────────────

    def check(self, headers: dict, body: Optional[dict] = None) -> BedrockAiResult:
        """
        Check a request for valid payment credentials.

        Returns BedrockAiResult. If result.requires_payment is True, return
        result.as_flask_response() or result.as_wsgi_response() immediately.
        """
        try:
            inner = self._gate.check(headers, body)
        except TypeError:
            inner = self._gate.check(headers)
        return BedrockAiResult(inner)

    # ── AI completion ─────────────────────────────────────────────────────────

    def complete(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        """
        Call the Bedrock Converse API and return the response text.

        Args:
            messages:   OpenAI-format message list — system role extracted automatically
                        [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
            model:      Override the default model ID
            max_tokens: Override the default max_tokens
            **kwargs:   Additional inferenceConfig params (temperature, topP, etc.)

        Returns:
            The assistant's reply as a plain string.
        """
        try:
            import boto3  # type: ignore
        except ImportError:
            raise ImportError("The boto3 package is required: pip install boto3")

        # Extract system prompt; build Bedrock-format message list
        system_text: Optional[str] = None
        bedrock_messages: list[dict] = []
        for m in messages:
            role    = m.get("role", "")
            content = m.get("content", "")
            if role == "system":
                system_text = content
            elif role in ("user", "assistant"):
                bedrock_messages.append({
                    "role":    role,
                    "content": [{"text": content}],
                })

        # Build boto3 client — uses env vars if keys not passed explicitly
        client_kwargs: dict[str, Any] = {"region_name": self._aws_region}
        if self._aws_key:
            client_kwargs["aws_access_key_id"] = self._aws_key
        if self._aws_secret:
            client_kwargs["aws_secret_access_key"] = self._aws_secret

        client = boto3.client("bedrock-runtime", **client_kwargs)

        # Build inference config
        inference_config: dict[str, Any] = {
            "maxTokens": max_tokens or self._max_tokens,
        }
        for k in ("temperature", "topP", "stopSequences"):
            if k in kwargs:
                inference_config[k] = kwargs.pop(k)

        converse_kwargs: dict[str, Any] = {
            "modelId":         model or self._model,
            "messages":        bedrock_messages,
            "inferenceConfig": inference_config,
        }
        if system_text:
            converse_kwargs["system"] = [{"text": system_text}]

        resp = client.converse(**converse_kwargs)
        return resp["output"]["message"]["content"][0]["text"]

    # ── Flask convenience ─────────────────────────────────────────────────────

    def flask_guard(
        self,
        messages_key: str = "messages",
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ):
        """
        Flask route handler — checks payment then calls Bedrock.

        Usage:
            @app.route("/ai/chat", methods=["POST"])
            def chat():
                return gate.flask_guard()
        """
        from flask import request, jsonify, Response  # type: ignore

        body   = request.get_json(silent=True) or {}
        result = self.check(dict(request.headers), body)
        if result.requires_payment:
            flask_body, status, headers = result.as_flask_response()
            return Response(flask_body, status=status, headers=headers,
                            mimetype="application/json")
        messages = body.get(messages_key, [])
        content  = self.complete(messages, model=model, max_tokens=max_tokens, **kwargs)
        return jsonify({"content": content})
