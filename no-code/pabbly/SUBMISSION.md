# Pabbly Connect — Submission Package

This file contains everything the user needs to copy/paste when submitting AlgoVoi to Pabbly Connect. Not included in the public app listing — internal only.

## 1. Submission route

Since `pabbly-app.json` is a standalone app definition, the realistic path to getting AlgoVoi listed is:

1. **You (already signed in)** → navigate to https://connect.pabbly.com/app in your logged-in session
   - If the page loads a developer dashboard → import `pabbly-app.json` directly and follow prompts
   - If the page shows "access denied" or 404 → fall back to the support-chat route below

2. **Support-chat fallback** → in your Pabbly Connect dashboard, click the chat widget (bottom-right) and send the message in §3 below

3. **Email fallback** → if chat is unresponsive, email **integration@pabbly.com** (copy the message from §3)

Pabbly's official pre-requisites guide: https://forum.pabbly.com/threads/introduction-and-pre-requisites.2425/

## 2. Intake form fields — copy/paste ready

| Field | Value |
|---|---|
| **App name** | AlgoVoi |
| **Category** | Payment / Finance |
| **Website** | https://algovoi.co.uk |
| **Dashboard URL** | https://dash.algovoi.co.uk |
| **API docs** | https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters |
| **Primary color** | #00b8a9 |
| **Audience** | Public (B2B + B2C merchants) |
| **Tagline** | Accept crypto payments on Algorand, VOI, Hedera & Stellar — direct-to-wallet, no processor fees. |
| **Support email** | support@algovoi.co.uk *(confirm before submitting)* |
| **Company** | AlgoVoi Ltd / Chopmob |

## 3. Initial message (copy/paste)

```
Hi Pabbly team,

I'd like to submit a custom app to Pabbly Connect. It's called AlgoVoi — a
crypto payment gateway that accepts USDC on Algorand, VOI, Hedera, and
Stellar, plus the native tokens on each chain. Direct-to-wallet
settlement, no card processors.

App spec is ready as a Pabbly Connect v1.1.0-compliant JSON definition.
Includes:

- 1 basic-auth connection (supports AlgoVoi Cloud + direct API modes)
- 3 actions: Create Payment Link, Verify Payment, List Networks
- 1 trigger: Payment Confirmed (webhook, instant on-chain confirmation)

JSON + README:
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/tree/master/no-code/pabbly

I can provide a test API key (algv_...) for your QA to exercise
every action and trigger against a live sandbox.

What's the next step to get this into your review queue?

Thanks,
[Your name]
Chopmob / AlgoVoi
```

## 4. Test credentials package (for their QA)

Prepare in advance so you can share immediately when asked:

```
# For Pabbly QA testing — AlgoVoi API key
ALGOVOI_API_KEY=algv_<paste-here>
ALGOVOI_API_BASE=https://cloud.algovoi.co.uk
# No tenant ID or payout addresses needed when API_BASE points at Cloud

# Test flow:
# 1. Create connection with the key above
# 2. Action: "List Networks" → should return 12 networks
# 3. Action: "Create Payment Link" with amount=1.00, network=algorand_testnet
#    → returns a checkout URL you can open in a browser
# 4. Trigger: "Payment Confirmed" → enable webhook, pay the checkout URL on testnet
#    → trigger fires with tx_id + amount + network
```

**Generate a fresh QA-only Cloud key** at https://dash.algovoi.co.uk → Settings → API Keys. Label it "Pabbly QA" so you can rotate it after approval.

## 5. Assets required (produce before submitting)

| Asset | Spec | Status |
|---|---|---|
| **Logo (main)** | 256×256 PNG, transparent background | ⬜ Need to produce |
| **Logo (large)** | 512×512 PNG, transparent background | ⬜ Need to produce |
| **Short description** | ≤140 chars | ✅ In JSON |
| **Long description** | ≤500 chars | ✅ In JSON |
| **Screenshots** | 1–3 showing the Pabbly workflow with AlgoVoi action/trigger | ⬜ Need to produce (take after connection is working locally) |
| **Privacy policy URL** | Publicly reachable | ⬜ Need to publish |
| **Terms of service URL** | Publicly reachable | ⬜ Need to publish |
| **Support email** | Monitored | ⬜ Confirm address |

### Logo placeholder

Until a proper logo asset exists, use the AlgoVoi emblem from the dashboard at https://dash.algovoi.co.uk — right-click → Save As to grab the SVG, then export to PNG at 256 and 512 using any image tool (e.g. `inkscape -w 256 logo.svg -o logo-256.png`).

## 6. Review timeline expectations

Based on Pabbly's public forum activity:
- **Initial response**: 24 business hours (Mon–Fri, 10am–6pm IST)
- **First review pass**: typically 1–2 weeks after submission
- **Approval → public listing**: 2–6 weeks total (depends on QA back-and-forth)

## 7. Post-approval follow-ups

Once listed:
- [ ] Update `no-code/pabbly/README.md` with the live Pabbly app URL
- [ ] Update `dash.algovoi.co.uk/connect` Pabbly wizard to link to the real app page
- [ ] Update `marketplace_submissions.md` memory: ⬜ → ✅
- [ ] Rotate the QA `algv_` key (can be kept for production monitoring, relabelled)
