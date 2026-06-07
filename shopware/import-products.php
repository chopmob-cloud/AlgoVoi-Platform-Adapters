<?php
// AlgoVoi product import — run as: php import-products.php

$_SERVER['PROJECT_ROOT'] = __DIR__;

$classLoader = require __DIR__ . '/vendor/autoload.php';

use Shopware\Core\Framework\Adapter\Kernel\KernelFactory;
use Shopware\Core\Framework\Context;
use Shopware\Core\Framework\Plugin\KernelPluginLoader\DbalKernelPluginLoader;
use Shopware\Core\Framework\Uuid\Uuid;
use Shopware\Core\Kernel;

$pluginLoader = new DbalKernelPluginLoader($classLoader, null, Kernel::getConnection());

$kernel = KernelFactory::create(
    environment: 'prod',
    debug: false,
    classLoader: $classLoader,
    pluginLoader: $pluginLoader,
);
$kernel->boot();

$container = $kernel->getContainer();
$context   = Context::createDefaultContext();

/** @var \Shopware\Core\Framework\DataAbstractionLayer\EntityRepository $productRepo
 * AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 — see LICENSE for details.
 */
$productRepo    = $container->get('product.repository');
$currencyId     = 'b7d2554b0ce847cd82f3ac9bd1c0dfca';
$salesChannelId = '019d4d94229771eaaa5f24b09ee811b6';
$taxId          = '019d4d925ebd729e8ebb0a9cf45bf110';
$languageId     = '2fbb5fe2e29a4d70aa5854ce7ce3e20b';

$products = [
    [
        'name'          => 'Digital Download A',
        'number'        => 'ALGOVOI-DL-A',
        'price'         => 0.05,
        'description'   => 'Instant digital download. Delivered after payment confirmation.',
    ],
    [
        'name'          => 'Digital Download B',
        'number'        => 'ALGOVOI-DL-B',
        'price'         => 0.10,
        'description'   => 'Instant digital download. Delivered after payment confirmation.',
    ],
    [
        'name'          => 'Premium Access',
        'number'        => 'ALGOVOI-PREM',
        'price'         => 0.25,
        'description'   => 'Premium access pass. Activated after payment confirmation.',
    ],
];

$toCreate = [];
foreach ($products as $p) {
    $toCreate[] = [
        'id'            => Uuid::randomHex(),
        'productNumber' => $p['number'],
        'stock'         => 9999,
        'price'         => [[
            'currencyId' => $currencyId,
            'gross'      => $p['price'],
            'net'        => $p['price'],
            'linked'     => true,
        ]],
        'taxId'         => $taxId,
        'active'        => true,
        'visibilities'  => [[
            'id'             => Uuid::randomHex(),
            'salesChannelId' => $salesChannelId,
            'visibility'     => 30,
        ]],
        'translations' => [
            $languageId => [
                'name'        => $p['name'],
                'description' => $p['description'],
            ],
        ],
    ];
}

$productRepo->create($toCreate, $context);

echo "Done. Imported " . count($toCreate) . " products:\n";
foreach ($toCreate as $idx => $p) {
    echo "  [{$p['productNumber']}] {$products[$idx]['name']} — \${$products[$idx]['price']}\n";
}
