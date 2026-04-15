"""
Capture real widget screenshots at each state (idle, loading, ready, done).

Drives a real browser instance against the local widget-preview server so the
GIF can composite the actual widget rather than a hand-drawn approximation.

Usage:
    python capture_widget_states.py
"""

from playwright.sync_api import sync_playwright
import os

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(OUT_DIR, exist_ok=True)

URL = "http://127.0.0.1:3334/index.html"

# Force the widget into a 2-column 2-row button layout that matches the GIF.
SETUP_JS = """
(function(){
  document.body.style.cssText = 'background:#0d1117;margin:0;padding:24px;display:flex;justify-content:center;align-items:flex-start;min-height:560px;';
  var ph = document.querySelector('.page-heading'); if (ph) ph.remove();
  var w = document.querySelector('algovoi-x402');
  w.setAttribute('amount', '0.01');
  w.style.maxWidth = '300px';
  w.style.width = '300px';
  // Force re-render so the new amount sticks
  if (typeof w._render === 'function') {
    w._amount = '0.01';
    w._render();
  }
  // Tighten inner padding for a more compact widget
  var inner = w.querySelector('.av-wrap');
  if (inner) {
    inner.style.maxWidth = '300px';
    inner.style.padding = '1.4rem 1.4rem';
  }
  return 'ok';
})()
"""

def capture_state(page, state, out_name, checkout_url=""):
    """Force the widget into a state, then screenshot just the widget element."""
    page.evaluate(f"""
        (function(){{
            var w = document.querySelector('algovoi-x402');
            w._step = '{state}';
            w._checkoutUrl = '{checkout_url}';
            w._render();
            var inner = w.querySelector('.av-wrap');
            if (inner) {{ inner.style.maxWidth = '300px'; inner.style.padding = '1.4rem 1.4rem'; }}
            return 'ok';
        }})()
    """)
    page.wait_for_timeout(150)
    el = page.query_selector("algovoi-x402")
    out = os.path.join(OUT_DIR, out_name)
    el.screenshot(path=out, omit_background=False)
    print(f"  {state:8s} -> {out}  ({os.path.getsize(out)//1024} KB)")

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 460, "height": 600},
            device_scale_factor=2,   # 2x DPR for crisp screenshots
        )
        page = context.new_page()
        page.goto(URL, wait_until="networkidle")
        page.evaluate(SETUP_JS)
        page.wait_for_timeout(300)

        capture_state(page, "idle",    "widget_idle.png")
        capture_state(page, "loading", "widget_loading.png")
        capture_state(page, "ready",   "widget_ready.png",
                      checkout_url="https://api1.ilovechicken.co.uk/checkout/abc123xyz")
        capture_state(page, "done",    "widget_done.png")

        browser.close()

if __name__ == "__main__":
    main()
