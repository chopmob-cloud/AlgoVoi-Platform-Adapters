<?php declare(strict_types=1);

namespace AlgovoiPayment;

use AlgovoiPayment\PaymentHandler\AlgovoiHostedPaymentHandler;
use AlgovoiPayment\PaymentHandler\AlgovoiWalletPaymentHandler;
use Shopware\Core\Framework\Context;
use Shopware\Core\Framework\DataAbstractionLayer\Search\Criteria;
use Shopware\Core\Framework\DataAbstractionLayer\Search\Filter\EqualsFilter;
use Shopware\Core\Framework\Plugin;
use Shopware\Core\Framework\Plugin\Context\ActivateContext;
use Shopware\Core\Framework\Plugin\Context\DeactivateContext;
use Shopware\Core\Framework\Plugin\Context\InstallContext;
use Shopware\Core\Framework\Plugin\Context\UninstallContext;

class AlgovoiPayment extends Plugin
{
    public function install(InstallContext $installContext): void
    {
        parent::install($installContext);
        $this->addPaymentMethods($installContext->getContext());
    }

    public function uninstall(UninstallContext $uninstallContext): void
    {
        parent::uninstall($uninstallContext);
        $this->setPaymentMethodsActive(false, $uninstallContext->getContext());
    }

    public function activate(ActivateContext $activateContext): void
    {
        parent::activate($activateContext);
        $this->setPaymentMethodsActive(true, $activateContext->getContext());
    }

    public function deactivate(DeactivateContext $deactivateContext): void
    {
        parent::deactivate($deactivateContext);
        $this->setPaymentMethodsActive(false, $deactivateContext->getContext());
    }

    private function addPaymentMethods(Context $context): void
    {
        /** @var \Shopware\Core\Framework\DataAbstractionLayer\EntityRepository $repo
 * AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Copyright (c) 2026 Christopher Hopley (ilovechicken.co.uk). BSL 1.1.
 */
        $repo = $this->container->get('payment_method.repository');

        $methods = [
            [
                'handlerIdentifier' => AlgovoiHostedPaymentHandler::class,
                'technicalName'     => 'algovoi_hosted',
                'name'              => 'AlgoVoi Checkout (USDC / aUSDC)',
                'description'       => 'Pay with stablecoins via AlgoVoi hosted checkout. Supports USDC on Algorand and aUSDC on VOI.',
                'active'            => true,
            ],
            [
                'handlerIdentifier' => AlgovoiWalletPaymentHandler::class,
                'technicalName'     => 'algovoi_wallet',
                'name'              => 'AlgoVoi Wallet (USDC / aUSDC)',
                'description'       => 'Pay with your Pera, Defly, or Lute wallet. Requires the wallet browser extension.',
                'active'            => true,
            ],
        ];

        foreach ($methods as $method) {
            $criteria = new Criteria();
            $criteria->addFilter(new EqualsFilter('handlerIdentifier', $method['handlerIdentifier']));
            if ($repo->search($criteria, $context)->getTotal() === 0) {
                $repo->create([$method], $context);
            }
        }
    }

    private function setPaymentMethodsActive(bool $active, Context $context): void
    {
        /** @var \Shopware\Core\Framework\DataAbstractionLayer\EntityRepository $repo */
        $repo = $this->container->get('payment_method.repository');

        foreach ([AlgovoiHostedPaymentHandler::class, AlgovoiWalletPaymentHandler::class] as $handler) {
            $criteria = new Criteria();
            $criteria->addFilter(new EqualsFilter('handlerIdentifier', $handler));
            $result = $repo->search($criteria, $context);
            if ($result->getTotal() > 0) {
                $repo->update([['id' => $result->first()->getId(), 'active' => $active]], $context);
            }
        }
    }
}
