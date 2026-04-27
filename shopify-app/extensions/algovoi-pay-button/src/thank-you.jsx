import '@shopify/ui-extensions/preact';
import { render } from 'preact';

const APP_BASE = 'https://worker.algovoi.co.uk';

export default async () => {
  render(<AlgoVoiPayButton />, document.body);
};

function AlgoVoiPayButton() {
  const shopDomain = shopify.shop?.myshopifyDomain ?? '';

  let orderId = '';
  const conf = shopify.orderConfirmation?.value;
  if (conf?.order?.id) {
    orderId = String(conf.order.id).match(/\d+$/)?.[0] ?? '';
  }

  if (!shopDomain || !orderId) {
    return (
      <s-banner heading="AlgoVoi" tone="info">
        Pay with USDC / aUSDC / USDCe on Algorand, VOI, Hedera, Stellar, Base, Solana or Tempo
      </s-banner>
    );
  }

  const payUrl = `${APP_BASE}/pay?shop=${encodeURIComponent(shopDomain)}&order_id=${encodeURIComponent(orderId)}`;

  // s-button variant="primary" renders as a solid call-to-action block.
  // Shopify locks the colour to the merchant's theme primary on the
  // checkout/thank-you target — most stores end up with a blue/branded
  // button. We can't override the colour from inside the sandbox.
  return (
    <s-stack gap="base">
      <s-divider />
      <s-text appearance="subdued" size="small">
        Pay securely with USDC / aUSDC / USDCe on Algorand, VOI, Hedera, Stellar, Base, Solana or Tempo
      </s-text>
      <s-button variant="primary" href={payUrl} target="_blank">
        Pay with Crypto
      </s-button>
    </s-stack>
  );
}
