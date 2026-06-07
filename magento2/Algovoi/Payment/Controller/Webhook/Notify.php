<?php
declare(strict_types=1);

namespace Algovoi\Payment\Controller\Webhook;

use Algovoi\Payment\Helper\ApiHelper;
use Magento\Framework\App\Action\HttpPostActionInterface;
use Magento\Framework\App\CsrfAwareActionInterface;
use Magento\Framework\App\Request\InvalidRequestException;
use Magento\Framework\App\RequestInterface;
use Magento\Framework\Controller\Result\JsonFactory;
use Magento\Sales\Api\OrderRepositoryInterface;
use Magento\Sales\Model\Order;
use Magento\Framework\Api\SearchCriteriaBuilder;

/**
 * AlgoVoi webhook receiver.
 * Verifies HMAC signature and marks orders as paid.

 * AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 — see LICENSE for details.
 */
class Notify implements HttpPostActionInterface, CsrfAwareActionInterface
{
    private RequestInterface $request;
    private JsonFactory $jsonFactory;
    private OrderRepositoryInterface $orderRepository;
    private SearchCriteriaBuilder $searchCriteriaBuilder;
    private ApiHelper $apiHelper;

    public function __construct(
        RequestInterface $request,
        JsonFactory $jsonFactory,
        OrderRepositoryInterface $orderRepository,
        SearchCriteriaBuilder $searchCriteriaBuilder,
        ApiHelper $apiHelper
    ) {
        $this->request = $request;
        $this->jsonFactory = $jsonFactory;
        $this->orderRepository = $orderRepository;
        $this->searchCriteriaBuilder = $searchCriteriaBuilder;
        $this->apiHelper = $apiHelper;
    }

    /**
     * Disable Magento CSRF validation for webhooks (we use HMAC instead).
     */
    public function createCsrfValidationException(RequestInterface $request): ?InvalidRequestException
    {
        return null;
    }

    public function validateForCsrf(RequestInterface $request): ?bool
    {
        return true;
    }

    public function execute()
    {
        $result = $this->jsonFactory->create();
        $rawBody = $this->request->getContent();
        $signature = $this->request->getHeader('X-AlgoVoi-Signature') ?: '';

        // Verify HMAC signature
        if (!$this->apiHelper->verifyWebhookSignature($rawBody, $signature)) {
            return $result->setHttpResponseCode(401)->setData(['error' => 'Unauthorized']);
        }

        $data = json_decode($rawBody, true);
        if (!$data) {
            return $result->setHttpResponseCode(400)->setData(['error' => 'Invalid JSON']);
        }

        $orderId = $data['order_id'] ?? null;
        $txId = $data['tx_id'] ?? null;

        if (!$orderId) {
            return $result->setHttpResponseCode(400)->setData(['error' => 'Missing order_id']);
        }

        // tx_id length guard
        if ($txId && strlen($txId) > 200) {
            return $result->setHttpResponseCode(400)->setData(['error' => 'Invalid tx_id']);
        }

        // Find the order by increment ID
        $searchCriteria = $this->searchCriteriaBuilder
            ->addFilter('increment_id', $orderId)
            ->create();
        $orders = $this->orderRepository->getList($searchCriteria)->getItems();
        $order = reset($orders);

        if (!$order) {
            return $result->setHttpResponseCode(404)->setData(['error' => 'Order not found']);
        }

        // Only process if order is still pending
        if ($order->getState() === Order::STATE_PENDING_PAYMENT) {
            $order->setState(Order::STATE_PROCESSING);
            $order->setStatus('processing');
            $order->addCommentToStatusHistory(
                __('AlgoVoi webhook: payment confirmed. TX: %1', $txId ?: 'n/a')
            );
            $this->orderRepository->save($order);
        }

        return $result->setData(['ok' => true]);
    }
}
