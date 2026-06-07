# Subdirectory Licensing Notice

This repository is primarily licensed under the **Business Source License 1.1**
(see [`LICENSE`](./LICENSE)). However, a handful of subdirectories are
**licensed separately** to enable distribution through public registries that
require permissive or GPL-compatible licenses.

## Permissively-licensed directories

### MIT

- [`mcp-server/`](./mcp-server/) — AlgoVoi MCP server (TypeScript + Python packages)

The MCP server is a pure API client: it exposes AlgoVoi's public endpoints to
MCP-compatible AI clients (Claude Desktop, Cursor, Windsurf, etc.). It contains
no proprietary business logic that warrants BUSL-1.1 protection. Licensing it
under MIT enables:

- Inclusion in the official MCP registry and community directories (Glama,
  MCP.so, PulseMCP, awesome-mcp-servers)
- Unrestricted integration into downstream MCP clients and tool runners
- Standard SPDX detection by GitHub, npm, PyPI, and Glama

The MIT grant covers everything under `mcp-server/`, including the TypeScript
package published to npm as `@algovoi/mcp-server`, the Python package
published to PyPI as `algovoi-mcp`, the Dockerfile used by Glama's inspector,
`server.json` registered with the official MCP registry, and test fixtures.

See [`mcp-server/LICENSE`](./mcp-server/LICENSE) for the full MIT text.

### GPL-2.0-or-later (dual-licensed with BUSL-1.1)

- `woocommerce/` — AlgoVoi Payment Gateway for WooCommerce
- `no-code/givewp/algovoi-givewp/` — AlgoVoi for GiveWP
- `no-code/gravity-forms/algovoi-gravity-forms/` — AlgoVoi for Gravity Forms

Each plugin's main PHP file declares `License: GPL-2.0-or-later` in its header
block, and each includes a `readme.txt` file declaring the same license for
WordPress.org's plugin directory.

WordPress.org requires plugins to be distributed under a **GPL-v2-compatible
license** ([policy source](https://developer.wordpress.org/plugins/wordpress-org/detailed-plugin-guidelines/#1-plugins-must-be-compatible-with-the-gnu-general-public-license)),
which BUSL-1.1 is not. These three directories are dual-licensed so end users
obtaining them through WordPress.org (or via the WordPress admin's plugin
uploader) are covered under GPL-2.0-or-later; anyone obtaining them through any
other channel can choose either licence.

## What this means in practice

| How you got the code | Applicable licence |
|---|---|
| `npm install @algovoi/mcp-server` or `pip install algovoi-mcp` | MIT |
| Anything else inside `mcp-server/` (cloned, downloaded, packaged) | MIT |
| A WordPress plugin installed through WordPress.org or WP admin | GPL-2.0-or-later |
| The three WP plugin directories obtained through any other channel | GPL-2.0-or-later **or** BUSL-1.1 (your choice) |
| Everything else in this repository | BUSL-1.1 only |

## BUSL-1.1 still covers

The rest of this repository — all core adapter directories outside the lists
above, the MPP / AP2 / x402 implementations, the native SDKs (Python, PHP, Go,
Rust), the no-code connectors other than GiveWP and Gravity Forms, and the
AlgoVoi Cloud components — remains under BUSL-1.1 only, including its
non-production and change-date provisions.

## Questions

For licensing questions, open an issue at
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/issues.
