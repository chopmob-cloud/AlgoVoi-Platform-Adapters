# AlgoVoi for GiveWP

Accept crypto donations (USDC on Algorand, VOI, Hedera & Stellar) via GiveWP.

## Requirements
- WordPress 5.8+
- PHP 7.4+
- GiveWP 2.25+

## Install
1. Download `algovoi-givewp.zip` from [GitHub Releases](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/releases/latest)
2. WordPress Admin → Plugins → Add New → Upload Plugin → Install → Activate
3. Donations → Settings → Payment Gateways → AlgoVoi

## Setup with AlgoVoi Cloud (recommended)
| Setting | Value |
|---------|-------|
| API Key | `algv_...` (from dash.algovoi.co.uk) |
| API Base URL | `https://cloud.algovoi.co.uk` |

Payout addresses are managed in your Cloud dashboard.

## How it works
1. Donor selects AlgoVoi on the donation form
2. Plugin creates an AlgoVoi checkout link and redirects the donor
3. Donor pays with their crypto wallet (USDC, ALGO, HBAR, XLM, etc.)
4. Payment confirmed on-chain — donation marked **Complete** in GiveWP
5. All donor data and reports available in GiveWP Reports

## Webhook (optional, for instant confirmation)
Set webhook URL in AlgoVoi dashboard:
```
https://yoursite.com/?algovoi_givewp_webhook=1
```

## Files
- `algovoi-givewp/algovoi-givewp.php` — plugin entry point
- `algovoi-givewp/src/AlgoVoiGateway.php` — payment gateway class
- `algovoi-givewp/src/AlgoVoiSettings.php` — GiveWP settings panel
