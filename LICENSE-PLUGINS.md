# Dual-Licensing Notice — WordPress Plugin Directories

This repository is primarily licensed under the **Business Source License 1.1**
(see [`LICENSE`](./LICENSE)). However, the three WordPress plugin directories
listed below are **dual-licensed** and may additionally be used under the terms
of the **GNU General Public License v2.0 or later** (GPL-2.0-or-later).

## Dual-licensed directories

- `woocommerce/` — AlgoVoi Payment Gateway for WooCommerce
- `no-code/givewp/algovoi-givewp/` — AlgoVoi for GiveWP
- `no-code/gravity-forms/algovoi-gravity-forms/` — AlgoVoi for Gravity Forms

Each plugin's main PHP file declares `License: GPL-2.0-or-later` in its header
block, and each includes a `readme.txt` file declaring the same license
for WordPress.org's plugin directory.

## Why dual-license?

WordPress.org's plugin directory requires plugins to be distributed under a
**GPL-v2-compatible license** ([source](https://developer.wordpress.org/plugins/wordpress-org/detailed-plugin-guidelines/#1-plugins-must-be-compatible-with-the-gnu-general-public-license)).
BUSL-1.1 is not GPL-compatible. To enable distribution through the WordPress
plugin directory — which is how most merchants discover WordPress plugins
inside their WP admin — we grant an additional GPL-2.0-or-later license for
these specific plugin directories.

## What this means in practice

- **If you obtain one of these three plugins from WordPress.org or from the
  respective plugin directory in your WordPress admin**, you are using it under
  GPL-2.0-or-later.
- **If you obtain a plugin (or any other part of this repository) through any
  other channel — e.g. cloning the GitHub repo, downloading a release zip
  directly, or redistributing as part of another project** — the default
  BUSL-1.1 license applies (including its non-production and change-date
  provisions), unless you are using only the three directories above and
  choosing to rely on the GPL-2.0-or-later license grant.

## Everything else

The rest of this repository (all other adapter directories, the MCP server,
the native SDKs, the MPP/AP2/x402 implementations, the no-code connectors
other than GiveWP and Gravity Forms, etc.) remains under BUSL-1.1 only.

## Questions

For licensing questions, contact support via the repository issue tracker
at https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/issues.
