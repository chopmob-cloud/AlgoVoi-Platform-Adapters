<?php

declare(strict_types=1);

namespace Drupal\commerce_algovoi\Controller;

use Drupal\commerce_payment\Entity\PaymentGatewayInterface;
use Drupal\commerce_payment\Entity\PaymentInterface;
use Drupal\Core\Controller\ControllerBase;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * Handles inbound AlgoVoi webhooks.
 *
 * Endpoint: POST /payment/notify/algovoi/{commerce_payment_gateway}
 * Expected headers: X-AlgoVoi-Signature (base64 HMAC-SHA256 of body).
 *
 * This controller only records / completes payments — the real source of
 * truth is the GET /checkout/{token} call inside the gateway. The webhook
 * is here so order status can update out-of-band if the customer doesn't
 * come back to the return URL.
 */
class WebhookController extends ControllerBase {

  /**
   * @param \Drupal\commerce_payment\Entity\PaymentGatewayInterface $commerce_payment_gateway
   *   Loaded automatically by routing from the URL parameter.
   */
  public function handle(Request $request, PaymentGatewayInterface $commerce_payment_gateway): Response {
    /** @var \Drupal\commerce_algovoi\Plugin\Commerce\PaymentGateway\AlgoVoi $plugin */
    $plugin = $commerce_payment_gateway->getPlugin();
    // If someone points this route at a non-AlgoVoi gateway (or a later
    // refactor changes the plugin class), fail closed rather than crash.
    if (!$plugin instanceof \Drupal\commerce_algovoi\Plugin\Commerce\PaymentGateway\AlgoVoi) {
      return new JsonResponse(['error' => 'not an AlgoVoi gateway'], 400);
    }

    // Size guard BEFORE HMAC computation — matches the AI adapters' cap.
    $raw = $request->getContent();
    if ($raw === '' || strlen($raw) > 65536) {
      return new JsonResponse(['error' => 'empty or oversized body'], 400);
    }

    $signature = $request->headers->get('X-AlgoVoi-Signature', '');
    $payload   = $plugin->verifyWebhook($raw, $signature);
    if ($payload === NULL) {
      return new JsonResponse(['error' => 'invalid signature'], 401);
    }

    $order_id = $payload['order_id'] ?? $payload['reference'] ?? NULL;
    $tx_id    = $payload['tx_id'] ?? $payload['transaction_id'] ?? NULL;
    if (!$order_id || !$tx_id || strlen((string) $tx_id) > 200) {
      return new JsonResponse(['error' => 'malformed payload'], 400);
    }

    $order_storage   = $this->entityTypeManager()->getStorage('commerce_order');
    $payment_storage = $this->entityTypeManager()->getStorage('commerce_payment');

    /** @var \Drupal\commerce_order\Entity\OrderInterface|null $order */
    $order = $order_storage->load($order_id);
    if (!$order) {
      return new JsonResponse(['error' => 'order not found'], 404);
    }

    // Cross-check by verifying with the gateway — belt-and-braces so a
    // spoofed webhook (with a valid HMAC but a lie) can't mark paid.
    $token = $order->getData('commerce_algovoi_token');
    if (!$token || !$plugin->verifyCheckoutPaid($token)) {
      return new JsonResponse(['error' => 'payment not confirmed by gateway'], 402);
    }

    // Only record a new payment if we haven't already — idempotent replay.
    $existing = $payment_storage->loadByProperties([
      'order_id'        => $order->id(),
      'remote_id'       => $token,
      'state'           => 'completed',
    ]);
    if (!$existing) {
      $payment = $payment_storage->create([
        'state'           => 'completed',
        'amount'          => $order->getTotalPrice(),
        'payment_gateway' => $commerce_payment_gateway->id(),
        'order_id'        => $order->id(),
        'remote_id'       => $token,
        'remote_state'    => 'paid',
      ]);
      $payment->save();
    }

    return new JsonResponse(['ok' => TRUE, 'order_id' => $order->id()]);
  }

}
