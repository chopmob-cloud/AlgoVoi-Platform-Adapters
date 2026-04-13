<?php
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
        ];
    }
}
