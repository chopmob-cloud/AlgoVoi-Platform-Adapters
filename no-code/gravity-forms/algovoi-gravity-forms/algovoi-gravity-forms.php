<?php
/**
 * Plugin Name:     AlgoVoi for Gravity Forms
 * Plugin URI:      https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Description:     Accept crypto payments (USDC on Algorand, VOI, Hedera & Stellar) in Gravity Forms.
 * Version:         1.0.0
 * Author:          AlgoVoi
 * Author URI:      https://algovoi.co.uk
 * License:         MIT
 * Text Domain:     algovoi-gf
 * Requires PHP:    7.4
 * Requires at least: 5.8
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
