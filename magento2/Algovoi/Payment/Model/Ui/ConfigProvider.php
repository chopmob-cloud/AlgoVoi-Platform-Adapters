<?php
/**
 * AlgoVoi: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 - see LICENSE for details.
 */
declare(strict_types=1);

namespace Algovoi\Payment\Model\Ui;

use Algovoi\Payment\Helper\ApiHelper;
use Algovoi\Payment\Model\AlgovoiPayment;
use Magento\Checkout\Model\ConfigProviderInterface;

class ConfigProvider implements ConfigProviderInterface
{
    private ApiHelper $apiHelper;

    public function __construct(ApiHelper $apiHelper)
    {
        $this->apiHelper = $apiHelper;
    }

    public function getConfig(): array
    {
        return [
            'payment' => [
                AlgovoiPayment::CODE => [
                    'chains' => [
                        ['value' => 'algorand_mainnet', 'label' => 'Algorand — USDC',  'colour' => '#3b82f6'],
                        ['value' => 'voi_mainnet',      'label' => 'VOI — aUSDC',      'colour' => '#8b5cf6'],
                        ['value' => 'hedera_mainnet',   'label' => 'Hedera — USDC',    'colour' => '#00a9a5'],
                        ['value' => 'stellar_mainnet',  'label' => 'Stellar — USDC',   'colour' => '#7C63D0'],
                        ['value' => 'base_mainnet',     'label' => 'Base — USDC',      'colour' => '#0052ff'],
                        ['value' => 'solana_mainnet',   'label' => 'Solana — USDC',    'colour' => '#9945ff'],
                        ['value' => 'tempo_mainnet',    'label' => 'Tempo — USDCe',    'colour' => '#f59e0b'],
                    ],
                    'defaultNetwork' => $this->apiHelper->getDefaultNetwork(),
                    'redirectUrl'    => '', // Set after order placement via JS
                ],
            ],
        ];
    }
}
