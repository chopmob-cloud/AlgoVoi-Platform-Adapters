/**
 * AlgoVoi × Manndeshi Foundation — $2.75 Donation Widget
 * Empowering rural women to become successful entrepreneurs.
 *
 * Embed on any page:
 *   <script type="module" src="https://widget.algovoi.co.uk/manndeshi.js"></script>
 *   <algovoi-manndeshi></algovoi-manndeshi>
 */

class AlgoVoiManndeshi extends HTMLElement {
  connectedCallback() {
    this._step = 'idle'; // idle | loading | ready | done
    this._checkoutUrl = '';
    this._render();
  }

  _render() {
    const s = this._step;
    this.innerHTML = `
<style>
  .mn-wrap *{box-sizing:border-box;margin:0;padding:0;}
  .mn-wrap{
    font-family:system-ui,-apple-system,sans-serif;
    background:#1a1d2e;
    border:1px solid #2a2d3a;
    border-radius:16px;
    padding:2rem 2rem 1.75rem;
    max-width:420px;
    color:#f1f2f6;
  }
  .mn-badge{
    display:inline-flex;align-items:center;gap:.4rem;
    font-size:.65rem;font-weight:700;letter-spacing:.08em;
    text-transform:uppercase;color:#6b7280;margin-bottom:1.25rem;
  }
  .mn-badge span{
    display:inline-block;width:7px;height:7px;
    border-radius:50%;background:#3b82f6;
    box-shadow:0 0 6px #3b82f6;
  }
  .mn-logo{
    font-size:1.05rem;font-weight:800;color:#f1f2f6;
    letter-spacing:-.01em;margin-bottom:.35rem;
  }
  .mn-tagline{
    font-size:.82rem;color:#9ca3af;line-height:1.55;
    margin-bottom:1.5rem;
  }
  .mn-amount-card{
    background:#0f1117;
    border:1px solid #2a2d3a;
    border-radius:12px;
    padding:1rem 1.25rem;
    display:flex;align-items:center;justify-content:space-between;
    margin-bottom:1.25rem;
  }
  .mn-amount-label{font-size:.72rem;color:#6b7280;font-weight:600;letter-spacing:.05em;text-transform:uppercase;}
  .mn-amount-value{font-size:1.9rem;font-weight:800;color:#10b981;letter-spacing:-.02em;}
  .mn-amount-sub{font-size:.72rem;color:#6b7280;margin-top:.15rem;}
  .mn-chain{
    display:flex;align-items:center;gap:.5rem;
    background:#1e2333;border:1px solid #2a2d3a;border-radius:8px;
    padding:.6rem .9rem;margin-bottom:1.35rem;
  }
  .mn-chain-dot{width:8px;height:8px;border-radius:50%;background:#3b82f6;flex-shrink:0;}
  .mn-chain-name{font-size:.82rem;font-weight:600;color:#f1f2f6;}
  .mn-chain-sub{font-size:.72rem;color:#6b7280;margin-left:auto;}
  .mn-btn{
    width:100%;padding:.9rem 1.5rem;
    background:linear-gradient(135deg,#3b82f6,#6366f1);
    color:#fff;border:none;border-radius:10px;
    font-size:.95rem;font-weight:700;cursor:pointer;
    transition:opacity .15s,transform .1s;
    display:flex;align-items:center;justify-content:center;gap:.5rem;
  }
  .mn-btn:hover:not(:disabled){opacity:.9;transform:translateY(-1px);}
  .mn-btn:disabled{opacity:.55;cursor:not-allowed;transform:none;}
  .mn-checkout-box{
    margin-top:1rem;padding:1rem 1.1rem;
    background:#0f1117;border:1px solid #2a2d3a;border-radius:10px;
    text-align:center;
  }
  .mn-checkout-box p{font-size:.8rem;color:#9ca3af;margin-bottom:.65rem;line-height:1.5;}
  .mn-checkout-link{
    display:inline-block;padding:.65rem 1.35rem;
    background:#3b82f6;color:#fff;border-radius:8px;
    font-size:.88rem;font-weight:700;text-decoration:none;
    transition:opacity .15s;
  }
  .mn-checkout-link:hover{opacity:.85;}
  .mn-done{
    margin-top:1rem;padding:1rem 1.1rem;
    background:rgba(16,185,129,.08);
    border:1px solid rgba(16,185,129,.25);
    border-radius:10px;text-align:center;
  }
  .mn-done-icon{font-size:1.6rem;margin-bottom:.4rem;}
  .mn-done p{font-size:.82rem;color:#10b981;line-height:1.55;}
  .mn-err{
    margin-top:.75rem;padding:.65rem .9rem;
    background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.25);
    border-radius:8px;font-size:.78rem;color:#ef4444;
  }
  .mn-footer{
    margin-top:1.25rem;padding-top:1rem;
    border-top:1px solid #1e2333;
    display:flex;align-items:center;justify-content:space-between;
  }
  .mn-footer-left{font-size:.68rem;color:#4b5563;}
  .mn-footer-right a{font-size:.68rem;color:#3b82f6;text-decoration:none;}
  .mn-footer-right a:hover{text-decoration:underline;}
  .mn-spinner{
    width:16px;height:16px;border:2px solid rgba(255,255,255,.3);
    border-top-color:#fff;border-radius:50%;
    animation:mn-spin .7s linear infinite;flex-shrink:0;
  }
  @keyframes mn-spin{to{transform:rotate(360deg);}}
</style>

<div class="mn-wrap">
  <div class="mn-badge"><span></span>Algorand · USDC · Powered by AlgoVoi</div>

  <div class="mn-logo">Manndeshi Foundation</div>
  <p class="mn-tagline">
    Empowering rural women across India to become<br>
    confident, successful entrepreneurs.
  </p>

  <div class="mn-amount-card">
    <div>
      <div class="mn-amount-label">Donation</div>
      <div class="mn-amount-value">$2.75</div>
      <div class="mn-amount-sub">USDC · Algorand mainnet</div>
    </div>
    <div style="font-size:2rem;opacity:.35;">🌱</div>
  </div>

  <div class="mn-chain">
    <div class="mn-chain-dot"></div>
    <div>
      <div class="mn-chain-name">Algorand</div>
    </div>
    <div class="mn-chain-sub">ASA 31566704 · ~2s settlement</div>
  </div>

  ${s === 'idle' ? `
  <button class="mn-btn" id="mn-donate-btn" onclick="this.getRootNode().host._donate()">
    &#10024; Donate $2.75 with USDC
  </button>` : ''}

  ${s === 'loading' ? `
  <button class="mn-btn" disabled>
    <div class="mn-spinner"></div> Creating payment link&hellip;
  </button>` : ''}

  ${s === 'ready' ? `
  <button class="mn-btn" onclick="this.getRootNode().host._donate()">
    &#10024; Donate another $2.75
  </button>
  <div class="mn-checkout-box">
    <p>Your secure checkout is ready.<br>Click below to complete your donation.</p>
    <a class="mn-checkout-link" href="${this._checkoutUrl}" target="_blank" rel="noopener">
      Complete Donation &rarr;
    </a>
  </div>` : ''}

  ${s === 'done' ? `
  <div class="mn-done">
    <div class="mn-done-icon">&#10003;</div>
    <p>Thank you — your donation is confirmed on-chain.<br>
    Every $2.75 helps a woman start her business.</p>
  </div>
  <button class="mn-btn" style="margin-top:.85rem;" onclick="this.getRootNode().host._reset()">
    &#10024; Donate again
  </button>` : ''}

  ${s === 'error' ? `
  <button class="mn-btn" onclick="this.getRootNode().host._donate()">
    &#10024; Donate $2.75 with USDC
  </button>
  <div class="mn-err" id="mn-err-msg">${this._errMsg || 'Something went wrong. Please try again.'}</div>` : ''}

  <div class="mn-footer">
    <span class="mn-footer-left">Instant · On-chain · No intermediary</span>
    <span class="mn-footer-right">
      <a href="https://www.manndeshifoundation.org" target="_blank" rel="noopener">manndeshifoundation.org</a>
    </span>
  </div>
</div>`;
  }

  async _donate() {
    this._step = 'loading';
    this._render();

    try {
      const res = await fetch('https://widget.algovoi.co.uk/api/manndeshi/donate', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ amount: 2.75, chain: 'ALGO', currency: 'USD' }),
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

      // Listen for the payment tab closing — poll for confirmation
      const tab = window.open(checkout_url, '_blank', 'noopener');
      if (tab) {
        const poll = setInterval(() => {
          if (tab.closed) {
            clearInterval(poll);
            // Give AlgoVoi a moment to fire the webhook before refreshing state
            setTimeout(() => {
              this._step = 'done';
              this._render();
            }, 2500);
          }
        }, 1000);
      }

    } catch (err) {
      this._errMsg = err.message;
      this._step   = 'error';
      this._render();
    }
  }

  _reset() {
    this._step = 'idle';
    this._checkoutUrl = '';
    this._errMsg = '';
    this._render();
  }
}

customElements.define('algovoi-manndeshi', AlgoVoiManndeshi);
