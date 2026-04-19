# AlgoVoi — Pabbly Connect App

Accept crypto payments on Algorand, VOI, Hedera & Stellar via Pabbly Connect.

## Actions
- **Create Payment Link** — hosted AlgoVoi checkout URL
- **Verify Payment** — check on-chain payment status by token
- **List Networks** — all supported chains and assets

## Triggers
- **Payment Confirmed** — instant webhook when a crypto payment settles on-chain

## Setup (end-user)
1. Log in at [connect.pabbly.com](https://connect.pabbly.com)
2. Create a workflow → search **AlgoVoi**
3. Connect with your `algvc_...` Cloud key — API Base defaults to `https://cloud.algovoi.co.uk`
4. Leave Tenant ID and payout-address fields **blank** — Cloud manages them centrally

Direct-API users (advanced): use an `algv_...` key + set API Base to `https://api1.ilovechicken.co.uk` + fill Tenant ID and payout addresses.

## For developers — submitting to Pabbly

The app definition lives at `pabbly-app/pabbly-app.json` (v1.1.0, Pabbly Connect schema). It declares:

- **1 connection** — supports both AlgoVoi Cloud (default, recommended) and direct-API modes via the same fields
- **3 actions** — Create Payment Link, Verify Payment, List Networks
- **1 trigger** — Payment Confirmed (webhook-based, instant on-chain confirmation)

### Submission path
1. Log into [connect.pabbly.com](https://connect.pabbly.com) → visit `/app` (the developer portal)
2. If portal is gated, use the chat widget or email `integration@pabbly.com` requesting developer access. Attach `pabbly-app.json` or link to this file on GitHub.
3. Pabbly reviewers will test actions + triggers against a sandbox; provide a working `algvc_...` Cloud key for QA.
4. Once approved, the app appears in the public Pabbly Connect app directory.

### Pabbly pre-requisites (per [official guide](https://forum.pabbly.com/threads/introduction-and-pre-requisites.2425/))
- Pabbly Connect account ✅
- REST API expertise + Postman/Insomnia familiarity ✅ (see sibling adapters for reference)
- Understanding of the integration flow ✅ (documented above)
- Adherence to Pabbly Connect Integration Best Practices ✅

## Files
- `pabbly-app/pabbly-app.json` — full app definition for Pabbly import (v1.1.0)
