# CMS Adapter Smoke Testing Guide

This guide covers how to run end-to-end smoke tests for the three CMS
adapters: Drupal Commerce, Easy Digital Downloads, and Ghost. Each
adapter ships with a two-phase smoke script.

**Phase 1** needs nothing — it exercises security guards, input
validation, and (where possible) the live AlgoVoi gateway. It runs now.

**Phase 2** needs a running sandbox of the target platform. Because each
platform requires an account (Ghost Pro, WordPress host, Drupal host),
you provision the sandbox, paste the URL + any credentials here, and we
run the smoke together.

---

## Quick reference — current status (2026-04-15)

| Adapter | Phase 1 | Phase 2 |
|---|---|---|
| Ghost | ✅ 34/34 PASS (incl. live 4-chain AlgoVoi gateway round-trip) | Pending a Ghost Pro trial |
| EDD (WordPress) | ✅ 27/27 static PASS | Pending a WP sandbox with EDD 3.2+ |
| Drupal Commerce | ✅ 43/43 static PASS | Pending a Drupal 10 + Commerce 2 sandbox |

---

## 1. Ghost — easiest

**Sandbox options:**
- **Ghost Pro 14-day trial** — https://ghost.org/pricing/ → "Start your 14-day free trial". Needs email + credit card (no charge until day 14). Best option — full Admin API access.
- **Self-hosted Docker** — `docker run -p 2368:2368 ghost:5-alpine`. No payment, but you'll lose state on restart unless you mount a volume.

**Steps once you have a blog:**

```
Ghost admin → Settings → Integrations → + Add custom integration
  Name: "AlgoVoi Payments"
  Copy the Admin API Key — format: <24 hex>:<64 hex>
```

**Run smoke:**

```bash
cd ai-adapters/ghost   # or wherever the ghost adapter lives
export GHOST_URL="https://your-blog.ghost.io"
export GHOST_ADMIN_KEY="65abcdef...:0123456789abcdef..."
export ALGOVOI_KEY="algv_..."
export TENANT_ID="your-tenant-uuid"

python -X utf8 smoke_test_ghost.py \
  JW4OOGMKDI4SVMLZIJQ6STJ5CA5TJLOVA4GKQCXZWWTXKOE35VHA \
  ZNCDOFTBIOX2QJSSGC6X6OOWYIR56VD3Q3VMYTTS2VW5PNODJPKA \
  '0.0.10376692@1776147485.122643710' \
  354a818e5fdf017d632338b50daccbf4aa7d5878b4e68432174a282725f83c1f
```

The 4 TX IDs are the reusable smoke TXs from 2026-04-14 Claude/OpenAI Phase 2 — same tenant, re-usable per `ai_adapters.md`.

---

## 2. Easy Digital Downloads — WordPress sandbox

**Sandbox options (in order of speed):**

