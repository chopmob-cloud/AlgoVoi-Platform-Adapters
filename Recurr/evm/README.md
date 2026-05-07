# EVM (Base + Tempo) — ERC-20 approve (Tier 2)

**Wire format:** `evm_erc20_approve_v1`
**Chains:** Base (chain id 8453), Tempo (chain id 4217), plus testnets
**Asset:** USDC (6 decimals on every supported EVM chain)
**Wallets:** MetaMask, Rainbow, Coinbase Wallet, any WalletConnect-compatible

EVM Tier 2 uses the standard **ERC-20 `approve(spender, amount)`** —
no custom contract deploy needed. The customer's `approve` grants
AlgoVoi's facilitator the right to call `transferFrom` up to
`cap_amount` total. Per-cycle pulls are individual `transferFrom`
calls; the ERC-20 contract enforces the running allowance on-chain.

This is the simplest Tier 2 flow of any chain — **a single transaction**
the wallet displays as a familiar "Approve USDC for spending" prompt
that users already understand from DeFi.

---

## Single-action group

Unlike Algorand's 6-action atomic group, EVM Tier 2 is one transaction:

| # | Action id | Method | Description |
|---|---|---|---|
| 1 | `approve` | `erc20_approve` | Customer calls `USDC.approve(facilitator, cap_amount)` |

That's it. Once mined, the authority transitions to active.

---

## Customer signing payload (sample)

```json
{
  "version":          "evm_erc20_approve_v1",
  "chain":            "base_mainnet",
  "chain_id":         8453,
  "asset_contract":   "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
  "decimals":         6,
  "spender":          "0xALGOVOI_FACILITATOR_40_HEX_CHARS",
  "merchant_payout_address": "0xMERCHANT_PAYOUT_40_HEX_CHARS",
  "customer_address": "0xCUSTOMER_40_HEX_CHARS",
  "amount_atomic":    120000000,
  "approve_amount":   "120000000",
  "per_cycle_amount_atomic": 10000000,
  "actions": [
    {
      "id":     "approve",
      "method": "erc20_approve",
      "signer": "customer",
      "args": {
        "asset_contract": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "spender":        "0xALGOVOI_FACILITATOR_40_HEX_CHARS",
        "amount":         120000000
      }
    }
  ]
}
```

---

## Chain reference

| Chain id (env) | Chain id (numeric) | USDC contract | Native gas token |
|---|---|---|---|
| `base_mainnet` | 8453 | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` | ETH |
| `base_sepolia` | 84532 | `0x036CbD53842c5426634e7929541eC2318f3dCF7e` | ETH (testnet) |
| `tempo_mainnet` | 4217 | `0x20c000000000000000000000b9537d11c60e8b50` | USDC (gas paid in USDC!) |
| `tempo_testnet` | 4218 | `0x20c000000000000000000000b9537d11c60e8b50` | USDC (gas paid in USDC!) |

**Tempo is unusual:** Stripe + Paradigm's EVM L1 uses USDC as the
native gas token. Customers don't need a separate balance to pay gas
— the same `cap_amount_minor` they authorise covers gas (gateway
calculates a small reserve).

---

## Wallet-side reference (TypeScript + ethers.js / viem)

```typescript
/**
 * Reference wallet-side flow for EVM Tier 2 authorisation.
 *
 * Works with any EIP-1193 provider (MetaMask, Rainbow, Coinbase
 * Wallet, WalletConnect). Shown here with viem; ethers.js v6 has
 * the same shape with `Contract.approve(...)`.
 */

import { createWalletClient, custom, parseAbi } from "viem";
import { base } from "viem/chains";

// 1. Receive the template from the gateway
const template = response.customer_signing_payload;
console.assert(template.version === "evm_erc20_approve_v1");

// 2. Connect to the user's wallet
const walletClient = createWalletClient({
  chain: base,
  transport: custom(window.ethereum!),
});

// 3. Verify chain id matches what the customer expects
const chainId = await walletClient.getChainId();
if (chainId !== template.chain_id) {
  // Prompt user to switch network
  await walletClient.switchChain({ id: template.chain_id });
}

// 4. Call USDC.approve(spender, amount)
const erc20Abi = parseAbi([
  "function approve(address spender, uint256 amount) returns (bool)",
]);

const txHash = await walletClient.writeContract({
  address: template.asset_contract as `0x${string}`,
  abi: erc20Abi,
  functionName: "approve",
  args: [
    template.spender as `0x${string}`,
    BigInt(template.approve_amount),
  ],
  account: template.customer_address as `0x${string}`,
});

// 5. Wait for confirmation (~5s on Base, ~1s on Tempo)
//    Use the public client to poll, or your wallet's provider.
const receipt = await publicClient.waitForTransactionReceipt({ hash: txHash });

// 6. Tell AlgoVoi the authority is active
//    on_chain_address format: "0x<tx_hash>"
await fetch(`${apiBase}/v1/recurring/authorities/${authorityId}/confirm`, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${apiKey}`,
    "X-Tenant-Id": tenantId,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    on_chain_address: txHash,
  }),
});
```

For Python on the merchant side (just creating + managing
authorities), use [`../../native-python/`](../../native-python/) —
the merchant flow is identical for EVM and other chains.

---

## Per-cycle pulls (informational)

After the authority is active, the cycle reaper calls
`USDC.transferFrom(customer, merchant_payout_address, amount)`
per cycle. The ERC-20 contract enforces:

- `allowance(customer, facilitator) >= amount` (decrements on each pull)
- `balanceOf(customer) >= amount` (otherwise reverts)

If a pull would exceed the remaining allowance, AlgoVoi marks the
authority `expired` and emits `recurring.authority_expired`. The
customer can re-authorise by signing a new approve.

---

## Common pitfalls

- **Front-running risk on `approve`.** ERC-20's classic vulnerability:
  if you change an existing allowance from N to M without zeroing first,
  an attacker can race-spend N + M. AlgoVoi v1 only sets fresh
  allowances on new authorities; it never rotates an existing
  allowance in place. Re-authorisation creates a new authority row.
- **Gas estimation.** On Base, gas is ETH; ensure customers have
  enough ETH for the approve (~0.0001 ETH at typical fees). On
  Tempo, gas is USDC and comes out of the same balance.
- **Permit2 / EIP-2612.** v1 uses standard ERC-20 `approve` for
  maximum wallet compatibility. EIP-2612 `permit` (gasless approves
  via signature) is a post-£150k roadmap item.
- **`allowance` decrements.** Each pull reduces the allowance.
  When `allowance == 0`, no more pulls succeed even if
  `cap_period_seconds` hasn't elapsed. AlgoVoi's reaper detects
  this via the `transferFrom` revert and transitions to
  `recurring.authority_expired`.

---

## Related

- [Algorand SpendingCapVault](../algorand/) — atomic 6-action vault flow
- [Solana SPL Approve](../solana/) — SPL Token native delegate (similar shape)
- [Hedera HTS allowance](../hedera/) — the consensus-layer equivalent on Hedera
