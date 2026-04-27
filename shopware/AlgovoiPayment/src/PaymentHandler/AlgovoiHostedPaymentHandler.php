<?php
/**
 * AlgoVoi: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 - see LICENSE for details.
 */
 declare(strict_types=1);

namespace AlgovoiPayment\PaymentHandler;

use AlgovoiPayment\Helper\ApiHelper;
use Shopware\Core\Checkout\Payment\Cart\PaymentHandler\AbstractPaymentHandler;
use Shopware\Core\Checkout\Payment\Cart\PaymentHandler\PaymentHandlerType;
use Shopware\Core\Checkout\Payment\Cart\PaymentTransactionStruct;
use Shopware\Core\Checkout\Payment\PaymentException;
use Shopware\Core\Framework\Context;
use Shopware\Core\Framework\DataAbstractionLayer\EntityRepository;
use Shopware\Core\Framework\DataAbstractionLayer\Search\Criteria;
use Shopware\Core\Framework\Struct\Struct;
use Symfony\Component\HttpFoundation\RedirectResponse;
use Symfony\Component\HttpFoundation\Request;

class AlgovoiHostedPaymentHandler extends AbstractPaymentHandler
{
    public function __construct(
        private readonly ApiHelper $apiHelper,
        private readonly EntityRepository $orderTransactionRepository,
        private readonly EntityRepository $orderRepository,
    ) {}

    public function supports(PaymentHandlerType $type, string $paymentMethodId, Context $context): bool
    {
        return false;
    }

    public function pay(
        Request $request,
        PaymentTransactionStruct $transaction,
        Context $context,
        ?Struct $validateStruct
    ): ?RedirectResponse {
        $txId      = $transaction->getOrderTransactionId();
        $returnUrl = $transaction->getReturnUrl();

        // Load the order transaction to get amount, currency and order number
        $criteria = new Criteria([$txId]);
        $criteria->addAssociation('order');
        $criteria->addAssociation('order.currency');
        $orderTransaction = $this->orderTransactionRepository->search($criteria, $context)->first();

        if (!$orderTransaction) {
            throw PaymentException::asyncProcessInterrupted($txId, 'AlgoVoi: order transaction not found.');
        }

        $order    = $orderTransaction->getOrder();
        $amount   = $orderTransaction->getAmount()->getTotalPrice();
        $currency = $order->getCurrency()?->getIsoCode() ?? 'USD';
        $label    = 'Order #' . $order->getOrderNumber();

        $network = $request->request->get('algovoi_network', '');
        $allowed = ['algorand_mainnet', 'voi_mainnet', 'hedera_mainnet', 'stellar_mainnet', 'base_mainnet', 'solana_mainnet', 'tempo_mainnet'];
        if (!in_array($network, $allowed, true)) $network = '';

        $link = $this->apiHelper->createPaymentLink($amount, $currency, $label, $returnUrl ?? '', $network);

        if (($link['_http_code'] ?? 0) >= 400 || empty($link['checkout_url'])) {
            throw PaymentException::asyncProcessInterrupted($txId, 'AlgoVoi: could not create payment link.');
        }

        $token = '';
        if (preg_match('#/checkout/([A-Za-z0-9_-]+)$#', $link['checkout_url'], $m)) {
            $token = $m[1];
        }

        $this->orderTransactionRepository->update([[
            'id'           => $txId,
            'customFields' => ['algovoi_token' => $token, 'algovoi_label' => $label],
        ]], $context);

        return new RedirectResponse($link['checkout_url']);
    }

    public function finalize(
        Request $request,
        PaymentTransactionStruct $transaction,
        Context $context
    ): void {
        $txId = $transaction->getOrderTransactionId();

        // Load the stored token from customFields
        $criteria = new Criteria([$txId]);
        $orderTransaction = $this->orderTransactionRepository->search($criteria, $context)->first();
        $cf = $orderTransaction?->getCustomFields() ?? [];
        $token = $cf['algovoi_token'] ?? '';

        if (!$token) {
            throw PaymentException::customerCanceled($txId, 'AlgoVoi: no payment token found.');
        }

        // Check payment status via the AlgoVoi API
        $statusUrl = $this->apiHelper->getApiBase() . '/checkout/' . rawurlencode($token);
        $ch = curl_init($statusUrl);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 15,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
        ]);
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($httpCode !== 200) {
            throw PaymentException::customerCanceled($txId, 'AlgoVoi: payment was not completed.');
        }

        $data = json_decode($response, true) ?? [];
        $status = $data['status'] ?? '';

        // Only allow if the API confirms the payment is complete
        if (!in_array($status, ['paid', 'completed', 'confirmed'], true)) {
            throw PaymentException::customerCanceled($txId, 'AlgoVoi: payment status is "' . $status . '", not confirmed.');
        }
    }
}
