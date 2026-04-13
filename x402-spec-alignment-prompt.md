# x402 Spec Alignment — API Server Brief

## Context

AlgoVoi's x402 implementation was validated against the official spec at
github.com/coinbase/x402 and docs.cdp.coinbase.com/x402/docs/welcome.

The implementation works end-to-end within AlgoVoi's ecosystem (smoke-tested
with real payments on Algorand, VOI, Stellar, and Hedera mainnet on 13 Apr 2026).
However, the payload formats diverge from the spec, making AlgoVoi's x402
non-interoperable with any standard x402 client built against the Coinbase spec.

This brief describes exactly what needs to change on the gateway/API server
to achieve spec compliance. A matching adapter update will be applied on the
client side (platform-adapters repo) once the server changes are deployed.

---

## What the Official x402 v1 Spec Requires

### 402 Response — X-PAYMENT-REQUIRED header (base64 JSON)

```json
{
  "x402Version": 1,
  "accepts": [
    {
      "scheme": "exact",
      "network": "<network-id>",
      "amount": "10000",
      "asset": "<asset-id>",
      "payTo": "<payout-address>",
      "maxTimeoutSeconds": 300,
      "extra": {
        "name": "USDC",
        "decimals": 6,
        "description": "AlgoVoi: <resource-path>"
      }
    }
  ],
  "resource": {
    "url": "<full-resource-url>",
    "description": "<human-readable-description>"
  }
}
```

Key points:
- `x402Version` is an **integer** (1), not a string like "x402/1"
- Payment options are wrapped in an `accepts` **array** (supports multiple chains/assets)
- `payTo` is **required** — agents must know where to send payment
- `amount` is a **string** of the asset's smallest unit (microunits for USDC: 1 USDC = 1000000)
- `asset` is the asset identifier (ASA ID for Algorand, contract address for EVM, etc.)

### X-PAYMENT header (base64 JSON) — submitted by the paying agent

```json
{
  "x402Version": 1,
  "scheme": "exact",
  "network": "<network-id>",
  "payload": {
    "signature": "<tx_id-or-checkout-token>",
    "authorization": {
      "from": "<payer-address>",
      "to": "<payTo-address>",
      "amount": "10000",
      "asset": "<asset-id>"
    }
  }
}
```

---

## Network Naming Convention for AlgoVoi Chains

The spec uses CAIP-2 style identifiers. Since Algorand, VOI, Stellar, and Hedera
are not yet in the official CAIP-2 registry, use the following AlgoVoi convention
which follows the CAIP-2 pattern (`namespace:reference`):

