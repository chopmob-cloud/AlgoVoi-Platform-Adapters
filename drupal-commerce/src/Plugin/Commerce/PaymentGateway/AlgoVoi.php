<?php

declare(strict_types=1);

namespace Drupal\commerce_algovoi\Plugin\Commerce\PaymentGateway;

use Drupal\commerce_order\Entity\OrderInterface;
use Drupal\commerce_payment\Entity\PaymentInterface;
use Drupal\commerce_payment\Exception\PaymentGatewayException;
use Drupal\commerce_payment\PaymentMethodTypeManager;
use Drupal\commerce_payment\PaymentTypeManager;
use Drupal\commerce_payment\Plugin\Commerce\PaymentGateway\OffsitePaymentGatewayBase;
use Drupal\Component\Datetime\TimeInterface;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\Core\Form\FormStateInterface;
use Psr\Log\LoggerInterface;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Symfony\Component\HttpFoundation\Request;

/**
 * Provides the AlgoVoi off-site hosted checkout payment gateway.
 *
 * Accepts USDC on Algorand, VOI (aUSDC), Hedera, and Stellar via AlgoVoi's
 * hosted checkout page. The customer is redirected to AlgoVoi, pays with
 * their wallet of choice, and is returned to the Drupal site. Funds settle
 * directly to the merchant's wallet — this is a non-custodial gateway.
 *
 * @CommercePaymentGateway(
 *   id = "algovoi_offsite",
 *   label = "AlgoVoi (USDC on Algorand / VOI / Hedera / Stellar)",
 *   display_label = "Pay with Crypto (AlgoVoi)",
 *   forms = {
 *     "offsite-payment" = "Drupal\commerce_algovoi\PluginForm\OffsiteRedirect\PaymentOffsiteForm",
 *   },
 *   payment_method_types = {},
 *   requires_billing_information = FALSE,
 *   modes = {
 *     "test" = @Translation("Test"),
 *     "live" = @Translation("Live"),
 *   },
 * )
 */
class AlgoVoi extends OffsitePaymentGatewayBase {

  /**
   * The HTTP client — Drupal's Guzzle wrapper, injected.
   *
   * @var \GuzzleHttp\ClientInterface
   */
  protected $httpClient;

  /**
   * Channel-specific logger, injected so the class is unit-testable.
   *
   * @var \Psr\Log\LoggerInterface
   */
  protected $logger;

  /**
   * Entity type manager, injected so onReturn() can load storage services
   * without relying on the \Drupal static container.
   *
   * @var \Drupal\Core\Entity\EntityTypeManagerInterface
   */
  protected $entityTypeManager;

  /**
   * {@inheritdoc}
   */
  public static function create(ContainerInterface $container, array $configuration, $plugin_id, $plugin_definition) {
    $instance = parent::create($container, $configuration, $plugin_id, $plugin_definition);
    $instance->httpClient        = $container->get('http_client');
    $instance->logger            = $container->get('logger.factory')->get('commerce_algovoi');
    $instance->entityTypeManager = $container->get('entity_type.manager');
    return $instance;
  }

  /**
   * {@inheritdoc}
   */
  public function defaultConfiguration() {
    return [
      'api_base'         => 'https://api1.ilovechicken.co.uk',
      'api_key'          => '',
      'tenant_id'        => '',
      'webhook_secret'   => '',
      'default_network'  => 'algorand_mainnet',
    ] + parent::defaultConfiguration();
  }

