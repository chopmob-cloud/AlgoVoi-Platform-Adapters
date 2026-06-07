# Stellar — Soroban auth_entry (Tier 2)

**Wire format:** `stellar_soroban_auth_v1`
**Chains:** Stellar mainnet (`stellar_mainnet`) + Testnet (`stellar_testnet`)
**Asset:** USDC (Stellar Asset Contract `CCW67TSZV3SSS2HXMBQ5JFGCKJNXKZM7UQUWUZPUTHXSTZLEO7SJMI75`, **7 decimals**)
**Wallets:** Freighter, LOBSTR, Albedo, any Soroban-aware wallet

Stellar Tier 2 uses **Soroban authorization entries** — Soroban is
Stellar's smart-contract platform (GA on mainnet 2024). The customer
pre-signs an authorization payload that proves "I authorize this
invocation tree on this network up to this ledger sequence". AlgoVoi's
facilitator then attaches the signed auth_entry to each
`InvokeHostFunction` per cycle.

This is the only chain in Tier 2 where the auth carries an explicit
**ledger expiry** (`valid_until_ledger_sequence`) baked into the
signature. The customer's auth literally cannot be replayed past
that ledger — strong on-chain time-bound, no merchant-side enforcement
required.

---

## Single-action group

| # | Action id | Method | Description |
|---|---|---|---|
| 1 | `approve` | `soroban_authorize_entry` | Customer signs `SorobanAuthorizationEntry` over `transfer(from, to, amount)` invocation against the USDC SAC contract |

---

## Decimals warning

⚠️ **Stellar uses 7 decimals for USDC, not 6.** This is Stellar's
native asset precision — 1 stroop = 10⁻⁷ XLM, and the USDC SAC
inherits that. When you specify `cap_amount_minor` in
`create_recurring_authority`:

| Display amount | Other chains (6 decimals) | Stellar (7 decimals) |
|---|---|---|
| 1 USDC | `1_000_000` | `10_000_000` |
| 10 USDC | `10_000_000` | `100_000_000` |
| 120 USDC | `120_000_000` | `1_200_000_000` |

Pass the right value or your customer authorises the wrong amount.

---

## Customer signing payload (sample)

```json
{
  "version":             "stellar_soroban_auth_v1",
  "chain":               "stellar_mainnet",
  "asset_contract_id":   "CCW67TSZV3SSS2HXMBQ5JFGCKJNXKZM7UQUWUZPUTHXSTZLEO7SJMI75",
  "decimals":            7,
  "spender_address":     "GALGOVOI_FACILITATOR_55_BASE32_CHARS",
  "merchant_payout_address": "GMERCHANT_PAYOUT_55_BASE32_CHARS",
  "customer_address":    "GCUSTOMER_55_BASE32_CHARS",
  "amount_atomic":       1200000000,
  "approve_amount":      "1200000000",
  "per_cycle_amount_atomic": 100000000,
  "network_passphrase":  "Public Global Stellar Network ; September 2015",
  "function_name":       "transfer",
  "actions": [
    {
      "id":     "approve",
      "method": "soroban_authorize_entry",
      "signer": "customer",
      "args": {
        "asset_contract_id": "CCW67TSZV3SSS2HXMBQ5JFGCKJNXKZM7UQUWUZPUTHXSTZLEO7SJMI75",
        "spender":           "GALGOVOI_FACILITATOR_55_BASE32_CHARS",
        "amount":            1200000000,
        "function_name":     "transfer"
      }
    }
  ]
}
```

---

## Wallet-side reference (Python + stellar_sdk)

