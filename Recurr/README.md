# AlgoVoi Recurring (Tier 2) — Standing-Authority Subscriptions

**Status:** v1 shipped — all 7 chains live · Wire formats locked at `_v1`

Tier 2 is **"customer signs ONCE, AlgoVoi auto-pulls per cycle"** — the
subscription / standing-authority model. It sits on top of Tier 1 (one-shot
hosted-checkout payments) and extends merchants into recurring billing,
metered services, and agent-bound spending authorities.

This folder organises Tier 2 by chain. If you're integrating wallets,
start in the per-chain folder for your network. If you're integrating
the merchant side (creating + managing authorities), start in
[`merchant-examples/`](merchant-examples/) or the language-specific
adapter folders at the repository root (`native-python/`, `native-go/`,
`native-php/`, `native-rust/`).

---

## What problem does Tier 2 solve?

Tier 1 (one-shot) requires the customer to click "pay" on every invoice.
That works for ad-hoc purchases but breaks for:

| Use case | Why Tier 1 doesn't fit |
|---|---|
| Monthly SaaS subscriptions | Customer clicks pay 12 times a year |
| Metered AI-agent calls (`$0.001/query`) | Sub-cent per-tx fees + UX friction |
| Autonomous-agent budget caps | Agent can't sign each call interactively |
| Pre-paid auto-topup | Card-on-file UX doesn't exist on-chain |

Tier 2 replaces this with a **standing authority**: the customer signs
ONE on-chain authorisation that grants AlgoVoi's facilitator the right
to pull up to `cap_amount_minor` over `cap_period_seconds`, with a
per-pull cap of `per_cycle_amount_minor`. Each chain enforces the
cap on-chain — over-pulling is impossible at the consensus layer.

---

## Prerequisite — you need a Tier 1 subscription first

Tier 2 **builds on top of** a Tier 1 subscription. Before calling
`create_recurring_authority` you must have a subscription UUID.

Create one via the AlgoVoi dashboard, **or** via the API:

```python
# Python — create a subscription first
sub = av.post("/v1/subscriptions", {
    "customer_id": "CUSTOMER_UUID",
    "amount_minor": 10_000_000,   # $10 USDC
    "currency": "USD",
    "chain": "algorand_mainnet",
    "receiver_address": "YOUR_ALGO_ADDRESS",
    "cadence": "monthly",
})
subscription_id = sub["id"]   # pass this to create_recurring_authority
```

```typescript
// TypeScript — same step
const sub = await av["_post"]("/v1/subscriptions", {
  customer_id: "CUSTOMER_UUID",
  amount_minor: 10_000_000,
  currency: "USD",
  chain: "algorand_mainnet",
  receiver_address: "YOUR_ALGO_ADDRESS",
  cadence: "monthly",
});
const subscriptionId = sub.id;  // pass this to createRecurringAuthority
```

> **Dashboard path (recommended for most merchants):** Log in → Subscriptions → New.
> The gateway returns the `id` you need.

---

## Lifecycle

```
1. Tenant creates a subscription              (POST /v1/subscriptions — see above)
                ↓
2. Tenant calls create_recurring_authority    (POST /v1/recurring/authorities)
                ↓
   Gateway returns:
     - authority row (status='pending')
     - customer_signing_payload — chain-specific template
     - authorisation_url — optional hosted page
                ↓
3. Customer's wallet signs the on-chain authorisation     ← per-chain code lives here
                ↓
4. Tenant calls confirm_authority             (or AlgoVoi widget does it)
                ↓
   Authority transitions to status='active'
                ↓
5. AlgoVoi cycle reaper auto-pulls each cap_period_seconds
   Each pull emits a webhook:
     - subscription.charged (success)
     - subscription.payment_failed (retry / dunning)
                ↓
6. Customer or merchant revokes
   - revoke_authority     → on-chain revocation transaction
   - pause_authority      → off-chain pause (no chain action)
   - resume_authority     → off-chain resume
```

---

## Chain matrix

All 7 chains in the Tier 2 v1 surface have real provider implementations.
Each uses the most native primitive available on that chain:

