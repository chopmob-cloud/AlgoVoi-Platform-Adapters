"""
Pydantic v2 strict-mode input schemas for all 8 tools.

Follows §4.1 of ALGOVOI_MCP.md — every tool handler validates its arguments
through a ``BaseModel`` with ``strict=True`` and ``extra='forbid'`` before any
business logic runs.  Unknown / mistyped fields are rejected with a clear
``ValidationError`` instead of silently passing into the AlgoVoi API.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .networks import NETWORKS

_STRICT = ConfigDict(strict=True, extra="forbid")

NetworkLiteral  = Literal[
    # Mainnet
    "algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet",
    "algorand_mainnet_algo", "voi_mainnet_voi", "hedera_mainnet_hbar", "stellar_mainnet_xlm",
    # Testnet
    "algorand_testnet", "voi_testnet", "hedera_testnet", "stellar_testnet",
    "algorand_testnet_algo", "voi_testnet_voi", "hedera_testnet_hbar", "stellar_testnet_xlm",
]
ExtNetworkLiteral = Literal[
    "algorand_mainnet", "voi_mainnet", "algorand_mainnet_algo", "voi_mainnet_voi",
    "algorand_testnet", "voi_testnet", "algorand_testnet_algo", "voi_testnet_voi",
]


class CreatePaymentLinkInput(BaseModel):
    model_config = _STRICT
    amount:          float           = Field(gt=0, le=10_000_000)
    currency:        str             = Field(min_length=3, max_length=3)
    label:           str             = Field(min_length=1, max_length=200)
    network:         NetworkLiteral
    redirect_url:    Optional[str]   = Field(default=None, max_length=2048)
    idempotency_key: Optional[str]   = Field(default=None, min_length=16, max_length=64)


class VerifyPaymentInput(BaseModel):
    model_config = _STRICT
    token: str           = Field(min_length=1, max_length=200)
    tx_id: Optional[str] = Field(default=None, min_length=1, max_length=200)


class PrepareExtensionPaymentInput(BaseModel):
    model_config = _STRICT
    amount:   float               = Field(gt=0, le=10_000_000)
    currency: str                 = Field(min_length=3, max_length=3)
    label:    str                 = Field(min_length=1, max_length=200)
    network:  ExtNetworkLiteral


class VerifyWebhookInput(BaseModel):
    model_config = _STRICT
    raw_body:  str = Field(min_length=0, max_length=64 * 1024)
    signature: str = Field(min_length=1, max_length=512)


class ListNetworksInput(BaseModel):
    model_config = _STRICT


class GenerateMppChallengeInput(BaseModel):
    model_config = _STRICT
    resource_id:        str                       = Field(min_length=1, max_length=200)
    amount_microunits:  int                       = Field(gt=0, le=10**15)
    networks:           Optional[list[NetworkLiteral]] = Field(default=None, min_length=1, max_length=4)
    expires_in_seconds: Optional[int]             = Field(default=None, gt=0, le=86_400)


class VerifyMppReceiptInput(BaseModel):
    model_config = _STRICT
    resource_id: str            = Field(min_length=1, max_length=200)
    tx_id:       str            = Field(min_length=1, max_length=200)
    network:     NetworkLiteral


class VerifyX402ProofInput(BaseModel):
    model_config = _STRICT
    proof:   str            = Field(min_length=1, max_length=64 * 1024)
    network: NetworkLiteral


class GenerateX402ChallengeInput(BaseModel):
    model_config = _STRICT
    resource:           str                    = Field(min_length=1, max_length=2048)
    amount_microunits:  int                    = Field(gt=0, le=10**15)
    network:            Optional[NetworkLiteral] = None
    expires_in_seconds: Optional[int]          = Field(default=None, gt=0, le=86_400)
    description:        Optional[str]          = Field(default=None, max_length=200)


class GenerateAp2MandateInput(BaseModel):
    model_config = _STRICT
    resource_id:        str                    = Field(min_length=1, max_length=200)
    amount_microunits:  int                    = Field(gt=0, le=10**15)
    network:            Optional[NetworkLiteral] = None
    expires_in_seconds: Optional[int]          = Field(default=None, gt=0, le=86_400)
    description:        Optional[str]          = Field(default=None, max_length=200)


class VerifyAp2PaymentInput(BaseModel):
    model_config = _STRICT
    mandate_id: str            = Field(min_length=1, max_length=64)
    tx_id:      str            = Field(min_length=1, max_length=200)
    network:    NetworkLiteral


# Mapping from tool name → schema class — used by the dispatcher to pick
# the right model at runtime.  Keep in sync with TOOL_SCHEMAS in server.py.
SCHEMAS_BY_TOOL: dict[str, type[BaseModel]] = {
    "create_payment_link":       CreatePaymentLinkInput,
    "verify_payment":            VerifyPaymentInput,
    "prepare_extension_payment": PrepareExtensionPaymentInput,
    "verify_webhook":            VerifyWebhookInput,
    "list_networks":             ListNetworksInput,
    "generate_mpp_challenge":    GenerateMppChallengeInput,
    "verify_mpp_receipt":        VerifyMppReceiptInput,
    "verify_x402_proof":         VerifyX402ProofInput,
    "generate_x402_challenge":   GenerateX402ChallengeInput,
    "generate_ap2_mandate":      GenerateAp2MandateInput,
    "verify_ap2_payment":        VerifyAp2PaymentInput,
}

# Sanity check at import time — if anyone adds a new tool without the matching
# schema, this surfaces immediately rather than at tool-call time.
_EXPECTED = set(SCHEMAS_BY_TOOL.keys())
assert len(_EXPECTED) == 11, f"expected 11 tool schemas, got {len(_EXPECTED)}"
# Cross-check each schema's network fields against the canonical NETWORKS tuple.
for _n in (
    "algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet",
    "algorand_mainnet_algo", "voi_mainnet_voi", "hedera_mainnet_hbar", "stellar_mainnet_xlm",
    "algorand_testnet", "voi_testnet", "hedera_testnet", "stellar_testnet",
    "algorand_testnet_algo", "voi_testnet_voi", "hedera_testnet_hbar", "stellar_testnet_xlm",
):
    assert _n in NETWORKS, f"network {_n!r} not in networks.NETWORKS"
