# Tier 2 — Merchant-side examples

Working examples of the merchant-side Tier 2 lifecycle (create
authority, confirm, manage, handle webhooks). The merchant flow is
**chain-agnostic** — the same HTTP endpoints work across all 7
supported chains. The only chain-specific detail at the merchant
layer is the `cap_amount_minor` decimals (6 on most chains, 7 on
Stellar).

For wallet-side / customer-signing flows (per chain), see the
sibling per-chain folders:
[`../algorand/`](../algorand/) · [`../voi/`](../voi/) ·
[`../evm/`](../evm/) · [`../solana/`](../solana/) ·
[`../hedera/`](../hedera/) · [`../stellar/`](../stellar/).

---

## Language status

| Language | File | Adapter version | Notes |
|---|---|---|---|
| Python | [`python.py`](python.py) | `native-python/algovoi.py` v1.2.0+ | Full Tier 2 surface — 8 lifecycle methods + `is_recurring_event` helper. **Shipped.** |
| Go | [`go.go`](go.go) | `native-go/` v1.2.0+ (`recurring.go`) | Same surface as Python with idiomatic Go — typed structs (`AuthorityCreateRequest`, `Authority`), `error` returns, `IsRecurringNetwork`, `IsRecurringEvent`. **Shipped.** 12 unit + round-trip tests pass with `go test ./...`. |
| PHP | [`php.php`](php.php) | `native-php/algovoi.php` v1.2.0+ | Same 8-method surface in PHP 8.4-style — typed parameters, `?array` returns, `AlgoVoi::isRecurringNetwork` / `AlgoVoi::isRecurringEvent` static helpers, `RECURRING_NETWORKS` / `RECURRING_EVENT_TYPES` constants. **Shipped.** 18 stdlib-only tests pass with `php recurring_test.php`. |
| Rust | [`rust.rs`](rust.rs) | `native-rust/` v1.2.0+ (`src/recurring.rs`) | Same 8-method surface, `Result<T, Error>` returns, typed structs, `BTreeMap<String, String>` for metadata. Caller-pluggable `HttpClient` trait (use `ureq` / `reqwest` / `hyper` / etc.). Manual JSON encode/decode (no `serde` dep — keeps the `# No [dependencies]` Cargo.toml promise). **Shipped.** 22 new Tier 2 tests + 23 pre-existing Tier 1 = 45/45 pass with `cargo test --lib`. |
| TypeScript | [`typescript.ts`](typescript.ts) | `native-typescript/algovoi.ts` v1.2.0+ | Single-file, zero-dep TS adapter. Universal `fetch` + WebCrypto — runs on Node 18+, Bun, Deno, browsers, Cloudflare Workers, Vercel Edge. Same 8-method surface; typed interfaces + `Promise<T \| null>` returns + `isRecurringEvent` / `isRecurringNetwork` helpers. **Shipped.** 24/24 tests pass with `node --experimental-strip-types recurring_test.ts`. |

All five language adapters now ship Tier 2. The MCP server, no-code
adapters, and platform plugins remain on the roadmap — track those
in the parent repo's open issues.

---

## Lifecycle (chain-agnostic merchant view)

```
POST /v1/recurring/authorities
  ↓ returns: { authority: {...}, customer_signing_payload: <chain-specific> }
  ↓
[wallet signs the customer_signing_payload — see per-chain folder]
  ↓
POST /v1/recurring/authorities/{id}/confirm
  ↓ marks authority active
  ↓
[AlgoVoi cycle reaper auto-pulls per cap_period_seconds]
  ↓
[your webhook handler receives subscription.charged / .payment_failed]
  ↓
[any time] GET    /v1/recurring/authorities/{id}    inspect state
[any time] POST   /v1/recurring/authorities/{id}/pause / resume
[when done] POST  /v1/recurring/authorities/{id}/revoke
```

`python.py` walks through each step end-to-end with comments.

---

## Why the merchant layer is chain-agnostic

Tier 2's merchant side has **no chain-specific code**. `create_recurring_authority`
takes a `chain` field, the gateway returns the right
`customer_signing_payload` for that chain, and your wallet UI handles
chain-native signing using the matching per-chain folder. The 8-method
API surface is identical across every language adapter — only the
type signatures and idioms differ.

---

## Running any example

Every example defaults to a smoke-check that lists supported chains and
event types without making any network calls. Replace the `api_key` /
`tenant_id` / `webhook_secret` placeholders with real values to exercise
the full lifecycle.

```bash
# Python
python python.py

# Go  (run from the native-go directory so the local package resolves)
cd ../../native-go && go run ../Recurr/merchant-examples/go.go

# PHP
php php.php

# Rust  (add algovoi + ureq to your Cargo.toml first — see file header)
cargo run --example rust

# TypeScript (Node 18+)
node --experimental-strip-types typescript.ts
```
