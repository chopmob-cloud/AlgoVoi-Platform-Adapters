"""
Pydantic v2 strict-mode input schemas for all 8 tools.

Follows §4.1 of ALGOVOI_MCP.md — every tool handler validates its arguments
through a ``BaseModel`` with ``strict=True`` and ``extra='forbid'`` before any
business logic runs.  Unknown / mistyped fields are rejected with a clear
``ValidationError`` instead of silently passing into the AlgoVoi API.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .networks import NETWORKS

_STRICT = ConfigDict(strict=True, extra="forbid")

NetworkLiteral  = Literal[
    # Mainnet
    "algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet",
    "base_mainnet", "solana_mainnet", "tempo_mainnet",
    "algorand_mainnet_algo", "voi_mainnet_voi", "hedera_mainnet_hbar", "stellar_mainnet_xlm",
    "base_mainnet_eth", "solana_mainnet_sol",
    # Testnet
    "algorand_testnet", "voi_testnet", "hedera_testnet", "stellar_testnet",
    "base_sepolia", "tempo_testnet", "solana_devnet",
    "algorand_testnet_algo", "voi_testnet_voi", "hedera_testnet_hbar", "stellar_testnet_xlm",
    "solana_devnet_sol",
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


class FetchAgentCardInput(BaseModel):
    model_config = _STRICT
    agent_url: str = Field(min_length=10, max_length=2048)

    @field_validator("agent_url")
    @classmethod
    def _must_be_https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError('"agent_url" must start with https://')
        return v


class SendA2aMessageInput(BaseModel):
    model_config = _STRICT
    agent_url:     str           = Field(min_length=10, max_length=2048)
    text:          str           = Field(min_length=1,  max_length=4096)
    payment_proof: Optional[str] = Field(default=None, min_length=1, max_length=4096)
    message_id:    Optional[str] = Field(default=None, min_length=1, max_length=64)

    @field_validator("agent_url")
    @classmethod
    def _must_be_https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError('"agent_url" must start with https://')
        return v


# ── Tier 2 — Standing-Authority Recurring Payments ───────────────────────────

# 14 chain ids matching native-* / TS MCP / -Hand SDK.
RecurringNetworkLiteral = Literal[
    "algorand_mainnet", "algorand_testnet",
    "voi_mainnet",      "voi_testnet",
    "base_mainnet",     "base_sepolia",
    "tempo_mainnet",    "tempo_testnet",
    "solana_mainnet",   "solana_devnet",
    "hedera_mainnet",   "hedera_testnet",
    "stellar_mainnet",  "stellar_testnet",
]

# 8 webhook event types in addition to Tier 1's payment.* events.
RECURRING_EVENT_TYPES: tuple[str, ...] = (
    "recurring.authority_created",
    "recurring.authority_activated",
    "recurring.authority_paused",
    "recurring.authority_resumed",
    "recurring.authority_revoked",
    "recurring.authority_expired",
    "subscription.charged",
    "subscription.payment_failed",
)


class CreateRecurringAuthorityInput(BaseModel):
    """Input for create_recurring_authority — opens a Tier 2 standing authority.

    Stellar uses 7-decimal precision for USDC; every other chain uses 6.
    Pass ``cap_amount_minor`` in chain-native atomic units.
    """

    model_config = _STRICT
    subscription_id:        str  = Field(min_length=1, max_length=36)
    chain:                  RecurringNetworkLiteral
    customer_wallet_address: str = Field(min_length=1, max_length=200)
    cap_amount_minor:       int  = Field(gt=0)
    cap_period_seconds:     int  = Field(ge=86_400)
    per_cycle_amount_minor: int  = Field(gt=0)
    asset:                  Optional[str] = Field(default=None, min_length=1, max_length=16)
    metadata:               Optional[dict] = None

    @field_validator("per_cycle_amount_minor")
    @classmethod
    def _per_cycle_le_cap(cls, v: int, info) -> int:
        cap = info.data.get("cap_amount_minor")
        if cap is not None and v > cap:
            raise ValueError(
                '"per_cycle_amount_minor" cannot exceed "cap_amount_minor"',
            )
        return v


class GetAuthorityInput(BaseModel):
    model_config = _STRICT
    authority_id: str = Field(min_length=1, max_length=36)


class ListAuthoritiesInput(BaseModel):
    model_config = _STRICT
    subscription_id: Optional[str] = Field(default=None, min_length=1, max_length=36)
    status:          Optional[str] = Field(default=None, min_length=1, max_length=32)
    limit:           Optional[int] = Field(default=None, ge=1, le=200)
    offset:          Optional[int] = Field(default=None, ge=0)

    @field_validator("status")
    @classmethod
    def _status_alnum_underscore(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not all(c.isalnum() or c == "_" for c in v):
            raise ValueError('"status" must be alphanumeric / underscore')
        return v


class ConfirmAuthorityInput(BaseModel):
    model_config = _STRICT
    authority_id:       str  = Field(min_length=1, max_length=36)
    on_chain_address:   str  = Field(min_length=1, max_length=200)
    first_cycle_due_at: Optional[str] = Field(default=None, min_length=1, max_length=64)


class RevokeAuthorityInput(BaseModel):
    model_config = _STRICT
    authority_id: str = Field(min_length=1, max_length=36)


class PauseAuthorityInput(BaseModel):
    model_config = _STRICT
    authority_id: str = Field(min_length=1, max_length=36)


class ResumeAuthorityInput(BaseModel):
    model_config = _STRICT
    authority_id:      str  = Field(min_length=1, max_length=36)
    next_cycle_due_at: Optional[str] = Field(default=None, min_length=1, max_length=64)


class ManualPullInput(BaseModel):
    model_config = _STRICT
    authority_id:    str  = Field(min_length=1, max_length=36)
    amount_minor:    int  = Field(gt=0)
    idempotency_key: Optional[str] = Field(default=None, min_length=1, max_length=128)


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
    "fetch_agent_card":          FetchAgentCardInput,
    "send_a2a_message":          SendA2aMessageInput,
    # Tier 2 — Standing-Authority Recurring Payments (added v1.3.0)
    "create_recurring_authority": CreateRecurringAuthorityInput,
    "get_authority":              GetAuthorityInput,
    "list_authorities":           ListAuthoritiesInput,
    "confirm_authority":          ConfirmAuthorityInput,
    "revoke_authority":           RevokeAuthorityInput,
    "pause_authority":            PauseAuthorityInput,
    "resume_authority":           ResumeAuthorityInput,
    "manual_pull":                ManualPullInput,
}

# Sanity check at import time — if anyone adds a new tool without the matching
# schema, this surfaces immediately rather than at tool-call time.
_EXPECTED = set(SCHEMAS_BY_TOOL.keys())
assert len(_EXPECTED) == 21, f"expected 21 tool schemas, got {len(_EXPECTED)}"
# Cross-check each schema's network fields against the canonical NETWORKS tuple.
for _n in (
    "algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet",
    "base_mainnet", "solana_mainnet", "tempo_mainnet",
    "algorand_mainnet_algo", "voi_mainnet_voi", "hedera_mainnet_hbar", "stellar_mainnet_xlm",
    "base_mainnet_eth", "solana_mainnet_sol",
    "algorand_testnet", "voi_testnet", "hedera_testnet", "stellar_testnet",
    "base_sepolia", "tempo_testnet", "solana_devnet",
    "algorand_testnet_algo", "voi_testnet_voi", "hedera_testnet_hbar", "stellar_testnet_xlm",
    "solana_devnet_sol",
):
    assert _n in NETWORKS, f"network {_n!r} not in networks.NETWORKS"
