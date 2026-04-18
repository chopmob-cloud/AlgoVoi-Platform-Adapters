# AlgoVoi for Gravity Forms

Accept crypto payments (USDC on Algorand, VOI, Hedera & Stellar) in Gravity Forms.

## Requirements
- WordPress 5.8+
- PHP 7.4+
- Gravity Forms 2.6+ (any license tier)

## Install
1. Download `algovoi-gravity-forms.zip` from [GitHub Releases](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/releases/latest)
2. WordPress Admin → Plugins → Add New → Upload Plugin → Install → Activate
3. Forms → Settings → AlgoVoi → enter your API credentials

## Setup with AlgoVoi Cloud (recommended)
| Setting | Value |
|---------|-------|
| API Key | `algvc_...` (from dash.algovoi.co.uk) |
| API Base URL | `https://cloud.algovoi.co.uk` |

Payout addresses are managed in your Cloud dashboard — no need to enter them in each plugin.

## How it works
1. Customer submits your form
2. Plugin creates an AlgoVoi checkout link and redirects the customer
3. Customer pays with their crypto wallet
4. AlgoVoi confirms the on-chain payment and redirects back
5. Entry is marked as **Paid** in Gravity Forms

## Files
- `algovoi-gravity-forms/algovoi-gravity-forms.php` — plugin entry point
- `algovoi-gravity-forms/class-gf-algovoi.php` — payment add-on class
