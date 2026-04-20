=== AlgoVoi for Gravity Forms ===
Contributors: algovoi
Tags: gravity forms, crypto, usdc, algorand, payments
Requires at least: 5.8
Tested up to: 6.9
Requires PHP: 7.4
Stable tag: 1.0.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Accept crypto payments (USDC + native tokens on Algorand, VOI, Hedera, Stellar) inside Gravity Forms.

== Description ==

**AlgoVoi for Gravity Forms** adds AlgoVoi as a payment feed inside Gravity Forms, letting your form submissions trigger a secure crypto checkout with on-chain settlement.

Built for merchants and creators who need form-driven payments:

* **Event ticket purchases** — sell tickets via a Gravity Form
* **Donation forms** — accept crypto donations with full form customization
* **Product order forms** — per-submission payment via hosted checkout
* **Service booking** — pay-to-submit intake forms
* **Membership / subscription intake** — upfront crypto payment

= Why crypto payments? =

* **No chargebacks** — blockchain transactions are irreversible
* **Instant settlement** — seconds, not days
* **No FX fees** — USDC is USD, no conversion overhead for international customers
* **Lower fees** than card processors — cents on-chain vs. 2.9% + 30¢
* **Global reach** — no bank-country restrictions

= How it works =

1. Customer submits your Gravity Form
2. Plugin creates an AlgoVoi checkout link and redirects the customer
3. Customer pays with their crypto wallet (Pera, Defly, HashPack, Freighter, LOBSTR, etc.)
4. On-chain confirmation happens in seconds — the form entry is marked **Paid**
5. Gravity Forms notifications, confirmations, and Add-On feeds fire as normal

= Supported chains =

* **Algorand** — USDC (ASA 31566704) + native ALGO
* **VOI** — aUSDC (ARC-200) + native VOI
* **Hedera** — USDC (HTS 0.0.456858) + native HBAR
* **Stellar** — USDC (Circle) + native XLM

All 16 networks (mainnet + testnet) supported.

= Payout management =

AlgoVoi Cloud centrally manages payout wallet addresses — configure them once in your AlgoVoi dashboard, and every form payment lands there automatically.

== Installation ==

1. Go to **Plugins > Add New**, search for **AlgoVoi for Gravity Forms** and click **Install Now**
2. Click **Activate**
3. Go to **Forms > Settings > AlgoVoi**
4. Enter your AlgoVoi API key (starts with `algv_`) from https://dash.algovoi.co.uk
5. Leave the API Base URL as the default `https://cloud.algovoi.co.uk`
6. Edit any form → add an **AlgoVoi** feed via the Payment Add-On framework
7. Set the amount field and network, publish the form

A free AlgoVoi Cloud account is required. Sign up at https://dash.algovoi.co.uk/signup

**Requirements:** Gravity Forms 2.6+ with the Payments Add-On framework (any paid license tier).

== Frequently Asked Questions ==

= Do customers need a crypto wallet? =

Yes — payers use their existing crypto wallet. Most are free and take under a minute to set up. No AlgoVoi account is needed on the customer side.

= Does this work with any Gravity Forms add-on? =

Yes. AlgoVoi fires the standard Gravity Forms payment lifecycle events, so notifications, confirmations, user registration, post creation, Zapier feeds, and other Add-Ons all work normally on payment completion.

= Can I still accept card / PayPal alongside AlgoVoi? =

Yes — use Gravity Forms' conditional logic to offer AlgoVoi as one option on a multi-gateway form.

= Where does the money go? =

Directly to the payout wallet addresses you configure in your AlgoVoi Cloud dashboard. AlgoVoi never holds your funds — settlement is on-chain.

= Are submissions GDPR-compliant? =

The plugin does not store customer payment details. Only the on-chain transaction ID is saved to the entry meta as an audit reference.

= What happens if the payment fails? =

The Gravity Forms entry is marked **Failed**. If the customer doesn't retry within 1 hour, the checkout session expires and the entry is cancelled.

== Screenshots ==

1. AlgoVoi settings panel at **Forms > Settings > AlgoVoi**.
2. Adding an AlgoVoi feed to an existing Gravity Form.
3. Hosted AlgoVoi checkout page with chain and wallet selection.
4. Gravity Forms entry showing **Paid** status and on-chain TX ID reference.

== Changelog ==

= 1.0.0 =
* Initial release
* All 16 AlgoVoi networks supported (Algorand, VOI, Hedera, Stellar — mainnet + testnet)
* HMAC-SHA256 webhook verification with timing-safe comparison
* Amount sanity validation (0 < amount < 1,000,000)
* HTTPS-enforced outbound requests
* 65KB webhook body cap (DoS protection)

== Upgrade Notice ==

= 1.0.0 =
Initial stable release. Safe for production use.
