# AlgoVoi — Activepieces Community Piece

Accept crypto payments on Algorand, VOI, Hedera & Stellar via [Activepieces](https://activepieces.com).

## Actions
- **Create Payment Link** — hosted AlgoVoi checkout URL
- **Verify Payment** — check on-chain payment status by token
- **List Networks** — all supported chains and assets

## Triggers
- **Payment Confirmed** — instant webhook when a crypto payment settles on-chain (optional network filter)

## Setup (Activepieces Cloud)
1. Open [cloud.activepieces.com](https://cloud.activepieces.com)
2. Pieces → search **AlgoVoi**
3. Connect with your `algvc_...` Cloud key + API Base `https://cloud.algovoi.co.uk`

## Setup (self-hosted)
```bash
cd no-code/activepieces/algovoi-piece
npm install
npm run build
```
Then add the piece to your Activepieces instance via the pieces registry.

## Auth — AlgoVoi Cloud (recommended)
| Field | Value |
|-------|-------|
| API Key | `algvc_...` (from dash.algovoi.co.uk) |
| API Base URL | `https://cloud.algovoi.co.uk` |

Leave Tenant ID and payout addresses blank — managed in your Cloud dashboard.