| Current wire format  | Proposed x402-spec-aligned ID     | Notes                          |
|----------------------|-----------------------------------|--------------------------------|
| `algorand-mainnet`   | `algorand:mainnet`                | Algorand mainnet               |
| `voi-mainnet`        | `voi:mainnet`                     | VOI network mainnet            |
| `stellar-mainnet`    | `stellar:pubnet`                  | Stellar public network (CAIP-2 |
| `hedera-mainnet`     | `hedera:mainnet`                  | Hedera mainnet                 |

---

## Current vs Required — What Needs to Change on the Server

### 1. Payment requirement format returned in X-PAYMENT-REQUIRED

**Current (AlgoVoi proprietary):**
```json
{
  "version": "x402/1",
  "network": "algorand_mainnet",
  "asset": "USDC",
  "amount": 0.01,
  "currency": "USD",
  "receiver": "",
  "memo": "<nonce>",
  "resource": "/api/inference",
  "description": "AlgoVoi: /api/inference",
  "expires_at": 1744390000
}
```

**Required (spec-compliant):**
```json
{
  "x402Version": 1,
  "accepts": [
    {
      "scheme": "exact",
      "network": "algorand:mainnet",
      "amount": "10000",
      "asset": "31566704",
      "payTo": "<tenant-payout-address>",
      "maxTimeoutSeconds": 300,
      "extra": {
        "name": "USDC",
        "decimals": 6,
        "payment_reference": "<tenant_id>:<resource_id>"
      }
    }
  ],
  "resource": {
    "url": "/api/inference",
    "description": "AlgoVoi: /api/inference"
  }
}
```

When a tenant has multiple networks enabled, include one entry per network in
the `accepts` array. The agent picks the one it can pay.

### 2. Asset identifiers per network

| Network           | x402 `asset` value                                      |
|-------------------|---------------------------------------------------------|
| `algorand:mainnet`| `31566704`  (USDC ASA ID)                              |
| `voi:mainnet`     | `302190`    (aUSDC ARC200 app ID)                      |
| `stellar:pubnet`  | `USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN` |
| `hedera:mainnet`  | `0.0.456858` (USDC HTS token)                          |

### 3. Payment proof verification (X-PAYMENT header)

The gateway's facilitator needs to accept the spec-format `X-PAYMENT` proof:

```json
{
  "x402Version": 1,
  "scheme": "exact",
  "network": "algorand:mainnet",
  "payload": {
    "signature": "<checkout-token-or-tx-id>",
    "authorization": {
      "from": "<payer-address>",
      "to": "<payTo-address>",
      "amount": "10000",
      "asset": "31566704"
    }
  }
}
```

The `signature` field carries the AlgoVoi checkout token (for the hosted checkout
flow) or the raw on-chain TX ID (for direct payment flow). The existing
`/checkout/{token}/status` endpoint can continue to power the verification —
the server just needs to extract `payload.signature` and call it.

### 4. X-PAYMENT-RECEIPT (optional but recommended)

After successful verification, return:
```
X-PAYMENT-RECEIPT: <base64 JSON>
```

```json
{
  "x402Version": 1,
  "payer": "<payer-address>",
  "network": "algorand:mainnet",
  "amount": "10000",
  "asset": "31566704",
  "tx_id": "<on-chain-tx-id>",
  "issued_at": 1744390000,
  "expires_at": 1744393600
}
```

---

## Migration Strategy — Backward Compatibility

During the transition, support **both** formats simultaneously:

1. **Incoming X-PAYMENT proofs**: accept both old format (`{x402Version:1, payload:{tx_id:...}}`)
   and new format (`{x402Version:1, payload:{signature:..., authorization:{...}}}`)
   — extract the token from whichever field is present.

2. **Outgoing X-PAYMENT-REQUIRED**: switch to spec format immediately — the
   client adapter will be updated in the same deploy window to generate and
   parse the new format.

3. **Version field**: if you see incoming `"version": "x402/1"` treat it as v1.
   Always emit `"x402Version": 1` going forward.

---

## What the Client Adapter Will Update (platform-adapters side)

Once the server changes are deployed, the following will be updated in
`x402-ai-agents/x402_agents_algovoi.py`:

- `create_payment_requirement` → emit `x402Version: 1`, `accepts` array, include `payTo`
- `decode_payment_requirement` → parse `accepts[0]` structure
- `build_payment_required_response` → same as above
- `verify_x402_payment` → read `payload.signature` instead of `payload.tx_id`
- Unit tests and smoke tests updated to match new format

The client update is ready to apply as soon as the server confirms it accepts
the new payment requirement format and the new proof format.

---

## Summary of Server Changes Required

| Change | Where | Priority |
|--------|-------|----------|
| Emit `x402Version: 1` integer (not `"version": "x402/1"`) | 402 response builder | High |
| Wrap payment option in `accepts: [...]` array | 402 response builder | High |
| Include `payTo` (tenant payout address) in accepts | 402 response builder | High |
| Use `amount` as string microunits (not float USD) | 402 response builder | High |
| Use `asset` as chain-native ID (not "USDC" string) | 402 response builder | High |
| Use `network` as `algorand:mainnet` style ID | 402 response builder | Medium |
| Accept `payload.signature` as alias for checkout token | Payment verifier | High |
| Emit `X-PAYMENT-RECEIPT` header on success | 402 success handler | Medium |
| Accept old flat format during transition | Payment verifier | High |
