# WordPress.org Plugin Directory — Submission Package

Three plugins ready for WordPress.org. Submit one at a time at
**https://wordpress.org/plugins/developers/add/** (WordPress.org account required — sign up at https://login.wordpress.org/register/).

## Plugins to submit

| Display name | Proposed slug | Zip | Source |
|---|---|---|---|
| AlgoVoi Payment Gateway | `algovoi-payment-gateway` | `dist/algovoi-woocommerce.zip` | `woocommerce/` |
| AlgoVoi for GiveWP | `algovoi-for-givewp` | `dist/algovoi-givewp.zip` | `no-code/givewp/algovoi-givewp/` |
| AlgoVoi for Gravity Forms | `algovoi-for-gravity-forms` | `dist/algovoi-gravity-forms.zip` | `no-code/gravity-forms/algovoi-gravity-forms/` |

---

## Pre-submission sanity check

Ran on 2026-04-19:

- ✅ All three main PHP files declare `License: GPL-2.0-or-later` (GPL-compatible — WP.org requirement)
- ✅ All three `readme.txt` files declare `License: GPLv2 or later` with the correct URI
- ✅ All three have `Tested up to: 6.9.4` and `Requires PHP: 7.4`+
- ✅ `LICENSE-PLUGINS.md` at repo root explains the dual-license (BUSL elsewhere, GPL for these three)
- ✅ No emojis, no premium-only code paths, no telemetry/analytics, no third-party CDN assets
- ✅ Outbound requests HTTPS-only, HMAC-verified
- ✅ Zips have been regenerated and uploaded to GitHub release `v1.0.0-nocode`

---

## Submission flow (per plugin, ~10 min each)

1. **Log in** to https://wordpress.org/plugins/developers/add/
2. **Upload the zip** — one of the three listed above
3. **Fill the plugin description** — WP.org auto-pulls from the zip's `readme.txt`, but confirms the slug and display name
4. **Submit** — the plugin enters the manual review queue
5. **Wait** — initial review typically 1–2 weeks. Reviewers check for GPL compatibility, code style, security, and policy issues. They email feedback if anything needs fixing.
6. **After approval** — you'll receive SVN credentials. Push `trunk` + tag the stable version.

## Copy-paste submission descriptions

WordPress.org uses your `readme.txt` for the listing page, but the submission form asks for a **short plain-text description**. Use these:

### AlgoVoi Payment Gateway (WooCommerce)
```
Accept USDC stablecoin payments on Algorand, VOI, Hedera, and Stellar in WooCommerce. Hosted checkout + browser extension flows. Instant on-chain settlement, no chargebacks, no FX fees. Routes through AlgoVoi Cloud (one API key, payouts managed centrally) or direct API.
```

### AlgoVoi for GiveWP
```
Accept crypto donations (USDC + native tokens on Algorand, VOI, Hedera, Stellar) through GiveWP. No chargebacks, no FX fees. Ideal for charities and nonprofits that want instant on-chain donation settlement with donor data staying inside GiveWP.
```

### AlgoVoi for Gravity Forms
```
Accept crypto payments on any Gravity Form — event tickets, donations, product orders, service bookings. Redirect to AlgoVoi hosted checkout, customer pays with their crypto wallet, entry marked Paid on on-chain confirmation. Works with the Payment Add-On framework.
```

---

## SVN push (after approval)

Once WP.org approves a plugin they give you SVN credentials. For each plugin:

```bash
# Check out the assigned SVN repo
svn co https://plugins.svn.wordpress.org/<slug> wp-<slug>-svn
cd wp-<slug>-svn

# Copy plugin contents to trunk/
cp -r ../source-dir/* trunk/

# Tag the stable version
svn cp trunk tags/<version>
svn add tags/<version> --force

# Commit
svn ci -m "Initial release v<version>"
```

Use the **unzipped contents** of the release zip (not the zip itself). The zip's folder structure (`algovoi-woocommerce/`, `algovoi-givewp/`, `algovoi-gravity-forms/`) should be preserved under `trunk/`.

---

## Plugin assets (icons + banners) — produce after approval

Once slugs are assigned, upload via SVN to `<slug>/assets/`:

| File | Dimensions | Purpose |
|---|---|---|
| `icon-128x128.png` | 128×128 | Search results thumbnail |
| `icon-256x256.png` | 256×256 | Plugin page thumbnail (retina) |
| `banner-772x250.png` | 772×250 | Plugin page banner |
| `banner-1544x500.png` | 1544×500 | Retina banner |
| `screenshot-1.png`, `-2.png`, ... | any reasonable | Matches the readme.txt Screenshots section |

Icon we can reuse from `shared/logo/`:
- `algovoi-mark-256.png` → upload as `icon-256x256.png`
- Generate a 128×128 variant: `npx @resvg/resvg-js-cli --fit-width 128 shared/logo/algovoi-mark.svg icon-128x128.png`

Banners and screenshots need to be produced — we don't have them yet.

---

## Post-approval follow-ups

When each listing goes live:
- [ ] Update this repo's plugin `readme.txt` `Stable tag` if we push a new version via SVN
- [ ] Update `dash.algovoi.co.uk/connect` wizard copy to mention "install from WordPress admin" alongside the current zip download
- [ ] Update `marketplace_submissions.md` memory: 🔄 → ✅ with the live plugin URL
- [ ] Update each plugin's `README.md` with a "Download from WordPress.org" link at the top

## Troubleshooting

If a reviewer flags our GPL license as inconsistent with the broader BUSL repo,
point them at `LICENSE-PLUGINS.md` which documents the dual-license. WP.org
reviewers do accept dual-licensed plugins where the WP.org distribution is
under a GPL-compatible license.
