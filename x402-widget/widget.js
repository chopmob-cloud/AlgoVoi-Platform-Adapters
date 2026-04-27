/**
 * AlgoVoi x402 Payment Widget
 *
 * Embed on any page:
 *   <script type="module" src="https://widget.algovoi.co.uk/widget.js"></script>
 *   <algovoi-x402
 *     amount="29.99"
 *     currency="USD"
 *     chains="ALGO,VOI,HBAR,XLM,BASE,SOL,TEMPO"
 *     tenant-id="YOUR_TENANT_ID"
 *     api-key="algv_YOUR_API_KEY">
 *   </algovoi-x402>
 *
 * Supports all 7 AlgoVoi chains:
 *   ALGO  → USDC on Algorand
 *   VOI   → aUSDC on VOI
 *   HBAR  → USDC on Hedera
 *   XLM   → USDC on Stellar
 *   BASE  → USDC on Base (EVM)
 *   SOL   → USDC on Solana
 *   TEMPO → USDCe on Tempo
 */

const DEFAULT_API_URL = 'https://widget.algovoi.co.uk/api/x402/pay';

// Canonical chain palette — matches the AlgoVoi panel design used by all
// e-commerce adapter checkouts (WooCommerce / PrestaShop / OpenCart /
// Shopware / Magento 2 / Shopify).
const CHAIN_META = {
  ALGO:  { label: 'Algorand', ticker: 'USDC',  colour: '#3b82f6' },
  VOI:   { label: 'VOI',      ticker: 'aUSDC', colour: '#8b5cf6' },
  HBAR:  { label: 'Hedera',   ticker: 'USDC',  colour: '#10b981' },
  XLM:   { label: 'Stellar',  ticker: 'USDC',  colour: '#06b6d4' },
  BASE:  { label: 'Base',     ticker: 'USDC',  colour: '#2563eb' },
  SOL:   { label: 'Solana',   ticker: 'USDC',  colour: '#9333ea' },
  TEMPO: { label: 'Tempo',    ticker: 'USDCe', colour: '#f59e0b' },
};

class AlgoVoiX402 extends HTMLElement {
  connectedCallback() {
    this._amount   = this.getAttribute('amount')    || '0.00';
    this._currency = (this.getAttribute('currency') || 'USD').toUpperCase();
    this._chains   = (this.getAttribute('chains')   || 'ALGO').split(',').map(c => c.trim().toUpperCase());
    this._tenantId = this.getAttribute('tenant-id') || '';
    this._apiKey   = this.getAttribute('api-key')   || '';
    this._apiUrl   = this.getAttribute('api-url')   || DEFAULT_API_URL;
    this._step     = 'idle';
    this._render();

    // Single delegated click listener — works in light DOM (no Shadow DOM needed)
    this.addEventListener('click', e => {
      const btn = e.target.closest('[data-chain]');
      if (btn) this._pay(btn.dataset.chain);
    });
  }

