<?php
/**
 * AlgoVoi WooCommerce child theme — functions.php
 * Adds the AlgoVoi "pay with crypto" banner and any WooCommerce tweaks.
 */

// Enqueue parent (Storefront) styles then ours
add_action('wp_enqueue_scripts', function () {
    wp_enqueue_style(
        'storefront-style',
        get_template_directory_uri() . '/style.css'
    );
    wp_enqueue_style(
        'algovoi-woo-style',
        get_stylesheet_directory_uri() . '/style.css',
        array('storefront-style'),
        '1.3'
    );
});

// AlgoVoi crypto payment banner below the site header
add_action('wp_body_open', function () {
    echo '<div class="algovoi-banner">'
       . '<strong>AlgoVoi</strong>'
       . '&nbsp;·&nbsp;Pay with USDC on Algorand or aUSDC on VOI'
       . '<a href="https://www.algovoi.co.uk" target="_blank" rel="noopener">Learn more →</a>'
       . '</div>';
});

// Show 12 products per page on the shop
add_filter('loop_shop_per_page', function () {
    return 12;
}, 20);

// Show products in 3 columns
add_filter('loop_shop_columns', function () {
    return 3;
});
