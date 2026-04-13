<?php
/**
 * AlgoVoi: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 - see LICENSE for details.
 */
 declare(strict_types=1);

namespace AlgovoiPayment\Controller;

use AlgovoiPayment\Helper\ApiHelper;
use Shopware\Core\Checkout\Order\Aggregate\OrderTransaction\OrderTransactionStateHandler;
use Shopware\Core\Framework\DataAbstractionLayer\EntityRepository;
use Shopware\Core\Framework\DataAbstractionLayer\Search\Criteria;
use Shopware\Core\System\SalesChannel\SalesChannelContext;
use Shopware\Storefront\Controller\StorefrontController;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Routing\Attribute\Route;

#[Route(defaults: ['_routeScope' => ['storefront']])]
class AlgovoiWalletController extends StorefrontController
{
    public function __construct(
        private readonly ApiHelper $apiHelper,
        private readonly EntityRepository $orderTransactionRepository,
        private readonly OrderTransactionStateHandler $transactionStateHandler,
    ) {}

    #[Route(
        path: '/algovoi/wallet-pending/{txId}',
        name: 'frontend.algovoi.wallet-pending',
        methods: ['GET']
    )]
    public function walletPending(string $txId, SalesChannelContext $context): Response
    {
        $criteria = new Criteria([$txId]);
        $transaction = $this->orderTransactionRepository->search($criteria, $context->getContext())->first();

        if (!$transaction) {
            return $this->redirectToRoute('frontend.home.page');
        }

        $cf = $transaction->getCustomFields() ?? [];

        return $this->renderStorefront('@AlgovoiPayment/storefront/algovoi/wallet-pending.html.twig', [
            'txId'          => $txId,
            'receiver'      => $cf['algovoi_receiver'] ?? '',
            'memo'          => $cf['algovoi_memo'] ?? '',
            'amountMu'      => $cf['algovoi_amount_mu'] ?? 0,
            'assetId'       => $cf['algovoi_asset_id'] ?? 31566704,
            'algodUrl'      => $cf['algovoi_algod_url'] ?? 'https://mainnet-api.algonode.cloud',
            'chain'         => $cf['algovoi_chain'] ?? 'algorand-mainnet',
            'ticker'        => $cf['algovoi_ticker'] ?? 'USDC',
            'amountDisplay' => $cf['algovoi_amount_display'] ?? '0.00',
            'returnUrl'     => $cf['algovoi_return_url'] ?? '/',
        ]);
    }

    #[Route(
        path: '/algovoi/verify',
        name: 'frontend.algovoi.verify',
        methods: ['POST'],
        defaults: ['XmlHttpRequest' => true]
    )]
    public function verify(Request $request, SalesChannelContext $context): JsonResponse
    {
        $body   = json_decode($request->getContent(), true) ?? [];
        $txId   = (string)($body['txId'] ?? '');
        $txHash = (string)($body['tx_id'] ?? '');

        if (!$txId || !$txHash) {
            return new JsonResponse(['error' => 'Missing parameters.'], 400);
        }

        $criteria    = new Criteria([$txId]);
        $transaction = $this->orderTransactionRepository->search($criteria, $context->getContext())->first();

        if (!$transaction) {
            return new JsonResponse(['error' => 'Transaction not found.'], 404);
        }

        $cf    = $transaction->getCustomFields() ?? [];
        $token = (string)($cf['algovoi_token'] ?? '');

        if (!$token) {
            return new JsonResponse(['error' => 'No payment token on record.'], 400);
        }

        $result = $this->apiHelper->verifyPayment($token, $txHash);

        if (($result['_http_code'] ?? 0) === 200) {
            try {
                $this->transactionStateHandler->paid($txId, $context->getContext());
            } catch (\Throwable) {
                // Already transitioned — fine
            }
            return new JsonResponse(['success' => true, 'returnUrl' => $cf['algovoi_return_url'] ?? '/']);
        }

        return new JsonResponse(
            ['error' => $result['detail'] ?? $result['message'] ?? 'Verification failed.'],
            400
        );
    }
}
