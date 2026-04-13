<?php
declare(strict_types=1);

namespace Algovoi\Payment\Model;

use Algovoi\Payment\Helper\ApiHelper;
use Magento\Framework\Exception\LocalizedException;
use Magento\Payment\Model\Method\AbstractMethod;
use Magento\Quote\Api\Data\CartInterface;

class AlgovoiPayment extends AbstractMethod
{
    public const CODE = 'algovoi';

    protected $_code = self::CODE;
    protected $_isOffline = false;
    protected $_canAuthorize = true;
    protected $_canCapture = false;
    protected $_canUseCheckout = true;
    protected $_canUseInternal = false;
    protected $_isInitializeNeeded = true;

    private ApiHelper $apiHelper;

    public function __construct(
        \Magento\Framework\Model\Context $context,
        \Magento\Framework\Registry $registry,
        \Magento\Framework\Api\ExtensionAttributesFactory $extensionFactory,
        \Magento\Framework\Api\AttributeValueFactory $customAttributeFactory,
        \Magento\Payment\Helper\Data $paymentData,
        \Magento\Framework\App\Config\ScopeConfigInterface $scopeConfig,
        \Magento\Payment\Model\Method\Logger $logger,
        ApiHelper $apiHelper,
        \Magento\Framework\Model\ResourceModel\AbstractResource $resource = null,
        \Magento\Framework\Data\Collection\AbstractDb $resourceCollection = null,
        array $data = []
    ) {
        parent::__construct(
            $context, $registry, $extensionFactory, $customAttributeFactory,
            $paymentData, $scopeConfig, $logger, $resource, $resourceCollection, $data
        );
        $this->apiHelper = $apiHelper;
    }

    /**
     * Initialize payment — create AlgoVoi payment link and set redirect URL.
    
 * AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 — see LICENSE for details.
 */
    public function initialize(string $paymentAction, object $stateObject): static
    {
        $payment = $this->getInfoInstance();
        $order = $payment->getOrder();

        $stateObject->setState(\Magento\Sales\Model\Order::STATE_PENDING_PAYMENT);
        $stateObject->setStatus('pending_payment');
        $stateObject->setIsNotified(false);

        $network = $payment->getAdditionalInformation('algovoi_network');
        if (!$network || !$this->apiHelper->isValidNetwork($network)) {
            $network = $this->apiHelper->getDefaultNetwork((int)$order->getStoreId());
        }

        $amount = (float)$order->getGrandTotal();
        $currency = $order->getOrderCurrencyCode();
        $label = 'Order #' . $order->getIncrementId();
        $redirectUrl = $order->getStore()->getUrl('algovoi/checkout/redirect', [
            'order_id' => $order->getEntityId(),
            '_secure'  => true,
        ]);

        $link = $this->apiHelper->createPaymentLink(
            $amount, $currency, $label, $network, $redirectUrl, (int)$order->getStoreId()
        );

        if (!$link) {
            throw new LocalizedException(__('AlgoVoi: Could not create payment link. Please try again.'));
        }

        $token = $this->apiHelper->extractToken($link['checkout_url']);

        $payment->setAdditionalInformation('algovoi_token', $token);
        $payment->setAdditionalInformation('algovoi_checkout_url', $link['checkout_url']);
        $payment->setAdditionalInformation('algovoi_network', $network);
        $payment->setAdditionalInformation('algovoi_chain', $link['chain'] ?? '');

        return $this;
    }

    /**
     * Redirect customer to AlgoVoi hosted checkout after order placement.
     */
    public function getOrderPlaceRedirectUrl(): string
    {
        $info = $this->getInfoInstance();
        if ($info) {
            $url = $info->getAdditionalInformation('algovoi_checkout_url');
            if ($url) {
                return $url;
            }
        }
        return '';
    }

    public function isAvailable(CartInterface $quote = null): bool
    {
        if (!parent::isAvailable($quote)) {
            return false;
        }

        $apiKey = $this->apiHelper->getApiKey();
        $tenantId = $this->apiHelper->getTenantId();

        return !empty($apiKey) && !empty($tenantId);
    }

    public function assignData(\Magento\Framework\DataObject $data): static
    {
        parent::assignData($data);

        $additionalData = $data->getData('additional_data') ?? $data->getData('additional_information') ?? [];
        if (is_array($additionalData) && isset($additionalData['algovoi_network'])) {
            $this->getInfoInstance()->setAdditionalInformation(
                'algovoi_network',
                $additionalData['algovoi_network']
            );
        }

        return $this;
    }
}
