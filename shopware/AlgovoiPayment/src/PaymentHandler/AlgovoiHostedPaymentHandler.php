<?php declare(strict_types=1);

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

        $link = $this->apiHelper->createPaymentLink($amount, $currency, $label, $returnUrl ?? '');

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
        // Webhook handles server-side confirmation. No exception = success page shown.
    }
}
