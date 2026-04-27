<?php
/**
 * AlgoVoi: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 - see LICENSE for details.
 */
/**
 * AlgoVoi Payment Gateway for Magento 2
 *
 * Accept USDC / aUSDC / USDCe stablecoin payments on Algorand, VOI, Hedera, Stellar, Base, Solana and Tempo.
 *
 * @package Algovoi_Payment
 * @version 1.2.0
 * @license BSL-1.1
 */

\Magento\Framework\Component\ComponentRegistrar::register(
    \Magento\Framework\Component\ComponentRegistrar::MODULE,
    'Algovoi_Payment',
    __DIR__
);