  _render() {
    const s = this._step;
    const symbol = this._currency === 'USD' ? '$' : this._currency === 'GBP' ? '£' : this._currency === 'EUR' ? '€' : this._currency + ' ';

    this.innerHTML = `<style>
  .av-wrap *{box-sizing:border-box;margin:0;padding:0;}
  .av-wrap{
    font-family:system-ui,-apple-system,sans-serif;
    background:#1a1d2e;border:1px solid #2a2d3a;border-radius:16px;
    padding:1.75rem 2rem;max-width:420px;color:#f1f2f6;
  }
  .av-badge{
    display:inline-flex;align-items:center;gap:.4rem;
    font-size:.65rem;font-weight:700;letter-spacing:.08em;
    text-transform:uppercase;color:#6b7280;margin-bottom:1.1rem;
  }
  .av-badge-dot{
    display:inline-block;width:7px;height:7px;border-radius:50%;
    background:#3b82f6;box-shadow:0 0 6px #3b82f6;
  }
  .av-amount-card{
    background:#0f1117;border:1px solid #2a2d3a;border-radius:12px;
    padding:.9rem 1.25rem;display:flex;align-items:center;
    justify-content:space-between;margin-bottom:1.25rem;
  }
  .av-amount-label{font-size:.72rem;color:#6b7280;font-weight:600;letter-spacing:.05em;text-transform:uppercase;}
  .av-amount-value{font-size:1.9rem;font-weight:800;color:#10b981;letter-spacing:-.02em;}
  .av-amount-sub{font-size:.72rem;color:#6b7280;margin-top:.1rem;}
  .av-chains{display:flex;gap:.6rem;flex-wrap:wrap;margin-bottom:1.1rem;}
  .av-btn{
    flex:1;min-width:88px;padding:.65rem .55rem;
    background:linear-gradient(135deg,#3b82f6,#6366f1);
    color:#fff;border:none;border-radius:10px;
    font-size:.82rem;font-weight:700;cursor:pointer;
    transition:opacity .15s,transform .1s;
    display:flex;flex-direction:column;align-items:center;gap:.15rem;
  }
  .av-btn-label{font-size:.85rem;font-weight:700;line-height:1;}
  .av-btn-ticker{font-size:.65rem;font-weight:600;opacity:.85;line-height:1;letter-spacing:.02em;}
  .av-btn:hover:not(:disabled){opacity:.9;transform:translateY(-1px);}
  .av-btn:disabled{opacity:.55;cursor:not-allowed;transform:none;}
  .av-checkout-box{
    margin-top:1rem;padding:1rem 1.1rem;
    background:#0f1117;border:1px solid #2a2d3a;border-radius:10px;text-align:center;
  }
  .av-checkout-box p{font-size:.8rem;color:#9ca3af;margin-bottom:.6rem;line-height:1.5;}
  .av-checkout-link{
    display:inline-block;padding:.6rem 1.25rem;
    background:#3b82f6;color:#fff;border-radius:8px;
    font-size:.88rem;font-weight:700;text-decoration:none;transition:opacity .15s;
  }
  .av-checkout-link:hover{opacity:.85;}
  .av-done{
    margin-top:1rem;padding:1rem 1.1rem;
    background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.25);
    border-radius:10px;text-align:center;
  }
  .av-done-icon{font-size:1.5rem;margin-bottom:.35rem;}
  .av-done p{font-size:.82rem;color:#10b981;line-height:1.55;}
  .av-err{
    margin-top:.75rem;padding:.6rem .9rem;
    background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.25);
    border-radius:8px;font-size:.78rem;color:#ef4444;
  }
  .av-footer{
    margin-top:1.1rem;padding-top:.9rem;border-top:1px solid #1e2333;
    display:flex;align-items:center;justify-content:space-between;
  }
  .av-footer-left{font-size:.68rem;color:#4b5563;}
  .av-footer-right a{font-size:.68rem;color:#3b82f6;text-decoration:none;}
  .av-footer-right a:hover{text-decoration:underline;}
  .av-spinner{
    display:inline-block;width:14px;height:14px;
    border:2px solid rgba(255,255,255,.3);border-top-color:#fff;
    border-radius:50%;animation:av-spin .7s linear infinite;vertical-align:middle;margin-right:.4rem;
  }
  @keyframes av-spin{to{transform:rotate(360deg);}}
</style>
<div class="av-wrap">
  <div class="av-badge"><span class="av-badge-dot"></span>USDC &middot; Multi-chain &middot; Powered by AlgoVoi</div>

  <div class="av-amount-card">
    <div>
      <div class="av-amount-label">Amount</div>
      <div class="av-amount-value">${symbol}${this._amount}</div>
      <div class="av-amount-sub">${this._currency} &middot; stablecoin</div>
    </div>
    <div style="font-size:1.8rem;opacity:.3;">⚡</div>
  </div>

  ${s === 'idle' ? `
  <div class="av-chains">
    ${this._chains.map(c => {
      const m = CHAIN_META[c] || { label: c, ticker: '', colour: '#3b82f6' };
      return `
    <button class="av-btn" data-chain="${c}" style="background:linear-gradient(135deg,${m.colour},${m.colour}cc);">
      <span class="av-btn-label">${m.label}</span>
      ${m.ticker ? `<span class="av-btn-ticker">${m.ticker}</span>` : ''}
    </button>`;
    }).join('')}
  </div>` : ''}

  ${s === 'loading' ? `
  <button class="av-btn" disabled style="width:100%;margin-bottom:.5rem;">
    <span class="av-spinner"></span>Creating link&hellip;
  </button>` : ''}

  ${s === 'ready' ? `
  <div class="av-chains">
    ${this._chains.map(c => {
      const m = CHAIN_META[c] || { label: c, ticker: '', colour: '#3b82f6' };
      return `
    <button class="av-btn" data-chain="${c}" style="background:linear-gradient(135deg,${m.colour},${m.colour}cc);">
      <span class="av-btn-label">${m.label}</span>
      ${m.ticker ? `<span class="av-btn-ticker">${m.ticker}</span>` : ''}
    </button>`;
    }).join('')}
  </div>
  <div class="av-checkout-box">
    <p>Your secure checkout is ready.</p>
    <a class="av-checkout-link" href="${this._checkoutUrl}" target="_blank" rel="noopener">Complete Payment &rarr;</a>
  </div>` : ''}

  ${s === 'done' ? `
  <div class="av-done">
    <div class="av-done-icon">&#10003;</div>
    <p>Payment confirmed on-chain. Thank you!</p>
  </div>
  <div class="av-chains" style="margin-top:.85rem;">
    ${this._chains.map(c => {
      const m = CHAIN_META[c] || { label: c, ticker: '', colour: '#3b82f6' };
      return `
    <button class="av-btn" data-chain="${c}" style="background:linear-gradient(135deg,${m.colour},${m.colour}cc);">
      <span class="av-btn-label">${m.label}</span>
      ${m.ticker ? `<span class="av-btn-ticker">${m.ticker}</span>` : ''}
    </button>`;
    }).join('')}
  </div>` : ''}

  ${s === 'error' ? `
  <div class="av-chains">
    ${this._chains.map(c => {
      const m = CHAIN_META[c] || { label: c, ticker: '', colour: '#3b82f6' };
      return `
    <button class="av-btn" data-chain="${c}" style="background:linear-gradient(135deg,${m.colour},${m.colour}cc);">
      <span class="av-btn-label">${m.label}</span>
      ${m.ticker ? `<span class="av-btn-ticker">${m.ticker}</span>` : ''}
    </button>`;
    }).join('')}
  </div>
  <div class="av-err">${this._errMsg || 'Something went wrong. Please try again.'}</div>` : ''}

  <div class="av-footer">
    <span class="av-footer-left">Instant &middot; On-chain &middot; No chargebacks</span>
    <span class="av-footer-right"><a href="https://www.algovoi.co.uk" target="_blank" rel="noopener">AlgoVoi</a></span>
  </div>
</div>`;
  }

  async _pay(chain) {
    this._step = 'loading';
    this._render();

    try {
      const payload = { chain, amount: this._amount, currency: this._currency };
      if (this._tenantId) payload.tenantId = this._tenantId;
      if (this._apiKey)   payload.apiKey   = this._apiKey;

      const res = await fetch(this._apiUrl, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `Server error ${res.status}`);
      }

      const { checkout_url } = await res.json();
      if (!checkout_url) throw new Error('No checkout URL returned.');

      this._checkoutUrl = checkout_url;
      this._step = 'ready';
      this._render();

      const tab = window.open(checkout_url, '_blank', 'noopener');
      if (tab) {
        const poll = setInterval(() => {
          if (tab.closed) {
            clearInterval(poll);
            setTimeout(() => { this._step = 'done'; this._render(); }, 2500);
          }
        }, 1000);
      }

    } catch (err) {
      this._errMsg = err.message;
      this._step   = 'error';
      this._render();
    }
  }
}

customElements.define('algovoi-x402', AlgoVoiX402);
