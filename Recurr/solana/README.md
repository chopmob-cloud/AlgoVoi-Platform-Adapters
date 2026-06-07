# Solana — SPL Token Approve (Tier 2)

**Wire format:** `solana_spl_approve_v1`
**Chains:** Solana mainnet (`solana_mainnet`) + Devnet (`solana_devnet`)
**Asset:** USDC (mint `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`, 6 decimals)
**Wallets:** Phantom, Solflare, Backpack, any wallet-adapter-compatible

Solana Tier 2 uses SPL Token's native **`Approve`** instruction —
much simpler than building a custom Anchor program for v1. The customer
signs ONE transaction granting AlgoVoi's facilitator pubkey "delegate
authority" over a fixed amount of USDC in their Associated Token
Account (ATA). SPL Token enforces the approved amount on-chain at
the runtime level — over-pulling is impossible.

---

## Single-action group

| # | Action id | Method | Description |
|---|---|---|---|
| 1 | `approve` | `spl_token_approve` | Customer signs `Approve(amount=cap_amount)` against their USDC ATA |

That's the entire on-chain authorisation. The post-£150k roadmap parks
an "Anchor delegate program" path that adds merchant-payout-address
pinning at the contract layer (similar to Algorand's `add_recipient`
allowlist). For v1, AlgoVoi enforces the merchant payout server-side
before submitting each pull.

---

## Customer signing payload (sample)

```json
{
  "version":            "solana_spl_approve_v1",
  "chain":              "solana_mainnet",
  "asset_mint":         "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
  "spl_token_program":  "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
  "ata_program":        "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
  "decimals":           6,
  "delegate":           "ALGOVOI_FACILITATOR_PUBKEY_BASE58",
  "merchant_payout_address": "MERCHANT_PUBKEY_BASE58",
  "customer_address":   "CUSTOMER_PUBKEY_BASE58",
  "amount_atomic":      120000000,
  "approve_amount":     "120000000",
  "per_cycle_amount_atomic": 10000000,
  "actions": [
    {
      "id":     "approve",
      "method": "spl_token_approve",
      "signer": "customer",
      "args": {
        "asset_mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "delegate":   "ALGOVOI_FACILITATOR_PUBKEY_BASE58",
        "amount":     120000000
      }
    }
  ]
}
```

---

## Wallet-side reference (TypeScript + @solana/web3.js + @solana/spl-token)

```typescript
/**
 * Reference wallet-side flow for Solana Tier 2 authorisation.
 *
 * Uses @solana/web3.js + @solana/spl-token (the canonical Solana
 * SDK pair). Works with @solana/wallet-adapter for browser wallets
 * (Phantom, Solflare, Backpack, etc.).
 */

import {
  Connection,
  PublicKey,
  Transaction,
  clusterApiUrl,
} from "@solana/web3.js";
import {
  createApproveInstruction,
  getAssociatedTokenAddress,
} from "@solana/spl-token";

// 1. Receive the template from the gateway
const template = response.customer_signing_payload;
console.assert(template.version === "solana_spl_approve_v1");

// 2. Connect to the cluster
const connection = new Connection(
  template.chain === "solana_mainnet"
    ? "https://api.mainnet-beta.solana.com"
    : clusterApiUrl("devnet"),
  "confirmed",
);

// 3. Resolve the customer's USDC ATA
const customerPk = new PublicKey(template.customer_address);
const mintPk     = new PublicKey(template.asset_mint);
const customerAta = await getAssociatedTokenAddress(mintPk, customerPk);

// 4. Build the SPL Token Approve instruction
const approveIx = createApproveInstruction(
  customerAta,                                  // source ATA (writable)
  new PublicKey(template.delegate),             // delegate (facilitator)
  customerPk,                                   // owner (signer)
  BigInt(template.approve_amount),              // amount as u64
);

// 5. Wrap in a transaction, set blockhash + fee payer
const tx = new Transaction().add(approveIx);
const { blockhash } = await connection.getLatestBlockhash();
tx.recentBlockhash = blockhash;
tx.feePayer = customerPk;

// 6. Hand to the wallet for signing.
//    With @solana/wallet-adapter:
const signature = await wallet.sendTransaction(tx, connection);

// 7. Wait for confirmation
await connection.confirmTransaction(signature, "confirmed");

// 8. Tell AlgoVoi the authority is active.
//    For Solana, on_chain_address is the base58 transaction signature
//    (which is what Solana wallets return as the canonical handle).
await fetch(`${apiBase}/v1/recurring/authorities/${authorityId}/confirm`, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${apiKey}`,
    "X-Tenant-Id": tenantId,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ on_chain_address: signature }),
});
```

The Python equivalent uses `solders` + `spl-token` bindings — the
instruction-byte layout is identical (a 1-byte discriminator `4`
followed by an 8-byte little-endian u64 amount, with three account
metas: source ATA writable, delegate read-only, owner signer).

---

## Per-cycle pulls (informational)

After the authority is active, the cycle reaper builds and submits
`Transfer` instructions using its delegate authority:

```
Transfer(amount):
  source:    customer's USDC ATA
  dest:      merchant payout's USDC ATA
  authority: facilitator pubkey (using delegated authority)
  amount:    per_cycle_amount_atomic
```

The SPL Token program checks:
- `delegated_amount(customer_ata, facilitator) >= amount`
- decrements `delegated_amount` on each successful pull

When `delegated_amount` reaches zero, the authority transitions to
`recurring.authority_expired`. The customer re-authorises by signing
a fresh `Approve` (which creates a new authority row).

---

## Common pitfalls

- **ATA must exist before approve.** Solana ATAs are created lazily.
  If the customer doesn't already hold USDC in an ATA, the wallet
  needs to create it first (`createAssociatedTokenAccountInstruction`).
  Most wallets handle this automatically when the user first interacts
  with USDC; if your customer has never held USDC, prepend the
  ATA-creation instruction to the transaction.
- **Revoke = approve(0).** SPL Token's standard "remove delegate"
  is signing a fresh `Revoke` instruction (different opcode), but
  signing `Approve(amount=0)` has the same effect. AlgoVoi's
  `revoke_authority` returns a Revoke template.
- **Devnet USDC mint differs.** Testnet flows must pass an explicit
  `asset_id` (the devnet mint pubkey) in `create_recurring_authority`
  — the gateway has a canonical mainnet mint but no canonical devnet
  mint (testnet asset deployments rotate).
- **Compute budget.** A single SPL Token Approve fits well within
  the default compute budget (200,000 CU). No `ComputeBudgetProgram`
  prefix needed.

---

## Related

- [EVM ERC-20 approve](../evm/) — same shape, different runtime
- [Hedera HTS allowance](../hedera/) — Hedera's consensus-layer equivalent
- [Stellar Soroban auth_entry](../stellar/) — smart-contract authorisation
