<?php declare(strict_types=1);

namespace AlgovoiPayment\Helper;

use Shopware\Core\System\SystemConfig\SystemConfigService;

class ApiHelper
{
    /** Algod node config per chain
 * AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 — see LICENSE for details.
 */
    public const ALGOD = [
        'algorand-mainnet' => [
            'url'      => 'https://mainnet-api.algonode.cloud',
            'asset_id' => 31566704,
            'dec'      => 6,
            'ticker'   => 'USDC',
        ],
        'voi-mainnet' => [
            'url'      => 'https://mainnet-api.voi.nodely.io',
            'asset_id' => 302190,
            'dec'      => 6,
            'ticker'   => 'aUSDC',
        ],
    ];

    public function __construct(private readonly SystemConfigService $config) {}

    public function getApiBase(): string
    {
        return rtrim((string)($this->config->get('AlgovoiPayment.config.apiBaseUrl') ?? 'https://api1.ilovechicken.co.uk'), '/');
    }

    public function getApiKey(): string
    {
        return (string)($this->config->get('AlgovoiPayment.config.apiKey') ?? '');
    }

    public function getTenantId(): string
    {
        return (string)($this->config->get('AlgovoiPayment.config.tenantId') ?? '');
    }

    public function getNetwork(): string
    {
        return (string)($this->config->get('AlgovoiPayment.config.network') ?? 'algorand_mainnet');
    }

    public function getWebhookSecret(): string
    {
        return (string)($this->config->get('AlgovoiPayment.config.webhookSecret') ?? '');
    }

    public function createPaymentLink(float $amount, string $currency, string $label, string $redirectUrl, string $network = ''): array
    {
        $payload = json_encode([
            'amount'             => round($amount, 2),
            'currency'           => $currency,
            'label'              => $label,
            'preferred_network'  => $network ?: $this->getNetwork(),
            'redirect_url'       => $redirectUrl,
            'expires_in_seconds' => 3600,
        ]);

        $ch = curl_init($this->getApiBase() . '/v1/payment-links');
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => $payload,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 30,
            CURLOPT_HTTPHEADER     => [
                'Content-Type: application/json',
                'Authorization: Bearer ' . $this->getApiKey(),
                'X-Tenant-Id: ' . $this->getTenantId(),
            ],
        ]);
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        $body = json_decode($response, true) ?? [];
        $body['_http_code'] = $httpCode;
        return $body;
    }

    public function scrapeCheckoutPage(string $checkoutUrl): array
    {
        $ch = curl_init($checkoutUrl);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 15,
            CURLOPT_FOLLOWLOCATION => true,
        ]);
        $html = curl_exec($ch);
        curl_close($ch);

        $receiver = $memo = '';
        if ($html) {
            if (preg_match('/onclick="copyText\(\'([A-Z2-7]{58})\'/', $html, $m)) {
                $receiver = $m[1];
            }
            if (preg_match('/onclick="copyText\(\'(algovoi:[A-Za-z0-9_-]+)\'/', $html, $m)) {
                $memo = $m[1];
            }
        }

        return ['receiver' => $receiver, 'memo' => $memo];
    }

    public function verifyPayment(string $token, string $txId): array
    {
        $ch = curl_init($this->getApiBase() . '/checkout/' . rawurlencode($token) . '/verify');
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => json_encode(['tx_id' => $txId]),
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 30,
            CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
        ]);
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        $body = json_decode($response, true) ?? [];
        $body['_http_code'] = $httpCode;
        return $body;
    }

    public static function getAlgodConfig(string $chain): array
    {
        return self::ALGOD[$chain] ?? self::ALGOD['algorand-mainnet'];
    }
}