  /**
   * {@inheritdoc}
   */
  public function buildConfigurationForm(array $form, FormStateInterface $form_state) {
    $form = parent::buildConfigurationForm($form, $form_state);

    $form['api_base'] = [
      '#type'          => 'textfield',
      '#title'         => $this->t('AlgoVoi API base URL'),
      '#default_value' => $this->configuration['api_base'],
      '#required'      => TRUE,
      '#description'   => $this->t('Default: https://api1.ilovechicken.co.uk'),
    ];
    $form['api_key'] = [
      '#type'          => 'textfield',
      '#title'         => $this->t('API Key'),
      '#default_value' => $this->configuration['api_key'],
      '#required'      => TRUE,
      '#description'   => $this->t('Your AlgoVoi API key (starts with algv_).'),
    ];
    $form['tenant_id'] = [
      '#type'          => 'textfield',
      '#title'         => $this->t('Tenant ID'),
      '#default_value' => $this->configuration['tenant_id'],
      '#required'      => TRUE,
    ];
    $form['webhook_secret'] = [
      '#type'          => 'textfield',
      '#title'         => $this->t('Webhook Secret'),
      '#default_value' => $this->configuration['webhook_secret'],
      '#required'      => TRUE,
      '#description'   => $this->t('Used to verify incoming webhooks. SECURITY: if this is empty, every webhook is rejected.'),
    ];
    $form['default_network'] = [
      '#type'          => 'select',
      '#title'         => $this->t('Default network'),
      '#default_value' => $this->configuration['default_network'],
      '#options'       => [
        'algorand_mainnet' => $this->t('Algorand (USDC)'),
        'voi_mainnet'      => $this->t('VOI (aUSDC)'),
        'hedera_mainnet'   => $this->t('Hedera (USDC)'),
        'stellar_mainnet'  => $this->t('Stellar (USDC)'),
      ],
    ];

    return $form;
  }

  /**
   * {@inheritdoc}
   */
  public function submitConfigurationForm(array &$form, FormStateInterface $form_state) {
    parent::submitConfigurationForm($form, $form_state);
    if (!$form_state->getErrors()) {
      $values = $form_state->getValue($form['#parents']);
      foreach (['api_base', 'api_key', 'tenant_id', 'webhook_secret', 'default_network'] as $k) {
        $this->configuration[$k] = $values[$k] ?? $this->configuration[$k];
      }
      // Trim trailing slash off api_base — simplifies URL building below.
      $this->configuration['api_base'] = rtrim($this->configuration['api_base'], '/');
    }
  }

  /**
   * Create a hosted payment link on the AlgoVoi gateway.
   *
   * Called from PaymentOffsiteForm::buildConfigurationForm() to get the
   * checkout URL to redirect the customer to.
   *
   * @return array|null
   *   ['checkout_url' => ..., 'token' => ..., 'chain' => ...]
   *   or NULL on failure.
   */
  public function createPaymentLink(OrderInterface $order, string $network, string $return_url, string $cancel_url): ?array {
    // Defence-in-depth: require https api_base.
    if (!$this->startsWithHttps($this->configuration['api_base'])) {
      $this->logger->error('Refusing to create payment link over plaintext (api_base=@u)', ['@u' => $this->configuration['api_base']]);
      return NULL;
    }

    $total    = $order->getTotalPrice();
    $amount   = (float) $total->getNumber();
    $currency = $total->getCurrencyCode();

    if (!is_finite($amount) || $amount <= 0) {
      return NULL;
    }

    $payload = [
      'amount'             => round($amount, 2),
      'currency'           => strtoupper($currency),
      'label'              => 'Drupal Order #' . $order->id(),
      'preferred_network'  => in_array($network, ['algorand_mainnet', 'voi_mainnet', 'hedera_mainnet', 'stellar_mainnet'], TRUE)
                              ? $network
                              : 'algorand_mainnet',
      'redirect_url'       => $return_url,
      'expires_in_seconds' => 3600,
    ];

    try {
      $response = $this->httpClient->post(
        $this->configuration['api_base'] . '/v1/payment-links',
        [
          'headers' => [
            'Content-Type'  => 'application/json',
            'Authorization' => 'Bearer ' . $this->configuration['api_key'],
            'X-Tenant-Id'   => $this->configuration['tenant_id'],
          ],
          'body'     => json_encode($payload),
          'timeout'  => 30,
          'verify'   => TRUE,
        ]
      );
    }
    catch (\Throwable $e) {
      $this->logger->error('createPaymentLink: @msg', ['@msg' => $e->getMessage()]);
      return NULL;
    }

    $code = $response->getStatusCode();
    $body = (string) $response->getBody();
    if ($code !== 201) {
      $this->logger->error('createPaymentLink HTTP @c: @b', ['@c' => $code, '@b' => substr($body, 0, 400)]);
      return NULL;
    }

    $data = json_decode($body, TRUE);
    if (!is_array($data) || empty($data['checkout_url'])) {
      return NULL;
    }

    $token = '';
    if (preg_match('#/checkout/([A-Za-z0-9_-]+)$#', $data['checkout_url'], $m)) {
      $token = $m[1];
    }

    // Stash token + api_base onto the order so onReturn / webhook can verify.
    $order->setData('commerce_algovoi_token', $token);
    $order->setData('commerce_algovoi_api_base', $this->configuration['api_base']);
    $order->setData('commerce_algovoi_network', $network);
    $order->save();

    return [
      'checkout_url' => $data['checkout_url'],
      'token'        => $token,
      'chain'        => $data['chain'] ?? 'algorand-mainnet',
    ];
  }

