<?php
/**
 * AlgoVoi Payment Gateway for Magento 2
 *
 * Accept USDC stablecoin payments on Algorand, VOI, Hedera, and Stellar.
 *
 * @package Algovoi_Payment
 * @version 1.0.0
 * @license BSL-1.1
 */

\Magento\Framework\Component\ComponentRegistrar::register(
    \Magento\Framework\Component\ComponentRegistrar::MODULE,
    'Algovoi_Payment',
    __DIR__
);
