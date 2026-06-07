=== AlgoVoi Payment Gateway ===
Contributors: algovoi
Tags: woocommerce, crypto, usdc, algorand, stablecoin
Requires at least: 6.4
Tested up to: 6.9
Requires PHP: 8.0
WC requires at least: 7.0
WC tested up to: 10.6.2
Stable tag: 2.4.2
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Accept USDC stablecoin payments on Algorand, VOI, Hedera, and Stellar. Instant settlement, no chargebacks, no FX fees.

== Description ==

AlgoVoi lets WooCommerce merchants accept USDC stablecoin payments settled directly on-chain — no intermediary holds your funds, no chargeback window, and no currency conversion fees for international orders.

**Two payment flows:**

* **Hosted checkout** — Customer selects their chain (Algorand, VOI, Hedera, or Stellar) and is redirected to a secure AlgoVoi-hosted payment page. Works with any compatible wallet (Pera, Defly, Lute, HashPack, Freighter, LOBSTR).
* **Browser extension** — Customer pays directly on the thank-you page using the AlgoVoi browser extension. No redirect. Supports Algorand and VOI.

**Why AlgoVoi?**

* Instant on-chain settlement — funds arrive in seconds, not days
* No chargebacks — payments are irreversible by design
* No FX fees — USDC is USD, no conversion overhead for international orders
* Works alongside card/PayPal — customers choose their preferred method
* Full security hardening — HMAC webhook verification, SSRF protection, timing-safe comparisons

**Supported chains:**

* Algorand — USDC (ASA 31566704)
* VOI — aUSDC (ASA 302190)
* Hedera — USDC (HTS token 0.0.456858)
* Stellar — USDC (Circle issuer)

== Installation ==

1. Go to **Plugins > Add New**, search for **AlgoVoi** and click **Install Now**
2. Click **Activate**
3. Go to **WooCommerce > Settings > Payments**
4. Enable **AlgoVoi** and/or **AlgoVoi Extension**
5. Enter your AlgoVoi API key (starts with `algv_`) from https://dash.algovoi.co.uk
6. Leave the API Base URL as the default `https://cloud.algovoi.co.uk` — tenant ID and payout addresses are managed centrally in your Cloud dashboard

A free AlgoVoi Cloud account is required. Sign up at https://dash.algovoi.co.uk/signup

== Frequently Asked Questions ==

= Do I need a crypto wallet to use this? =

No. You only need an AlgoVoi merchant account. Your customers need a compatible wallet to pay.

= What currencies are supported? =

Orders are placed in your store currency (GBP, USD, EUR, etc.) and converted to USDC at the current rate at checkout.

= Are chargebacks possible? =

No. Blockchain transactions are irreversible by design. This is a significant advantage over card payments for digital goods.

= Which wallets are supported? =

Algorand: Pera, Defly, Lute. VOI: Nautilus. Hedera: HashPack. Stellar: Freighter, LOBSTR. Any wallet compatible with the respective chain works.

= Is this plugin GDPR compliant? =

The plugin does not store customer payment details. On-chain transaction IDs are stored in WooCommerce order meta as a payment reference only.

== Changelog ==

= 2.4.2 =
* Stellar mainnet support added (USDC via Circle)
* Replay attack prevention on webhook verification
* Security hardening: timing-safe comparisons, SSRF guard, empty-secret rejection

= 2.0.0 =
* Hedera mainnet support
* Two-gateway architecture (hosted + extension)
* Full security audit applied (April 2026)

= 1.0.0 =
* Initial release — Algorand and VOI support

== Upgrade Notice ==

= 2.4.2 =
Adds Stellar support and security hardening. Recommended for all merchants.
