# CAIP-2 Namespace Conventions for Algorand, VOI, Hedera, and Stellar

This document defines the CAIP-2 chain identifiers used by AlgoVoi for the x402
payment protocol. These conventions were established through live implementation
and testing against x402 spec v1.

## Background

[CAIP-2](https://github.com/ChainAgnostic/CAIPs/blob/main/CAIPs/caip-2.md) defines
a chain identifier format: `namespace:reference`. For EVM chains this is well
established (e.g. `eip155:1` for Ethereum mainnet). For non-EVM chains, conventions
are less standardised. This document records what AlgoVoi uses in production.

---

## Identifier Table

| Network | CAIP-2 ID | Notes |
|---------|-----------|-------|
| Algorand mainnet | `algorand:mainnet` | AVM — USDC ASA 31566704 |
| VOI mainnet | `voi:mainnet` | AVM fork — aUSDC ARC200 302190 |
| Hedera mainnet | `hedera:mainnet` | HTS token 0.0.456858 (USDC) |
| Stellar pubnet | `stellar:pubnet` | USDC issued by Circle (`GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN`) |

---

## Algorand — `algorand:mainnet`

The Algorand namespace follows the pattern established by the
[CAIP-2 Algorand specification](https://github.com/ChainAgnostic/namespaces/tree/main/algorand).
The reference is the human-readable network name.

```json
{
  "scheme": "exact",
  "network": "algorand:mainnet",
  "amount": "10000",
  "asset": "31566704",
  "payTo": "<algorand-address>"
}
```

**Asset identifier:** The numeric ASA ID (`31566704` for USDC). This is unambiguous
on Algorand — ASA IDs are globally unique integers assigned at creation.

**Address format:** Standard Algorand base32 address (58 characters).

---

## VOI — `voi:mainnet`

VOI is an AVM-compatible chain (Algorand Virtual Machine fork) with its own namespace.

```json
{
  "scheme": "exact",
  "network": "voi:mainnet",
  "amount": "10000",
  "asset": "302190",
  "payTo": "<voi-address>"
}
```

**Asset identifier:** ARC200 token ID (`302190` for aUSDC — Aramid-bridged USDC).
VOI uses the same address format as Algorand (base32, 58 characters).

---

## Hedera — `hedera:mainnet`

Hedera uses dot-notation for all identifiers (accounts, tokens, contracts).

```json
{
  "scheme": "exact",
  "network": "hedera:mainnet",
  "amount": "10000",
  "asset": "0.0.456858",
  "payTo": "0.0.<account-id>"
}
```

**Asset identifier:** HTS token ID in shard.realm.num format (`0.0.456858` for USDC).

**Address format:** Hedera account IDs use `0.0.<number>` notation.
EVM-compatible addresses (`0x...`) are also valid on Hedera but the dot-notation
form is used here for consistency.

**Transaction ID note:** Hedera wallet apps produce IDs in the format
`0.0.account@seconds.nanos`. The Hedera Mirror Node REST API requires
`0.0.account-seconds-nanos` (replace `@` with `-`, replace the first `.` in the
timestamp with `-`). Normalise before querying:

```python
if "@" in tx_id:
    account, time = tx_id.split("@", 1)
    normalised = f"{account}-{time.replace('.', '-', 1)}"
```

---

## Stellar — `stellar:pubnet`

Stellar uses `pubnet` (not `mainnet`) to refer to the production network,
following the convention used in Stellar's own tooling and documentation.

```json
{
  "scheme": "exact",
  "network": "stellar:pubnet",
  "amount": "10000",
  "asset": "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN",
  "payTo": "<stellar-address>"
}
```

**Asset identifier:** `CODE:ISSUER` format — asset code plus the issuer's G-address.
This follows the Stellar SDK convention and is unambiguous (same code can have
multiple issuers on Stellar).

**Amount:** Horizon returns amounts as decimal strings (e.g. `"0.0100000"`).
Convert to microunits: `int(float(amount) * 1_000_000)`.

**Trust line requirement:** The receiver address must have an established trust line
for the USDC asset before it can receive it.

---

## Implementation notes

These identifiers are used in the `network` field of every x402 `accepts` entry
and payment proof. They were validated through end-to-end payment flows on each
network on **13 April 2026** — real 0.01 USDC transactions on each chain, verified
via the respective chain's public indexer/explorer API.

See the AlgoVoi x402 adapter:
[x402-ai-agents/](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/tree/master/x402-ai-agents)

---

## References

- [CAIP-2 specification](https://github.com/ChainAgnostic/CAIPs/blob/main/CAIPs/caip-2.md)
- [Chain Agnostic Namespaces registry](https://github.com/ChainAgnostic/namespaces)
- [x402 protocol specification](https://www.x402.org)
- [Algorand CAIP-2 namespace](https://github.com/ChainAgnostic/namespaces/tree/main/algorand)
- [Hedera Mirror Node API](https://mainnet-public.mirrornode.hedera.com)
- [Stellar Horizon API](https://horizon.stellar.org)
