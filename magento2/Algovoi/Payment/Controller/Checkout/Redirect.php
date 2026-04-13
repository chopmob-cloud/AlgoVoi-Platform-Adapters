<?php
declare(strict_types=1);

namespace Algovoi\Payment\Controller\Checkout;

use Algovoi\Payment\Helper\ApiHelper;
use Magento\Customer\Model\Session as CustomerSession;
use Magento\Framework\App\Action\HttpGetActionInterface;
use Magento\Framework\App\RequestInterface;
use Magento\Framework\Controller\Result\RedirectFactory;
use Magento\Framework\Message\ManagerInterface;
use Magento\Sales\Api\OrderRepositoryInterface;

/**
 * Customer return from AlgoVoi hosted checkout.
 * Verifies payment status AND order ownership before marking paid.

 * AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Copyright (c) 2026 Christopher Hopley (ilovechicken.co.uk). BSL 1.1.
 */
class Redirect implements HttpGetActionInterface
{
    private RequestInterface $request;
    private RedirectFactory $redirectFactory;
    private ManagerInterface $messageManager;
    private OrderRepositoryInterface $orderRepository;
    private CustomerSession $customerSession;
    private ApiHelper $apiHelper;

    public function __construct(
        RequestInterface $request,
        RedirectFactory $redirectFactory,
        ManagerInterface $messageManager,
        OrderRepositoryInterface $orderRepository,
        CustomerSession $customerSession,
        ApiHelper $apiHelper
    ) {
        $this->request = $request;
        $this->redirectFactory = $redirectFactory;
        $this->messageManager = $messageManager;
        $this->orderRepository = $orderRepository;
        $this->customerSession = $customerSession;
        $this->apiHelper = $apiHelper;
    }

    public function execute()
    {
        $orderId = (int)$this->request->getParam('order_id');
        $redirect = $this->redirectFactory->create();

        if (!$orderId) {
            $this->messageManager->addErrorMessage(__('Invalid order.'));
            return $redirect->setPath('checkout/cart');
        }

        try {
            $order = $this->orderRepository->get($orderId);
        } catch (\Exception $e) {
            $this->messageManager->addErrorMessage(__('Order not found.'));
            return $redirect->setPath('checkout/cart');
        }

        // Order ownership check — prevent accessing other customers' orders
        $customerId = $this->customerSession->getCustomerId();
        if ($customerId && (int)$order->getCustomerId() !== (int)$customerId) {
            $this->messageManager->addErrorMessage(__('Unauthorized.'));
            return $redirect->setPath('checkout/cart');
        }

        // Guest orders: verify by checking the last order in session
        if (!$customerId) {
            $lastOrderId = $this->customerSession->getData('last_order_id');
            if ((int)$lastOrderId !== $orderId) {
                $this->messageManager->addErrorMessage(__('Unauthorized.'));
                return $redirect->setPath('checkout/cart');
            }
        }

        $payment = $order->getPayment();
        $token = $payment->getAdditionalInformation('algovoi_token');

        if (!$token) {
            $this->messageManager->addErrorMessage(__('Payment token not found.'));
            return $redirect->setPath('checkout/cart');
        }

        // CRITICAL: verify payment was actually completed (cancel-bypass prevention)
        $paid = $this->apiHelper->verifyHostedReturn($token, (int)$order->getStoreId());

        if ($paid) {
            $order->setState(\Magento\Sales\Model\Order::STATE_PROCESSING);
            $order->setStatus('processing');
            $order->addCommentToStatusHistory(
                __('AlgoVoi payment confirmed. Token: %1', $token)
            );
            $this->orderRepository->save($order);
            $this->messageManager->addSuccessMessage(__('Payment received. Thank you!'));
        } else {
            $this->messageManager->addNoticeMessage(
                __('Payment is being processed. You will receive a confirmation email shortly.')
            );
        }

        return $redirect->setPath('checkout/onepage/success');
    }
}
