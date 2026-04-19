<?php
/**
 * Plugin Name:     AlgoVoi for Gravity Forms
 * Plugin URI:      https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Description:     Accept crypto payments (USDC on Algorand, VOI, Hedera & Stellar) in Gravity Forms.
 * Version:         1.0.0
 * Author:          AlgoVoi
 * Author URI:      https://algovoi.co.uk
 * License:         GPL-2.0-or-later
 * License URI:     https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain:     algovoi-gf
 * Requires at least: 5.8
 * Tested up to:    6.9.4
 * Requires PHP:    7.4
 *
 * This WordPress plugin is dual-licensed: GPL-2.0-or-later (for WordPress.org
 * distribution and GPL compatibility) and BUSL-1.1 (for the wider AlgoVoi
 * Platform Adapters repository). See LICENSE-PLUGINS.md at the repo root.
 */

defined( 'ABSPATH' ) || exit;

define( 'ALGOVOI_GF_VERSION', '1.0.0' );
define( 'ALGOVOI_GF_FILE',    __FILE__ );
define( 'ALGOVOI_GF_DIR',     plugin_dir_path( __FILE__ ) );

// ── Boot when GF is ready ──────────────────────────────────────────────────────

add_action( 'gform_loaded', function () {
    if ( ! method_exists( 'GFForms', 'include_payment_addon_framework' ) ) {
        return;
    }
    GFForms::include_payment_addon_framework();
    require_once ALGOVOI_GF_DIR . 'class-gf-algovoi.php';
    GFAddOn::register( 'GF_AlgoVoi' );
}, 5 );

function gf_algovoi() {
    return GF_AlgoVoi::get_instance();
}
