/**
 * AlgoVoi Payment Provider — Wix Velo Service Plugin (SPI)
 *
 * Integrates AlgoVoi as a custom payment method at Wix checkout.
 * Customer selects AlgoVoi → redirected to hosted checkout → pays on-chain → order marked paid.
 *
 * Supports: Algorand (USDC), VOI (aUSDC), Hedera (USDC), Stellar (USDC)
 *
 * Setup:
 *   1. Enable Velo Developer Mode on your Wix site
 *   2. Create backend/payment-provider.js (this file)
 *   3. Configure AlgoVoi credentials in Wix Secrets Manager
 *   4. The payment method appears automatically at checkout
 *
 * Wix Docs: https://dev.wix.com/docs/velo/events-service-plugins/payments/service-plugins/wix-payments/payment-provider/introduction
 *
 * Version: 1.0.0
 */

import { fetch } from 'wix-fetch';
import { getSecret } from 'wix-secrets-backend';

const ALGOVOI_API = 'https://api1.ilovechicken.co.uk';

const NETWORKS = [
  { value: 'algorand_mainnet', label: 'Algorand — USDC',  colour: '#3b82f6' },
  { value: 'voi_mainnet',      label: 'VOI — aUSDC',      colour: '#8b5cf6' },
  { value: 'hedera_mainnet',   label: 'Hedera — USDC',    colour: '#00a9a5' },
  { value: 'stellar_mainnet',  label: 'Stellar — USDC',   colour: '#7C63D0' },
];

// ── Wix Payment Provider SPI ────────────────────────────────────────────

/**
 * Called when a customer selects AlgoVoi as their payment method.
 * Returns payment provider configuration to Wix.
 */
export function paymentProvider_connectAccount(options) {
  return {
    credentials: {
      configured: true,
    },
    accountId: 'algovoi',
    accountName: 'AlgoVoi Crypto Payments',
  };
}

/**
 * Called when Wix needs to create a payment transaction.
 * Creates an AlgoVoi payment link and returns a redirect URL.
 */
export async function paymentProvider_createTransaction(options) {
  const { wixTransactionId, order, merchantCredentials } = options;

  try {
    const apiKey = await getSecret('ALGOVOI_API_KEY');
    const tenantId = await getSecret('ALGOVOI_TENANT_ID');

    if (!apiKey || !tenantId) {
      return {
        pluginTransactionId: wixTransactionId,
        reasonCode: 5005,
        errorCode: 'CONFIGURATION_ERROR',
        errorMessage: 'AlgoVoi credentials not configured. Add ALGOVOI_API_KEY and ALGOVOI_TENANT_ID to Wix Secrets Manager.',
      };
    }

    const amount = order.amount.value;
    const currency = order.amount.currency || 'USD';
    const label = `Wix Order ${wixTransactionId.substring(0, 8)}`;
    const network = 'algorand_mainnet'; // Default — customer selects on AlgoVoi checkout page

    // Return URL after payment — Wix provides this
    const returnUrl = order.returnUrls?.successUrl || '';

    const response = await fetch(`${ALGOVOI_API}/v1/payment-links`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
        'X-Tenant-Id': tenantId,
      },
      body: JSON.stringify({
        amount: parseFloat(amount),
        currency,
        label,
        preferred_network: network,
        redirect_url: returnUrl,
        expires_in_seconds: 1800,
        metadata: {
          wix_transaction_id: wixTransactionId,
        },
      }),
    });

    if (!response.ok) {
      const errText = await response.text();
      return {
        pluginTransactionId: wixTransactionId,
        reasonCode: 5005,
        errorCode: 'PROVIDER_ERROR',
        errorMessage: `AlgoVoi API error: ${response.status} — ${errText.substring(0, 200)}`,
      };
    }

    const linkData = await response.json();

    if (!linkData.checkout_url) {
      return {
        pluginTransactionId: wixTransactionId,
        reasonCode: 5005,
        errorCode: 'PROVIDER_ERROR',
        errorMessage: 'AlgoVoi did not return a checkout URL.',
      };
    }

    // Extract token for later verification
    const tokenMatch = linkData.checkout_url.match(/\/checkout\/([A-Za-z0-9_-]+)$/);
    const token = tokenMatch ? tokenMatch[1] : '';

    return {
      pluginTransactionId: token || wixTransactionId,
      redirectUrl: linkData.checkout_url,
    };
  } catch (err) {
    return {
      pluginTransactionId: wixTransactionId,
      reasonCode: 5005,
      errorCode: 'INTERNAL_ERROR',
      errorMessage: `AlgoVoi error: ${err.message}`,
    };
  }
}

/**
 * Called when a customer returns from the AlgoVoi checkout page.
 * Verifies the payment was actually completed (cancel-bypass prevention).
 */
export async function paymentProvider_submitEvent(options) {
  const { wixTransactionId, event } = options;

  if (event.transaction) {
    const token = event.transaction.pluginTransactionId || wixTransactionId;

    // CRITICAL: verify payment was completed before confirming
    const paid = await verifyPayment(token);

    if (paid) {
      return {
        wixTransactionId,
        pluginTransactionId: token,
        event: {
          transaction: {
            wixTransactionId,
            pluginTransactionId: token,
            reasonCode: 0,
          },
        },
      };
    }
  }

  // Payment not confirmed — return pending
  return {
    wixTransactionId,
    pluginTransactionId: wixTransactionId,
    event: {
      transaction: {
        wixTransactionId,
        pluginTransactionId: wixTransactionId,
        reasonCode: 5005,
        errorCode: 'PAYMENT_PENDING',
        errorMessage: 'Payment is being processed. It will be confirmed shortly via webhook.',
      },
    },
  };
}

/**
 * Called when a refund is requested.
 * AlgoVoi does not support on-chain refunds — returns error.
 */
export function paymentProvider_refundTransaction(options) {
  return {
    pluginRefundId: options.wixRefundId,
    reasonCode: 5005,
    errorCode: 'REFUND_NOT_SUPPORTED',
    errorMessage: 'On-chain refunds are not supported. Please arrange the refund directly with the customer.',
  };
}

// ── Internal Helpers ────────────────────────────────────────────────────

/**
 * Verify that a payment was actually completed on-chain.
 * Cancel-bypass prevention — don't trust the redirect alone.
 */
async function verifyPayment(token) {
  if (!token || token.length > 200) return false;

  try {
    const response = await fetch(`${ALGOVOI_API}/checkout/${encodeURIComponent(token)}`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    });

    if (response.status !== 200) return false;

    const data = await response.json();
    return ['paid', 'completed', 'confirmed'].includes(data.status);
  } catch (_) {
    return false;
  }
}
