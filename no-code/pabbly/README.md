# AlgoVoi — Pabbly Connect App

Accept crypto payments on Algorand, VOI, Hedera & Stellar via Pabbly Connect.

## Actions
- **Create Payment Link** — hosted AlgoVoi checkout URL
- **Verify Payment** — check on-chain payment status by token
- **List Networks** — all supported chains and assets

## Triggers
- **Payment Confirmed** — instant webhook when a crypto payment settles on-chain

## Setup
1. Log in at [connect.pabbly.com](https://connect.pabbly.com)
2. Create a workflow → search **AlgoVoi**
3. Connect with your `algvc_...` Cloud key + API Base `https://cloud.algovoi.co.uk`

Or use a direct `algv_...` AlgoVoi key with default API Base.

## Files
- `pabbly-app/pabbly-app.json` — full app definition for Pabbly import