- **[tastewp.com](https://tastewp.com)** — free, 7 days, fastest to spin up. Click **Create a free site**, pick a one-hour or 7-day WP install.
- **[instawp.com](https://instawp.com)** — free tier, 24 h to 14 days depending on template. Supports plugin pre-install.
- **[LocalWP](https://localwp.com/)** — free, runs locally, unlimited time. Requires Docker or Flywheel desktop app.

**After your sandbox is up:**

1. Log into `/wp-admin` (tastewp gives you a direct magic-login link).
2. **Plugins → Add New** → search "Easy Digital Downloads" → Install + Activate.
3. Upload our plugin:
   - Plugins → Add New → Upload Plugin
   - Zip `easy-digital-downloads/` from this repo (or just the `algovoi-edd.php` file in a zip)
   - Install + Activate.
4. Configure at **Downloads → Settings → Payments → AlgoVoi**:
   - API Base URL: `https://api1.ilovechicken.co.uk`
   - API Key: your `algv_*` key
   - Tenant ID: your tenant UUID
   - Webhook Secret: pick something, remember it for the smoke
   - Default network: Algorand
5. Under **Downloads → Settings → Payments → General**, enable AlgoVoi.
6. Create a test **Download** (e.g. "Test Product" at $0.99).
7. Register the webhook URL (`https://your-sandbox.tastewp.com/wp-json/algovoi-edd/v1/webhook`) in your AlgoVoi dashboard.

**Run smoke:**

```bash
cd easy-digital-downloads/
export EDD_WEBHOOK_SECRET="the-secret-you-set-in-admin"
# optional — for happy path:
# export EDD_TEST_PAYMENT_ID=42   # id of a pending EDD payment
# export ALGOVOI_TX_ID="JW4OOGMKDI4SVMLZIJQ6STJ5CA5TJLOVA4GKQCXZWWTXKOE35VHA"

python -X utf8 smoke_test_edd.py https://your-sandbox.tastewp.com
```

What it tests (Phase 2):

1. Webhook route exists (GET → 404/405)
2. POST without signature → 401
3. POST with bad signature → 401
4. Oversized body (>64 KB) → 400
5. Valid HMAC but missing fields → 400
6. Valid HMAC against non-existent order → 404
7. (Optional) Valid HMAC + existing pending payment → 200 or 402

---

## 3. Drupal Commerce — toughest

**Sandbox options:**

- **[simplytest.me](https://simplytest.me)** — 40-minute free sandbox. Fastest. Select **Drupal 10** + add **Commerce** module. Then upload `commerce_algovoi/` as a zip.
- **[Pantheon free dev sandbox](https://pantheon.io/signup)** — longer-lived but requires an account.
- **Lando / DDEV** — local. Needs Docker.
- **`drush si` in a fresh Drupal 10 Composer project** — most control.

**After your sandbox is up:**

1. Install Commerce:
   ```
   composer require drupal/commerce
   drush en commerce commerce_payment commerce_cart commerce_checkout -y
   ```
2. Copy this module into `web/modules/contrib/commerce_algovoi/`:
   ```
   cp -r drupal-commerce/ /path/to/drupal/web/modules/contrib/commerce_algovoi/
   ```
3. Enable it:
   ```
   drush en commerce_algovoi -y
   ```
4. Configure the gateway at `/admin/commerce/config/payment-gateways`:
   - Click **+ Add payment gateway**
   - Choose **AlgoVoi (USDC on Algorand / VOI / Hedera / Stellar)**
   - Machine name: `algovoi_offsite` (default)
   - Fill in API Base URL, API Key, Tenant ID, Webhook Secret, Default network
5. Register webhook URL:
   `https://your-sandbox/payment/notify/algovoi/algovoi_offsite`

**Run smoke:**

```bash
cd drupal-commerce/
export DRUPAL_WEBHOOK_SECRET="the-secret-you-set-in-admin"

python -X utf8 smoke_test_drupal.py https://your-sandbox/ algovoi_offsite
```

---

## Full four-chain happy path (any of the three)

For any adapter, once the sandbox is live you can also do a FULL happy
path by re-using the 4 smoke TXs:

```
Algorand: JW4OOGMKDI4SVMLZIJQ6STJ5CA5TJLOVA4GKQCXZWWTXKOE35VHA
VOI:      ZNCDOFTBIOX2QJSSGC6X6OOWYIR56VD3Q3VMYTTS2VW5PNODJPKA
Hedera:   0.0.10376692@1776147485.122643710
Stellar:  354a818e5fdf017d632338b50daccbf4aa7d5878b4e68432174a282725f83c1f
```

These are reusable — AlgoVoi's gateway accepts the same on-chain TX ID
across different resource IDs for the same tenant (see `ai_adapters.md`
memory note 2026-04-15).

---

## What the Phase 2 smokes DON'T test

All three Phase 2 smokes focus on the webhook endpoint — that's the
security-critical path. They don't test:

- The **checkout redirect** (customer lands on AlgoVoi, pays, returns)
  — this is manual; open the test product in a browser and click
  through. Comet has reviewed the redirect flow; that's sufficient for
  v1.0.0 shipping.
- **Ghost's upgrade_member()** end-to-end — smoke hits the Admin API
  reachability check (GET /members/) but doesn't drive a full
  PUT/POST because that would leave test members in your Ghost admin.

If you want either of those exercised, let me know — I can extend the
smokes to go further.

---

Licensed under the [Business Source License 1.1](./LICENSE).
