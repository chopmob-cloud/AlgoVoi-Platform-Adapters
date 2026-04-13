<?php
declare(strict_types=1);

namespace Algovoi\Payment\Helper;

use Magento\Framework\App\Helper\AbstractHelper;
use Magento\Framework\App\Helper\Context;
use Magento\Framework\HTTP\Client\Curl;
use Magento\Store\Model\ScopeInterface;

class ApiHelper extends AbstractHelper
{
    private const HOSTED_NETWORKS = ['algorand_mainnet', 'voi_mainnet', 'hedera_mainnet', 'stellar_mainnet'];

    private Curl $curl;

    public function __construct(Context $context, Curl $curl)
    {
        parent::__construct($context);
        $this->curl = $curl;
    }

    public function getConfigValue(string $field, ?int $storeId = null): ?string
    {
        return $this->scopeConfig->getValue(
            'payment/algovoi/' . $field,
            ScopeInterface::SCOPE_STORE,
            $storeId
        );
    }

    public function getApiBase(?int $storeId = null): string
    {
        return rtrim((string)$this->getConfigValue('api_base_url', $storeId), '/');
    }

    public function getApiKey(?int $storeId = null): string
    {
        return (string)$this->getConfigValue('api_key', $storeId);
    }

    public function getTenantId(?int $storeId = null): string
    {
        return (string)$this->getConfigValue('tenant_id', $storeId);
    }

    public function getWebhookSecret(?int $storeId = null): string
    {
        return (string)$this->getConfigValue('webhook_secret', $storeId);
    }

    public function getDefaultNetwork(?int $storeId = null): string
    {
        return (string)($this->getConfigValue('default_network', $storeId) ?: 'algorand_mainnet');
    }

    public function isValidNetwork(string $network): bool
    {
        return in_array($network, self::HOSTED_NETWORKS, true);
    }

    /**
     * Create a payment link via the AlgoVoi API.
    
 * AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Copyright (c) 2026 Christopher Hopley (ilovechicken.co.uk). BSL 1.1.
 */
    public function createPaymentLink(
        float $amount,
        string $currency,
        string $label,
        string $network,
        string $redirectUrl = '',
        ?int $storeId = null
    ): ?array {
        if (!$this->isValidNetwork($network)) {
            $network = 'algorand_mainnet';
        }

        $payload = [
            'amount'            => round($amount, 2),
            'currency'          => strtoupper($currency),
            'label'             => $label,
            'preferred_network' => $network,
        ];
        if ($redirectUrl) {
            $payload['redirect_url'] = $redirectUrl;
            $payload['expires_in_seconds'] = 3600;
        }

        $apiBase = $this->getApiBase($storeId);
        $url = $apiBase . '/v1/payment-links';

        $this->curl->setHeaders([
            'Content-Type'  => 'application/json',
            'Authorization' => 'Bearer ' . $this->getApiKey($storeId),
            'X-Tenant-Id'   => $this->getTenantId($storeId),
        ]);
        $this->curl->setOption(CURLOPT_SSL_VERIFYPEER, true);
        $this->curl->setOption(CURLOPT_SSL_VERIFYHOST, 2);
        $this->curl->setOption(CURLOPT_TIMEOUT, 30);
        $this->curl->post($url, json_encode($payload));

        $status = $this->curl->getStatus();
        $body = json_decode($this->curl->getBody(), true);

        if (($status < 200 || $status >= 300) || empty($body['checkout_url'])) {
            return null;
        }
        return $body;
    }

    /**
     * Extract short token from a checkout URL.
     */
    public function extractToken(string $checkoutUrl): string
    {
        if (preg_match('#/checkout/([A-Za-z0-9_-]+)$#', $checkoutUrl, $m)) {
            return $m[1];
        }
        return '';
    }

    /**
     * Verify hosted checkout return — cancel-bypass prevention.
     */
    public function verifyHostedReturn(string $token, ?int $storeId = null): bool
    {
        if (!$token) {
            return false;
        }

        $url = $this->getApiBase($storeId) . '/checkout/' . rawurlencode($token);

        $verifyCurl = clone $this->curl;
        $verifyCurl->setOption(CURLOPT_SSL_VERIFYPEER, true);
        $verifyCurl->setOption(CURLOPT_SSL_VERIFYHOST, 2);
        $verifyCurl->setOption(CURLOPT_TIMEOUT, 15);
        $verifyCurl->get($url);

        if ($verifyCurl->getStatus() !== 200) {
            return false;
        }

        $data = json_decode($verifyCurl->getBody(), true) ?? [];
        return in_array($data['status'] ?? '', ['paid', 'completed', 'confirmed'], true);
    }

    /**
     * Verify webhook HMAC signature.
     */
    public function verifyWebhookSignature(string $rawBody, string $signature, ?int $storeId = null): bool
    {
        $secret = $this->getWebhookSecret($storeId);

        // Reject if secret is not configured
        if (empty($secret)) {
            return false;
        }

        $expected = base64_encode(hash_hmac('sha256', $rawBody, $secret, true));

        return hash_equals($expected, $signature);
    }
}
