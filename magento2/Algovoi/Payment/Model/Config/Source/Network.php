<?php
/**
 * AlgoVoi: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 - see LICENSE for details.
 */
declare(strict_types=1);

namespace Algovoi\Payment\Model\Config\Source;

use Magento\Framework\Data\OptionSourceInterface;

class Network implements OptionSourceInterface
{
    public function toOptionArray(): array
    {
        return [
            ['value' => 'algorand_mainnet', 'label' => __('Algorand — USDC')],
            ['value' => 'voi_mainnet',      'label' => __('VOI — aUSDC')],
            ['value' => 'hedera_mainnet',   'label' => __('Hedera — USDC')],
            ['value' => 'stellar_mainnet',  'label' => __('Stellar — USDC')],
            ['value' => 'base_mainnet',     'label' => __('Base — USDC')],
            ['value' => 'solana_mainnet',   'label' => __('Solana — USDC')],
            ['value' => 'tempo_mainnet',    'label' => __('Tempo — USDCe')],
        ];
    }
}
