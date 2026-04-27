import '@shopify/ui-extensions/preact';
import { render } from 'preact';

const APP_BASE = 'https://worker.algovoi.co.uk';

export default async () => {
  render(<AlgoVoiOrderStatus />, document.body);
};

function AlgoVoiOrderStatus() {
  const shopDomain = shopify.shop?.myshopifyDomain ?? '';
  const orderId = (shopify.order?.id ?? '').toString().match(/\d+$/)?.[0] ?? '';

  if (!shopDomain || !orderId) return null;

  const payUrl = `${APP_BASE}/pay?shop=${encodeURIComponent(shopDomain)}&order_id=${encodeURIComponent(orderId)}`;

  // s-button variant="primary" → solid call-to-action block in the
  // merchant's theme colour. The Shopify checkout/customer-account
  // sandbox does not allow overriding colours from inside the extension
  // (raw <a> with inline styles gets stripped). The brand-coloured
  // /pay page that the button links to has full AlgoVoi styling.
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