  /**
   * Called when the customer returns from AlgoVoi's hosted checkout.
   *
   * CRITICAL: always calls the gateway's GET /checkout/{token} endpoint
   * before marking the order as paid. Without this check a customer could
   * cancel payment on the hosted page and still appear to have paid
   * (cancel-bypass vulnerability, fixed during the April 2026 audit).
   *
   * {@inheritdoc}
   */
  public function onReturn(OrderInterface $order, Request $request) {
    $token = $order->getData('commerce_algovoi_token');
    if (!$token) {
      throw new PaymentGatewayException('AlgoVoi: no checkout token on order');
    }
    if (!$this->verifyCheckoutPaid($token)) {
      throw new PaymentGatewayException('AlgoVoi: payment not confirmed — order stays pending');
    }

    // Record the payment as completed.
    $payment_storage = $this->entityTypeManager->getStorage('commerce_payment');
    $payment = $payment_storage->create([
      'state'           => 'completed',
      'amount'          => $order->getTotalPrice(),
      'payment_gateway' => $this->parentEntity->id(),
      'order_id'        => $order->id(),
      'remote_id'       => $token,
      'remote_state'    => 'paid',
    ]);
    $payment->save();
  }

  /**
   * {@inheritdoc}
   */
  public function onCancel(OrderInterface $order, Request $request) {
    $this->messenger()->addMessage($this->t('Payment cancelled — your order is still open.'));
  }

  /**
   * Verify HMAC signature on a webhook body.
   *
   * @param string $raw_body
   *   Raw POST body as a string.
   * @param string $signature
   *   The X-AlgoVoi-Signature header value (base64 digest).
   *
   * @return array|null
   *   Parsed JSON payload on success, or NULL on any failure.
   */
  public function verifyWebhook(string $raw_body, string $signature): ?array {
    if (empty($this->configuration['webhook_secret'])) {
      return NULL;
    }
    if ($signature === '' || strlen($raw_body) > 65536) {
      return NULL;
    }

    $expected = base64_encode(hash_hmac('sha256', $raw_body, $this->configuration['webhook_secret'], TRUE));
    if (!hash_equals($expected, $signature)) {
      return NULL;
    }

    $data = json_decode($raw_body, TRUE);
    return is_array($data) ? $data : NULL;
  }

  /**
   * Verify checkout status via the gateway's GET /checkout/{token} endpoint.
   */
  public function verifyCheckoutPaid(string $token): bool {
    if ($token === '' || strlen($token) > 200) {
      return FALSE;
    }
    $api_base = $this->configuration['api_base'];
    if (!$this->startsWithHttps($api_base)) {
      return FALSE;
    }

    try {
      $response = $this->httpClient->get(
        $api_base . '/checkout/' . rawurlencode($token),
        ['timeout' => 15, 'verify' => TRUE]
      );
    }
    catch (\Throwable $e) {
      return FALSE;
    }
    if ($response->getStatusCode() !== 200) {
      return FALSE;
    }
    $data = json_decode((string) $response->getBody(), TRUE);
    $status = is_array($data) ? ($data['status'] ?? '') : '';
    return in_array($status, ['paid', 'completed', 'confirmed'], TRUE);
  }

  /**
   * Defence-in-depth: refuse any outbound call over plaintext HTTP.
   */
  protected function startsWithHttps(string $url): bool {
    return str_starts_with($url, 'https://');
  }

}
