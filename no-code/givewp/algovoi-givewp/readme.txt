=== AlgoVoi for GiveWP ===
Contributors: algovoi
Tags: donations, crypto, usdc, algorand, stellar, givewp, blockchain, payments, stablecoin
Requires at least: 5.8
Tested up to: 6.9.4
Requires PHP: 7.4
Stable tag: 1.0.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Accept crypto donations (USDC on Algorand, VOI, Hedera, Stellar + native tokens) through GiveWP. No chargebacks, no FX fees.

== Description ==

**AlgoVoi for GiveWP** adds AlgoVoi as a payment gateway inside GiveWP, letting your donors pay in crypto from any compatible wallet and settle the donation directly on-chain.

Ideal for charities and nonprofits who want:

* **No intermediary** holding donation funds
* **No chargebacks** — blockchain transactions are irreversible
* **No FX fees** for international donors — USDC is USD, no conversion
* **Instant settlement** — funds arrive in seconds, not days
* **Lower fees** than card processors — a few cents on-chain vs. 2.9% + 30¢

= How it works =

1. Donor selects **AlgoVoi** on your GiveWP donation form
2. Plugin creates a secure AlgoVoi checkout link and redirects the donor
3. Donor pays with their crypto wallet (Pera, Defly, HashPack, Freighter, LOBSTR, etc.)
4. On-chain confirmation happens in seconds — the donation is marked **Complete** in GiveWP
5. All donor data and reports stay inside GiveWP — nothing moves off your site

= Supported chains =

* **Algorand** — USDC (ASA 31566704) + native ALGO
* **VOI** — aUSDC (ARC-200) + native VOI
* **Hedera** — USDC (HTS 0.0.456858) + native HBAR
* **Stellar** — USDC (Circle) + native XLM

Mainnet and testnet — all 16 networks supported.

= Payout management =

AlgoVoi Cloud manages your payout wallet addresses centrally — you add them once to your AlgoVoi dashboard and every donation lands there. No per-site wallet configuration.

== Installation ==

1. Go to **Plugins > Add New**, search for **AlgoVoi for GiveWP** and click **Install Now**
2. Click **Activate**
3. Go to **Donations > Settings > Payment Gateways**
4. Enable **AlgoVoi**
5. Enter your AlgoVoi API key (starts with `algv_`) from https://dash.algovoi.co.uk
6. Leave the API Base URL as the default `https://cloud.algovoi.co.uk`

A free AlgoVoi Cloud account is required. Sign up at https://dash.algovoi.co.uk/signup

**Requirements:** GiveWP 2.25+ installed and activated.

== Frequently Asked Questions ==

= Do donors need a crypto wallet? =

Yes — donors pay using their existing crypto wallet. Most supported wallets are free and take under a minute to set up. No account is required from the donor with AlgoVoi itself.

= Where does the money go? =

Directly to your AlgoVoi payout wallet addresses, which you control. AlgoVoi never holds donor funds. The settlement is on-chain and irreversible.

= Can I accept donations in GBP / USD / EUR? =

Donation forms can be in any GiveWP-supported currency. The amount is converted to USDC (or the chosen crypto) at the current rate when the donor checks out. Fiat accounting is preserved in GiveWP.

= Are transactions GDPR-compliant? =

The plugin does not store donor payment details. Only the on-chain transaction ID is stored in the GiveWP donation meta as an audit reference.

= What if a donor's transaction fails on-chain? =

The GiveWP donation stays in the **Pending** state. If the donor doesn't retry within 1 hour, the session expires and the donation is cancelled automatically.

= Can I still accept card / PayPal donations alongside AlgoVoi? =

Yes — AlgoVoi coexists with any other GiveWP gateway. Donors choose their preferred method on each form.

== Screenshots ==

1. AlgoVoi listed as a payment gateway inside **Donations > Settings > Payment Gateways**.
2. Donor-facing AlgoVoi option on the GiveWP donation form.
3. Hosted AlgoVoi checkout page showing chain selection and wallet options.
4. Completed donation in GiveWP with on-chain transaction ID linked from the donation meta.

== Changelog ==

= 1.0.0 =
* Initial release
* All 16 AlgoVoi networks supported (Algorand, VOI, Hedera, Stellar — mainnet + testnet)
* HMAC-SHA256 webhook verification
* Amount sanity validation (0 < amount < 1,000,000)
* HTTPS-enforced outbound requests
* 65KB webhook body cap (DoS protection)
* Timing-safe HMAC comparison

== Upgrade Notice ==

= 1.0.0 =
Initial stable release. Safe for production use.
