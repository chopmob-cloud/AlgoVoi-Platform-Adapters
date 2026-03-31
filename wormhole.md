# Wormhole Integration — AlgoVoi Tenant Services

Bridge **USDC from any supported chain** to **Algorand or VOI** for settlement via AlgoVoi.

> **Financial Services integration.** Wormhole is a permissionless cross-chain messaging and token transfer protocol. This integration enables USDC held on Ethereum, Solana, Base, Polygon, or other supported chains to be bridged natively to Algorand for AlgoVoi settlement — no manual swap required.

---

## How it works

```
Payer holds USDC on Ethereum / Solana / Base / Polygon (or any Wormhole chain)
            ↓
Wormhole NTT burns/locks USDC on source chain
            ↓
Wormhole guardian network produces attestation (~13 seconds)
            ↓
USDC minted on Algorand (or VOI) via CCTP / NTT bridge
            ↓
AlgoVoi verifies on-chain receipt on Algorand / VOI
            ↓
Settlement complete — TX ID recorded
```

No CEX. No manual swap. USDC arrives natively on Algorand from any source chain.

---

## Prerequisites

- An active AlgoVoi tenant account
- A funded wallet on a Wormhole-supported source chain (Ethereum, Solana, Base, Polygon, Avalanche, etc.)
- An Algorand wallet opted into ASA `31566704` (USDC) as the destination
- Basic familiarity with cross-chain transactions

> Wormhole is a permissionless open protocol — no onboarding, KYB, or approval required. Integration is developer-driven.

---

## Step 1 — Configure your network

### USDC on Algorand mainnet (destination)

```http
POST /internal/tenants/{tenant_id}/network-configs
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "network": "algorand_mainnet",
  "payout_address": "<your-algorand-address>",
  "preferred_asset_id": "31566704",
  "preferred_asset_decimals": 6
}
```

> The Algorand payout wallet must have opted into ASA `31566704` before it can receive bridged USDC.

---

## Step 2 — Connect the integration

No platform-specific credentials are required for Wormhole — the bridge is on-chain. Register the integration to enable AlgoVoi to watch for bridged USDC arriving at your payout address:

```http
POST /internal/integrations/{tenant_id}/wormhole
Authorization: Bearer <admin-key>
Content-Type: application/json

{
  "credentials": {},
  "shop_identifier": "<your-identifier>",
  "base_currency": "USD",
  "preferred_network": "algorand_mainnet"
}
```

---

## Step 3 — Initiate a cross-chain transfer

Use the Wormhole SDK or Portal Bridge UI to transfer USDC from the source chain to Algorand.

### Via Wormhole SDK (TypeScript)

```typescript
import { wormhole, amount } from "@wormhole-foundation/sdk";
import algorand from "@wormhole-foundation/connect-sdk-algorand";
import evm from "@wormhole-foundation/connect-sdk-evm";

const wh = await wormhole("Mainnet", [evm, algorand]);

const srcChain = wh.getChain("Ethereum");
const dstChain = wh.getChain("Algorand");

// Initiate USDC transfer: 10 USDC from Ethereum → Algorand
const xfer = await wh.tokenTransfer(
  "USDC",
  amount.units(amount.parse("10", 6)),
  { chain: "Ethereum", address: "<sender-evm-address>" },
  { chain: "Algorand", address: "<your-algorand-payout-address>" },
  false // automatic = false (manual redeem)
);

const srcTxids = await xfer.initiateTransfer(srcSigner);
console.log("Source TX:", srcTxids);

// Wait for attestation (~13 seconds), then redeem on Algorand
await xfer.fetchAttestation(60_000);
const dstTxids = await xfer.completeTransfer(dstSigner);
console.log("Algorand TX:", dstTxids);
```

### Via Portal Bridge UI

1. Go to [portalbridge.com](https://portalbridge.com)
2. Select **Source chain** (e.g. Ethereum) and **Target chain** (Algorand)
3. Select **USDC** as the token
4. Paste your AlgoVoi payout address as the destination
5. Confirm and sign on the source chain
6. Wait for attestation, then redeem on Algorand

---

## Payment flow

Once a cross-chain transfer completes:

1. USDC arrives at your AlgoVoi payout address on Algorand
2. AlgoVoi detects the on-chain receipt via its Algorand indexer
3. Payment is confirmed and TX ID is recorded against the pending order
4. Merchant is notified via configured webhook

> AlgoVoi monitors for USDC transfers to registered payout addresses. The Wormhole transfer TX ID on the destination chain is used as the payment reference.

---

## Supported source chains

| Chain | USDC source | Bridge mechanism |
|-------|-------------|-----------------|
| Ethereum | Native USDC (Circle) | CCTP via Wormhole |
| Solana | Native USDC (Circle) | CCTP via Wormhole |
| Base | Native USDC (Circle) | CCTP via Wormhole |
| Polygon | Native USDC (Circle) | CCTP via Wormhole |
| Avalanche | Native USDC (Circle) | CCTP via Wormhole |
| Arbitrum | Native USDC (Circle) | CCTP via Wormhole |
| Optimism | Native USDC (Circle) | CCTP via Wormhole |

All transfers settle as native USDC (ASA `31566704`) on Algorand mainnet.

---

## Transfer times

| Step | Typical duration |
|------|-----------------|
| Source chain confirmation | 12–15 seconds (EVM), ~1 second (Solana) |
| Wormhole guardian attestation | ~13 seconds |
| Algorand destination confirmation | ~4 seconds |
| **Total end-to-end** | **~30 seconds** |

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| Transfer stuck at attestation | Guardian network congestion — wait up to 60 seconds before retrying |
| Algorand redeem failing | Payout wallet not opted into ASA `31566704` |
| USDC not appearing in AlgoVoi | Destination address mismatch — verify the Algorand address used matches your registered payout address |
| HTTP 422 "No network config" | Network config missing for `algorand_mainnet` |

---

## Supported networks

| Network | Asset | Notes |
|---------|-------|-------|
| `algorand_mainnet` | USDC (ASA 31566704) | Destination for all Wormhole transfers |
| `algorand_testnet` | Test USDC | Use Wormhole testnet environment for testing |