```python
"""Reference wallet-side flow for Stellar Tier 2 authorisation.

Requires: pip install "stellar-sdk>=13.0"

Builds a Soroban authorization entry over a `transfer(from, to, amount)`
invocation against the USDC Stellar Asset Contract, signs it with the
customer's keypair, and returns the signed auth_entry XDR.

The signed auth_entry is what AlgoVoi's facilitator then attaches
to every per-cycle InvokeHostFunction transaction. The customer
signs once; the same auth_entry is reused per cycle until the
ledger-expiry passes.
"""

from stellar_sdk import Keypair, Network, scval, xdr as stellar_xdr
from stellar_sdk.address import Address
from stellar_sdk.auth import authorize_entry

# 1. Receive the template from the gateway
template = response["customer_signing_payload"]
assert template["version"] == "stellar_soroban_auth_v1"

# 2. Build the unsigned SorobanAuthorizationEntry over transfer(from, to, amount)
contract_args = stellar_xdr.InvokeContractArgs(
    contract_address=Address(template["asset_contract_id"]).to_xdr_sc_address(),
    function_name=stellar_xdr.SCSymbol(
        sc_symbol=template["function_name"].encode()
    ),
    args=[
        scval.to_address(template["customer_address"]),
        scval.to_address(template["merchant_payout_address"]),
        scval.to_int128(int(template["approve_amount"])),
    ],
)
auth_function = stellar_xdr.SorobanAuthorizedFunction(
    type=stellar_xdr.SorobanAuthorizedFunctionType.SOROBAN_AUTHORIZED_FUNCTION_TYPE_CONTRACT_FN,
    contract_fn=contract_args,
)
root_invocation = stellar_xdr.SorobanAuthorizedInvocation(
    function=auth_function,
    sub_invocations=[],
)

unsigned = stellar_xdr.SorobanAuthorizationEntry(
    credentials=stellar_xdr.SorobanCredentials(
        type=stellar_xdr.SorobanCredentialsType.SOROBAN_CREDENTIALS_ADDRESS,
        address=stellar_xdr.SorobanAddressCredentials(
            address=Address(template["customer_address"]).to_xdr_sc_address(),
            nonce=stellar_xdr.Int64(0),
            signature_expiration_ledger=stellar_xdr.Uint32(0),
            signature=scval.to_void(),
        ),
    ),
    root_invocation=root_invocation,
)

# 3. Resolve the customer's keypair from the wallet
#    (wallet provider handles the actual Keypair derivation; here
#    we assume direct access for illustration)
customer_kp: Keypair = wallet.keypair

# 4. Pick a sensible expiry — typically ~1 year of ledgers ahead.
#    Stellar produces ~5s ledgers, so 1 year ≈ 6.3M ledgers.
#    Fetch current ledger and add a buffer:
#      from stellar_sdk import ServerAsync
#      current_ledger = (await server.ledgers().limit(1).order(desc=True).call())["...
valid_until_ledger = await get_current_ledger() + 6_300_000

# 5. Sign the auth_entry
signed_entry = authorize_entry(
    entry=unsigned,
    signer=customer_kp,
    valid_until_ledger_sequence=valid_until_ledger,
    network_passphrase=template["network_passphrase"],
)

# 6. Submit a Soroban transaction that includes this auth_entry.
#    AlgoVoi's facilitator does this submission for the activation
#    transaction (so the customer's wallet only signs the auth_entry,
#    not a full tx). Tenants self-hosting can build the
#    InvokeHostFunctionOperation themselves.
#
#    The customer's signing handle (returned to AlgoVoi) is the
#    transaction hash once the activation tx lands.

# 7. Tell AlgoVoi the authority is active
#    on_chain_address format: 64-char hex SHA-256 of the signed envelope
av.confirm_authority(
    authority_id=response["authority"]["id"],
    on_chain_address=tx_hash_hex,   # 64 hex chars, no 0x prefix
)
```

For browser wallets (Freighter / LOBSTR / Albedo), the wallet API
exposes a `signAuthEntry(...)` or `signSorobanAuth(...)` method that
takes the unsigned XDR and returns the signed XDR — wallets handle
the network-passphrase + ledger-expiry resolution internally.

---

## Per-cycle pulls (informational)

After the authority is active, the cycle reaper submits
`InvokeHostFunction` operations of the form:

```
InvokeHostFunction:
  invocation: <transfer(customer, merchant_payout, per_cycle_amount)>
  auth: [<signed auth_entry from the customer>]
  signed_by: facilitator (covering tx fee in XLM)
```

Soroban's host function verifies:
- the auth_entry's signature against the customer's public key
- the auth_entry's `signature_expiration_ledger` > current ledger
- the invocation tree matches what the auth_entry authorises

If the cap_amount has been exhausted across cumulative pulls, the
USDC SAC contract reverts (insufficient allowance). AlgoVoi's
reaper detects this and emits `recurring.authority_expired`.

---

## Common pitfalls

- **7 decimals, not 6.** See the warning at the top. Easy to get
  wrong if you copy values from EVM/Solana code paths.
- **Customer must have a USDC trustline** before they can hold the
  asset. Stellar's classic asset model requires explicit trustlines;
  Soroban's SAC inherits this. Wallets handle trustline creation
  automatically when first interacting with the asset.
- **Network passphrase MUST match.** Soroban auth signatures are
  network-bound — a mainnet auth_entry will not verify on testnet
  and vice versa. The template carries `network_passphrase`
  explicitly; pass it through to `authorize_entry(...)` unchanged.
- **Testnet has no canonical USDC contract.** You must pass an
  explicit `asset_id` (Soroban contract id) when calling
  `create_recurring_authority` for `chain="stellar_testnet"`. The
  gateway will reject testnet calls without an explicit asset_id
  rather than guess.
- **Ledger expiry is exclusive.** `valid_until_ledger_sequence: N`
  means "valid for ledgers < N". If `current_ledger == N`, the
  auth has already expired. Pick a comfortable buffer.

---

## Related

- [Algorand SpendingCapVault](../algorand/) — the other smart-contract-based
  Tier 2 chain (more complex flow but with merchant-payout pinned at
  the contract layer)
- [Solana SPL Approve](../solana/) — Solana's runtime-level delegate
  (no contract; merchant-payout enforced server-side)
- The `stellar_sdk` library docs:
  [stellar-sdk.readthedocs.io](https://stellar-sdk.readthedocs.io)
