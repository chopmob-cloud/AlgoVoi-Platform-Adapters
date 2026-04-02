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
use Symfony\Component\Routing\RouterInterface;

class AlgovoiWalletPaymentHandler extends AbstractPaymentHandler
{
    public function __construct(
        private readonly ApiHelper $apiHelper,
        private readonly EntityRepository $orderTransactionRepository,
        private readonly RouterInterface $router,
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

        $checkoutUrl = $link['checkout_url'];
        $chain       = $link['chain'] ?? 'algorand-mainnet';
        $amountMu    = (int)($link['amount_microunits'] ?? 0);
        $algod       = ApiHelper::getAlgodConfig($chain);

        $scraped = $this->apiHelper->scrapeCheckoutPage($checkoutUrl);
        if (empty($scraped['receiver']) || empty($scraped['memo'])) {
            throw PaymentException::asyncProcessInterrupted($txId, 'AlgoVoi: could not retrieve signing data.');
        }

        $token = '';
        if (preg_match('#/checkout/([A-Za-z0-9_-]+)$#', $checkoutUrl, $m)) {
            $token = $m[1];
        }

        $this->orderTransactionRepository->update([[
            'id'           => $txId,
            'customFields' => [
                'algovoi_token'          => $token,
                'algovoi_label'          => $label,
                'algovoi_receiver'       => $scraped['receiver'],
                'algovoi_memo'           => $scraped['memo'],
                'algovoi_amount_mu'      => $amountMu,
                'algovoi_asset_id'       => $algod['asset_id'],
                'algovoi_algod_url'      => $algod['url'],
                'algovoi_chain'          => $chain,
                'algovoi_ticker'         => $algod['ticker'],
                'algovoi_amount_display' => number_format($amountMu / (10 ** $algod['dec']), 2),
                'algovoi_return_url'     => $returnUrl,
            ],
        ]], $context);

        return new RedirectResponse(
            $this->router->generate('frontend.algovoi.wallet-pending', ['txId' => $txId])
        );
    }

    public function finalize(
        Request $request,
        PaymentTransactionStruct $transaction,
        Context $context
    ): void {
        // Verify endpoint already marked transaction paid.
    }
}
