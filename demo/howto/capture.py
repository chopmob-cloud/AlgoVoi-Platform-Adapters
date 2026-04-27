"""
Capture high-DPI screenshots of the canonical AlgoVoi panel for the
'how to pay with crypto' demo GIF.

Captures:
  - panel_default.png      Canonical panel, dropdown closed, Algorand selected
  - panel_voi.png          Same panel with VOI selected (purple dot)
  - panel_hedera.png       Hedera selected (green dot)
  - panel_solana.png       Solana selected (violet dot)
  - panel_dropdown.png     Panel with dropdown open showing all 7 chains
  - widget_default.png     x402 embeddable widget (widget.algovoi.co.uk)

All shots are 2x DPR for crisp output. Source URLs are the live deployed
endpoints — no mock data.
"""
from __future__ import annotations

import os
import sys
from playwright.sync_api import sync_playwright

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")
os.makedirs(OUT_DIR, exist_ok=True)

PAY_URL    = "https://worker.algovoi.co.uk/pay/?shop=demo.myshopify.com&order_id=12345"
WIDGET_URL = "https://widget.algovoi.co.uk/"


def setup_pay_page(page):
    """Make the /pay page panel-only — strip body padding, isolate the panel."""
    page.evaluate("""
      (function() {
        document.body.style.cssText = 'background:#0d1117;margin:0;padding:32px;display:flex;justify-content:center;align-items:flex-start;min-height:600px;';
        var panel = document.querySelector('.panel');
        if (panel) panel.style.maxWidth = '440px';
      })();
    """)
    page.wait_for_timeout(150)


def select_chain(page, chain_value: str):
    """Programmatically pick a chain on the /pay page so we can capture each colour."""
    page.evaluate(f"""
      (function() {{
        var sel = document.getElementById('net-sel');
        if (!sel) return;
        sel.value = '{chain_value}';
        sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
      }})();
    """)
    page.wait_for_timeout(150)


def capture_pay_panel(page, out_name: str, *, dropdown_open: bool = False):
    panel = page.query_selector(".panel")
    if not panel:
        print(f"  ! no .panel found, skipping {out_name}")
        return
    if dropdown_open:
        # Force the <select> visually open by adding focus and a screenshot-only style
        page.evaluate("""
          (function() {
            var sel = document.getElementById('net-sel');
            if (!sel) return;
            sel.size = 7;
            sel.style.position = 'absolute';
            sel.style.zIndex = '99';
            sel.style.background = '#0d0e1a';
            sel.style.color = '#f1f2f6';
            sel.style.border = '1px solid #6366f1';
            sel.style.borderRadius = '7px';
            sel.style.padding = '4px';
            sel.style.minWidth = '220px';
            sel.style.font = '14px -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif';
          })();
        """)
        page.wait_for_timeout(200)
    out = os.path.join(OUT_DIR, out_name)
    panel.screenshot(path=out, omit_background=False)
    print(f"  panel  -> {out_name}  ({os.path.getsize(out) // 1024} KB)")


def capture_widget(page, out_name: str):
    el = page.query_selector("algovoi-x402")
    if not el:
        # Widget might still be initialising
        page.wait_for_timeout(800)
        el = page.query_selector("algovoi-x402")
    if not el:
        print(f"  ! no algovoi-x402 found, skipping {out_name}")
        return
    out = os.path.join(OUT_DIR, out_name)
    el.screenshot(path=out, omit_background=False)
    print(f"  widget -> {out_name}  ({os.path.getsize(out) // 1024} KB)")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 720, "height": 900},
            device_scale_factor=3,   # 3x DPR for crisp HQ output
        )
        page = context.new_page()

        # ── Pay page: capture per-chain variants ─────────────────────────────
        print(f"-> {PAY_URL}")
        page.goto(PAY_URL, wait_until="networkidle", timeout=15000)
        setup_pay_page(page)

        select_chain(page, "ALGO")
        capture_pay_panel(page, "panel_default.png")

        select_chain(page, "VOI")
        capture_pay_panel(page, "panel_voi.png")

        select_chain(page, "HBAR")
        capture_pay_panel(page, "panel_hedera.png")

        select_chain(page, "SOL")
        capture_pay_panel(page, "panel_solana.png")

        # Reset to ALGO before opening dropdown so the highlighted option is canonical
        select_chain(page, "ALGO")
        capture_pay_panel(page, "panel_dropdown.png", dropdown_open=True)

        # ── Widget capture ───────────────────────────────────────────────────
        print(f"-> {WIDGET_URL}")
        widget_page = context.new_page()
        widget_page.goto(WIDGET_URL, wait_until="networkidle", timeout=15000)
        widget_page.wait_for_timeout(400)
        capture_widget(widget_page, "widget_default.png")

        browser.close()
        print("\nAll captures written to:", OUT_DIR)


if __name__ == "__main__":
    main()