| Chain | Primitive | Wire format | Decimals (USDC) | Mainnet | Testnet |
|---|---|---|---|---|---|
| **[Algorand](algorand/)** | SpendingCapVault smart contract (6-action atomic group) | `algorand_spending_cap_vault_v1` | 6 | ✓ | ✓ |
| **[VOI](voi/)** | SpendingCapVault (same contract — AVM-compatible) | `algorand_spending_cap_vault_v1` | 6 | ✓ | ✓ |
| **[Base](evm/)** (EVM) | ERC-20 `approve` (single tx) | `evm_erc20_approve_v1` | 6 | ✓ | ✓ Sepolia |
| **[Tempo](evm/)** (EVM) | ERC-20 `approve` (single tx) | `evm_erc20_approve_v1` | 6 | ✓ | ✓ |
| **[Solana](solana/)** | SPL Token `Approve` + facilitator delegate | `solana_spl_approve_v1` | 6 | ✓ | ✓ Devnet |
| **[Hedera](hedera/)** | HTS `AccountAllowanceApproveTransaction` (native) | `hedera_hts_allowance_v1` | 6 | ✓ | ✓ |
| **[Stellar](stellar/)** | Soroban `auth_entry` (smart-contract-based) | `stellar_soroban_auth_v1` | 7 | ✓ | ✓ |

**Note on decimals.** USDC uses 6-decimal precision on every chain
EXCEPT Stellar, where it uses 7 (Stellar's native asset precision).
When you specify `cap_amount_minor`, you must use the chain's native
decimals: `120 USDC = 120_000_000` on Algorand/Base/Solana/etc.,
but `120 USDC = 1_200_000_000` on Stellar.

---

## Webhook events

Tier 2 emits these event types in addition to Tier 1's `payment.*`
events. They share the same HMAC-signed envelope, so existing webhook
handlers verify them with the same secret.

| Event | When |
|---|---|
| `recurring.authority_created` | Tenant calls `create_recurring_authority` |
| `recurring.authority_activated` | Customer's authorisation lands on-chain |
| `recurring.authority_paused` | Tenant or customer pauses |
| `recurring.authority_resumed` | Tenant or customer resumes |
| `recurring.authority_revoked` | On-chain revocation lands |
| `recurring.authority_expired` | Cap window or auth expiry hit |
| `subscription.charged` | A cycle pull succeeded (carries `tx_id`) |
| `subscription.payment_failed` | A cycle pull failed (carries `failure_reason`) |

The `is_recurring_event(payload)` helper in `native-python/algovoi.py`
classifies these — fork your handler accordingly.

---

## Where to start

### "I'm a wallet integrator" — making customers sign authorisations

Start in the per-chain folder for the network your wallet supports:

- [`algorand/`](algorand/) — Pera, Defly, Lute, Daffi
- [`voi/`](voi/) — Lute, Kibisis, AVM-compatible wallets
- [`evm/`](evm/) — MetaMask, Rainbow, Coinbase Wallet, WalletConnect
- [`solana/`](solana/) — Phantom, Solflare, Backpack
- [`hedera/`](hedera/) — HashPack, Blade, Kabila
- [`stellar/`](stellar/) — Freighter, LOBSTR, Albedo

Each per-chain README documents the wire format, the actions the wallet
walks through, and shows realistic wallet-side code using that chain's
canonical SDK.

### "I'm a backend / merchant integrator" — creating + managing authorities

The merchant side is **chain-agnostic**: the same HTTP endpoints work
across every chain. Use one of the language adapters:

| Language | Folder | Tier 2 status |
|---|---|---|
| Python | [`../native-python/`](../native-python/) | ✅ v1.2.0 |
| TypeScript / JS | [`../native-typescript/`](../native-typescript/) | ✅ v1.2.0 |
| Go | [`../native-go/`](../native-go/) | ✅ v1.2.0 |
| PHP | [`../native-php/`](../native-php/) | ✅ v1.2.0 |
| Rust | [`../native-rust/`](../native-rust/) | ✅ v1.2.0 |

Or see [`merchant-examples/`](merchant-examples/) for runnable Python and
TypeScript samples.

### "I'm a platform plugin author" (WooCommerce / Shopify / etc.)

Tier 2 hooks for the platform plugins are tracked but not yet shipped.
The pattern: your plugin's "subscription product" type calls
`create_recurring_authority`, hands the returned `customer_signing_payload`
to the customer's wallet via per-chain JS, then listens for
`subscription.charged` webhooks to extend access.

---

## Reference

- **Gateway HTTP API:** `POST /v1/recurring/authorities` and 7 sibling endpoints
- **Hosted docs:** [docs.algovoi.co.uk](https://docs.algovoi.co.uk)
- **Compliance attestation:** [api.algovoi.co.uk/compliance/attestation](https://api.algovoi.co.uk/compliance/attestation)
- **Issues / support:** [GitHub Issues](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/issues)

The gateway server-side, the official `algovoi` Python SDK + `@algovoi/sdk`
TypeScript SDK, and the per-chain provider implementations are
co-versioned in the AlgoVoi product platform. The wire formats
(`*_v1`) are locked — future-format changes will bump the version
and run dual-path during rollout.
