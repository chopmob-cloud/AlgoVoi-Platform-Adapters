# Hedera — HTS AccountAllowanceApprove (Tier 2)

**Wire format:** `hedera_hts_allowance_v1`
**Chains:** Hedera mainnet (`hedera_mainnet`) + Testnet (`hedera_testnet`)
**Asset:** USDC (HTS token `0.0.456858` mainnet · `0.0.429274` testnet, 6 decimals)
**Wallets:** HashPack, Blade, Kabila, any HCS-app-compatible wallet

Hedera Tier 2 uses HTS's native **`AccountAllowanceApproveTransaction`**
— much simpler than Solana or EVM because the allowance lives at the
consensus layer, not in a smart contract. No deploy, no contract gas,
no per-instruction overhead beyond Hedera's flat HTS fees.

---

## Single-action group

| # | Action id | Method | Description |
|---|---|---|---|
| 1 | `approve` | `hts_allowance_approve` | Customer signs `AccountAllowanceApproveTransaction` granting facilitator allowance over USDC HTS token |

After the transaction reaches consensus, AlgoVoi marks the authority
active and the cycle reaper begins pulling.

---

## Customer signing payload (sample)

```json
{
  "version":                  "hedera_hts_allowance_v1",
  "chain":                    "hedera_mainnet",
  "token_id":                 "0.0.456858",
  "decimals":                 6,
  "owner_account_id":         "0.0.<customer>",
  "spender_account_id":       "0.0.<algovoi_facilitator>",
  "merchant_payout_account_id": "0.0.<merchant>",
  "amount_atomic":            120000000,
  "approve_amount":           "120000000",
  "per_cycle_amount_atomic":  10000000,
  "actions": [
    {
      "id":     "approve",
      "method": "hts_allowance_approve",
      "signer": "customer",
      "args": {
        "token_id":           "0.0.456858",
        "owner_account_id":   "0.0.<customer>",
        "spender_account_id": "0.0.<algovoi_facilitator>",
        "amount":             120000000
      }
    }
  ]
}
```

---

## Wallet-side reference (Python + hiero_sdk_python)

```python
"""Reference wallet-side flow for Hedera Tier 2 authorisation.

Requires:
    pip install "hiero-sdk-python>=0.2" "protobuf>=6.31"

`hiero_sdk_python` is the Linux Foundation's official Python SDK for
Hedera. It mirrors the official Java/JS SDKs in surface and produces
Protocol Buffers-encoded transactions identical to what HashPack /
Blade / Kabila wallets emit.
"""

from hiero_sdk_python import (
    AccountAllowanceApproveTransaction,
    AccountId,
    Client,
    PrivateKey,
    TokenId,
)
from hiero_sdk_python.transaction.transaction_id import TransactionId

# 1. Receive the template from the gateway
template = response["customer_signing_payload"]
assert template["version"] == "hedera_hts_allowance_v1"

# 2. Parse the chain-native types
def parse_account_id(s: str) -> AccountId:
    shard, realm, num = s.split(".")
    return AccountId(int(shard), int(realm), int(num))

def parse_token_id(s: str) -> TokenId:
    shard, realm, num = s.split(".")
    return TokenId(int(shard), int(realm), int(num))

token   = parse_token_id(template["token_id"])
owner   = parse_account_id(template["owner_account_id"])
spender = parse_account_id(template["spender_account_id"])
amount  = int(template["approve_amount"])

# 3. Build the AccountAllowanceApproveTransaction
tx = AccountAllowanceApproveTransaction()
tx.approve_token_allowance(
    token_id=token,
    owner_account_id=owner,
    spender_account_id=spender,
    amount=amount,
)

# 4. Set transaction id + node before freeze.
#    Most wallets handle node selection automatically when you pass
#    the unsigned tx body; if you're freezing yourself, pick a
#    Hedera consensus node (0.0.3 through 0.0.27 on mainnet).
tx.transaction_id = TransactionId.generate(owner)
tx.node_account_id = AccountId(0, 0, 3)

# 5. Freeze + sign
client = Client.for_mainnet()
frozen = tx.freeze_with(client)

# Customer's wallet signs:
customer_key: PrivateKey = wallet.private_key   # provider-specific
signed = frozen.sign(customer_key)

# 6. Submit
receipt = signed.execute(client)
tx_id = str(tx.transaction_id)   # format: "0.0.X@seconds.nanos"

# 7. Tell AlgoVoi the authority is active
#    on_chain_address format: the transaction id
av.confirm_authority(
    authority_id=response["authority"]["id"],
    on_chain_address=tx_id,
)
```

For browser wallets (HashPack / Blade / Kabila) using
HashConnect / WalletConnect, the wallet handles the freeze + sign
+ submit steps. Pass the raw transaction body (Protocol Buffers
bytes) and the wallet returns the transaction id.

---

## Per-cycle pulls (informational)

After the authority is active, the cycle reaper submits
`TransferTransaction` flagged `is_approval=True`:

```
TransferTransaction:
  token_id: 0.0.456858 (USDC)
  transfers:
    - account: customer        amount: -per_cycle    (is_approval=True)
    - account: merchant_payout amount: +per_cycle
  signed_by: facilitator (using customer's pre-approved allowance)
```

Hedera's consensus layer enforces:
- `allowance(customer, facilitator, token) >= |amount|` (decrements per pull)
- `balance(customer, token) >= |amount|`

Failed pulls emit `subscription.payment_failed`; the next cycle retries.
When allowance reaches zero, the authority transitions to
`recurring.authority_expired`.

---

## Common pitfalls

- **Customer must have token-associated.** Hedera requires accounts
  to opt-in (`TokenAssociateTransaction`) to an HTS token before
  receiving or holding it. If the customer has never held USDC,
  they need to associate first — most Hedera wallets handle this
  with a one-click prompt when first seeing a USDC operation.
- **Spender must also be associated.** AlgoVoi's facilitator
  account is pre-associated with USDC on every supported network;
  no integrator action needed.
- **Hedera fees in HBAR.** Even though the value transfer is in
  USDC, network fees are paid in HBAR. Customers need a small HBAR
  balance (~0.05 HBAR / £0.001) for the approve transaction.
- **`AccountAllowanceApproveTransaction` is one of the few txns
  that can be batched** with other allowance approvals in a single
  signature. AlgoVoi v1 only requests a single token allowance per
  authority, so batching isn't currently used — but if you later
  want a multi-asset standing-authority, the same tx can carry
  multiple `approve_token_allowance(...)` entries.
- **`protobuf>=6.31` required.** `hiero_sdk_python` ships with
  proto bindings generated against newer protobuf runtime versions.
  If your environment pins protobuf < 6.31, you'll get a
  `VersionError` at import time. Upgrade with `pip install
  "protobuf>=6.31"`.

---

## Related

- [EVM ERC-20 approve](../evm/) — Hedera's HTS allowance is the
  consensus-layer equivalent of ERC-20 approve, just without the
  smart contract overhead
- [Solana SPL Approve](../solana/) — similar in spirit (native
  delegate primitive) but with Solana's account model
