<?php declare(strict_types=1);

namespace AlgovoiPayment\Controller;

use AlgovoiPayment\Helper\ApiHelper;
use Shopware\Core\Checkout\Order\Aggregate\OrderTransaction\OrderTransactionStateHandler;
use Shopware\Core\Framework\Context;
use Shopware\Core\Framework\DataAbstractionLayer\EntityRepository;
use Shopware\Core\Framework\DataAbstractionLayer\Search\Criteria;
use Shopware\Core\Framework\DataAbstractionLayer\Search\Filter\EqualsFilter;
use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Routing\Attribute\Route;

#[Route(defaults: ['_routeScope' => ['storefront']])]
class AlgovoiWebhookController extends AbstractController
{
    public function __construct(
        private readonly ApiHelper $apiHelper,
        private readonly EntityRepository $orderRepository,
        private readonly OrderTransactionStateHandler $transactionStateHandler,
    ) {}

    #[Route(
        path: '/algovoi/webhook',
        name: 'frontend.algovoi.webhook',
        methods: ['POST']
    )]
    public function webhook(Request $request): JsonResponse
    {
        $rawBody = $request->getContent();
        $secret  = $this->apiHelper->getWebhookSecret();

        // FIX: reject all webhook calls if secret is not configured — never skip verification
        if (!$secret) {
            return new JsonResponse(['error' => 'Webhook secret not configured on this store.'], Response::HTTP_INTERNAL_SERVER_ERROR);
        }

        $expected = base64_encode(hash_hmac('sha256', $rawBody, $secret, true));
        $received = $request->headers->get('X-AlgoVoi-Signature', '');
        if (!hash_equals($expected, $received)) {
            return new JsonResponse(['error' => 'Unauthorized'], Response::HTTP_UNAUTHORIZED);
        }

        $data  = json_decode($rawBody, true) ?? [];
        $event = $data['event'] ?? $data['type'] ?? '';
        $label = $data['label'] ?? '';

        if (!in_array($event, ['payment.confirmed', 'payment_confirmed'], true)) {
            return new JsonResponse(['status' => 'ignored']);
        }

        if (!preg_match('/Order #(\S+)/', $label, $m)) {
            return new JsonResponse(['status' => 'no_match']);
        }

        $criteria = new Criteria();
        $criteria->addFilter(new EqualsFilter('orderNumber', $m[1]));
        $criteria->addAssociation('transactions');
        $orders = $this->orderRepository->search($criteria, Context::createDefaultContext());

        if ($orders->getTotal() === 0) {
            return new JsonResponse(['status' => 'order_not_found']);
        }

        $order        = $orders->first();
        $transactions = $order->getTransactions();

        if ($transactions && $transactions->count() > 0) {
            try {
                $this->transactionStateHandler->paid(
                    $transactions->last()->getId(),
                    Context::createDefaultContext()
                );
            } catch (\Throwable) {
                // Already paid or transition blocked
            }
        }

        return new JsonResponse(['status' => 'ok']);
    }
}
