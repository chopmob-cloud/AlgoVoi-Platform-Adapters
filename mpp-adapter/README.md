# MPP — Machine Payments Protocol Adapter for AlgoVoi

Drop-in server middleware that gates APIs behind MPP payment challenges. Implements the IETF `draft-ryan-httpauth-payment` spec (`intent="charge"`) with challenge echo validation and on-chain verification across all 4 chains — no central verification API, zero pip dependencies.

**100% IETF spec compliant — v2.1.0, verified live on all 4 chains (2026-04-13). 153/153 tests passing.**

Full integration guide: [mpp-adapter.md](mpp-adapter.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `mpp.py` | Adapter — `MppGate` middleware class for Flask, Django, FastAPI, or any WSGI/ASGI framework |
| `mpp-adapter.md` | Full integration guide |
| `test_mpp.py` | 153 unit tests |
| `smoke_test_mpp.py` | End-to-end smoke test — live 0.01 USDC payments across all 4 chains |

---

## Supported chains

| Chain | Network key | Asset | Asset ID |
|-------|-------------|-------|----------|
| Algorand mainnet | `algorand_mainnet` | USDC | 31566704 |
| VOI mainnet | `voi_mainnet` | aUSDC | 302190 |
| Hedera mainnet | `hedera_mainnet` | USDC HTS | 0.0.456858 |
| Stellar pubnet | `stellar_mainnet` | USDC Circle | `USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN` |

---

## Quick start

Copy `mpp.py` into your project. No package install required.

```python
from mpp import MppGate

gate = MppGate(
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_...",
    tenant_id="<your-tenant-uuid>",
    resource_id="my-inference-api",
    amount_microunits=10000,          # 0.01 USDC
    networks=["algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet"],
    realm="My Inference API",
    payout_address="<your-algorand-address>",
)
```

### Flask

```python
@app.before_request
def check_payment():
    return gate.flask_guard()
```

### Django

```python
# yourapp/middleware.py
from mpp import MppGate
gate = MppGate(...)
mpp_middleware = gate.django_middleware
```

### WSGI (manual)

```python
result = gate.check(request.headers)
if result.requires_payment:
    status, headers, body = result.as_wsgi_response()
    return start_response(status, headers), [body]
```

---

## Live smoke test — 13 April 2026

0.01 USDC verified on each chain via on-chain indexers:

| Chain | TX ID | Result |
|-------|-------|--------|
| Algorand | `PNN25O7E6WTOWFB36YVZHRLIHICPOWOYBRDFP3ZJKKJ32PKL472A` | ✅ Pass |
| VOI | `YOJTOMTW7K2VASM3N2OALPIDC66CMABDD2ZJE4SYTHGR2H2MKTYA` | ✅ Pass |
| Hedera | `0.0.10376692@1776103661.888390747` | ✅ Pass |
| Stellar | `338b0061e81cf615631f7830e0a480f6beed0c333206c4366c14e6a761393153` | ✅ Pass |

---

Licensed under the [Business Source License 1.1](../LICENSE).
