<?php

declare(strict_types=1);

namespace Drupal\commerce_algovoi\PluginForm\OffsiteRedirect;

use Drupal\commerce_payment\PluginForm\PaymentOffsiteForm as BasePaymentOffsiteForm;
use Drupal\Core\Form\FormStateInterface;

/**
 * Off-site payment redirect form.
 *
 * Creates a hosted payment link on the AlgoVoi gateway, then redirects the
 * customer to the returned checkout URL. The gateway return handler
 * (AlgoVoi::onReturn()) verifies the payment on the customer's return.
 */
class PaymentOffsiteForm extends BasePaymentOffsiteForm {

  /**
   * {@inheritdoc}
   */
  public function buildConfigurationForm(array $form, FormStateInterface $form_state) {
    $form = parent::buildConfigurationForm($form, $form_state);

    /** @var \Drupal\commerce_payment\Entity\PaymentInterface $payment */
    $payment = $this->entity;
    $order   = $payment->getOrder();

    /** @var \Drupal\commerce_algovoi\Plugin\Commerce\PaymentGateway\AlgoVoi $gateway */
    $gateway = $payment->getPaymentGateway()->getPlugin();

    $network = $order->getData('commerce_algovoi_network')
      ?? $gateway->getConfiguration()['default_network']
      ?? 'algorand_mainnet';

    $link = $gateway->createPaymentLink(
      $order,
      $network,
      $form['#return_url'],
      $form['#cancel_url']
    );

    if (!$link) {
      throw new \Exception('Could not create AlgoVoi payment link. Check logs for details.');
    }

    // No extra POST data needed — the AlgoVoi checkout page handles the
    // redirect back via the `redirect_url` we passed when creating the
    // link. We use GET because the URL already contains the signed token.
    return $this->buildRedirectForm(
      $form,
      $form_state,
      $link['checkout_url'],
      [],
      self::REDIRECT_GET
    );
  }

}
