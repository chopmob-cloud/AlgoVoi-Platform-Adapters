"""
AlgoVoi x402 Widget — Embed Demo GIF
Shows: code snippet → widget idle → loading → ready → checkout link
"""

import os, sys, textwrap
from PIL import Image, ImageDraw, ImageFont

# ── Canvas ─────────────────────────────────────────────────────────────────
W, H   = 720, 480
FPS    = 18          # frames per second
DELAY  = round(1000 / FPS)   # ms per frame (Pillow GIF duration is in ms)

# ── Colours ────────────────────────────────────────────────────────────────
BG          = (15,  17,  23)   # #0f1117
CARD_BG     = (26,  29,  46)   # #1a1d2e
CARD_BORDER = (42,  45,  58)   # #2a2d3a
EDITOR_BG   = (18,  20,  30)
EDITOR_LINE = (30,  33,  48)
GUTTER_BG   = (22,  24,  36)

GREEN   = (16,  185, 129)
BLUE    = (59,  130, 246)
INDIGO  = (99,  102, 241)
RED     = (239,  68,  68)
GRAY1   = (107, 114, 128)
GRAY2   = (75,   85,  99)
WHITE   = (241, 242, 246)
DIM     = (156, 163, 175)

# Syntax colours
SYN_TAG    = (129, 182, 255)   # HTML tags   – light blue
SYN_ATTR   = (255, 198, 109)   # attributes  – amber
SYN_VAL    = (152, 195, 121)   # values      – green
SYN_PLAIN  = (220, 223, 228)   # plain text  – near-white
SYN_PUNCT  = (171, 178, 191)   # punctuation – grey

# ── Font loader ────────────────────────────────────────────────────────────
def _font(size, bold=False):
    candidates = [
        r"C:\Windows\Fonts\consola.ttf",
        r"C:\Windows\Fonts\cour.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]
    if bold:
        candidates = [r"C:\Windows\Fonts\consolab.ttf",
                      r"C:\Windows\Fonts\courbd.ttf"] + candidates
    for p in candidates:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except Exception: pass
    return ImageFont.load_default()

MONO_SM  = _font(13)
MONO_MD  = _font(15)
MONO_LG  = _font(17, bold=True)
SANS_SM  = _font(12)
SANS_MD  = _font(14)
SANS_LG  = _font(16, bold=True)
SANS_XL  = _font(22, bold=True)
SANS_XXL = _font(28, bold=True)

# ── Helpers ────────────────────────────────────────────────────────────────
def new_frame():
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)

def rrect(d, xy, r=10, fill=None, outline=None, width=1):
    d.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)

def badge(d, x, y, text, bg, fg=WHITE, font=SANS_SM, pad=6):
    tw, th = d.textlength(text, font=font), 14
    bw = int(tw) + pad * 2
    bh = th + pad
    rrect(d, [x, y, x+bw, y+bh], r=5, fill=bg)
    d.text((x+pad, y+pad//2), text, font=font, fill=fg)
    return bw

def progress_bar(d, x, y, w, h, pct, bg=CARD_BORDER, fg=BLUE):
    rrect(d, [x, y, x+w, y+h], r=h//2, fill=bg)
    if pct > 0:
        rrect(d, [x, y, x+int(w*pct), y+h], r=h//2, fill=fg)

# ── Scene 1 — Title card (30 frames) ──────────────────────────────────────
def scene_title(frames):
    for i in range(30):
        img, d = new_frame()
        alpha = min(1.0, i / 12)

        # Logo area
        def faded(c): return tuple(int(v * alpha) for v in c)

        d.text((W//2, 130), "AlgoVoi", font=SANS_XXL,
               fill=faded(WHITE), anchor="mm")
        d.text((W//2, 168), "x402 Payment Widget", font=SANS_LG,
               fill=faded(GRAY1), anchor="mm")

        # Divider
        lw = int(200 * alpha)
        d.line([(W//2 - lw, 190), (W//2 + lw, 190)], fill=faded(CARD_BORDER), width=1)

        # Sub
        d.text((W//2, 215), "Embed on any website in under a minute",
               font=SANS_MD, fill=faded(GRAY2), anchor="mm")

        # Chain badges
        chains = [("ALGO", BLUE), ("VOI", INDIGO), ("XLM", GREEN), ("HBAR", (0,178,137))]
        total  = sum(60 for _ in chains) + 10 * (len(chains)-1)
        cx     = W//2 - total//2
        cy     = 270
        for label, col in chains:
            bw = badge(d, cx, cy, label, faded(col), faded(WHITE), SANS_SM, 10)
            cx += bw + 10

        frames.append(img)

# ── Scene 2 — Code editor (50 frames) ─────────────────────────────────────
CODE_LINES = [
    # (gutter_num, tokens)  token = (text, colour)
    (1,  [("<!DOCTYPE html>",                     SYN_PLAIN)]),
    (2,  [("<html>",                              SYN_TAG)]),
    (3,  [("<head>...",                           GRAY2)]),
    (4,  [("",                                    SYN_PLAIN)]),
    (5,  [("<body>",                              SYN_TAG)]),
    (6,  [("",                                    SYN_PLAIN)]),
    (7,  [("  <!-- 1. Load the widget script -->",GRAY2)]),
    (8,  [("  <", SYN_TAG), ("script ", SYN_TAG),
          ("type", SYN_ATTR), ("=", SYN_PUNCT), ('"module"', SYN_VAL),
          (" src", SYN_ATTR), ("=", SYN_PUNCT),
          ('"https://worker.ilovechicken.co.uk/widget.js"', SYN_VAL),
          (">", SYN_TAG), ("</", SYN_TAG), ("script", SYN_TAG), (">", SYN_TAG)]),
    (9,  [("",                                    SYN_PLAIN)]),
    (10, [("  <!-- 2. Drop in the element -->",   GRAY2)]),
    (11, [("  <", SYN_TAG), ("algovoi-x402",      SYN_TAG)]),
    (12, [("    amount",  SYN_ATTR), ('="', SYN_PUNCT), ("0.01",   SYN_VAL), ('"',SYN_PUNCT)]),
    (13, [("    currency",SYN_ATTR), ('="', SYN_PUNCT), ("USD",    SYN_VAL), ('"',SYN_PUNCT)]),
    (14, [("    chains",  SYN_ATTR), ('="', SYN_PUNCT), ("ALGO,VOI,XLM,HBAR", SYN_VAL), ('"',SYN_PUNCT)]),
    (15, [("    tenant-id",SYN_ATTR),('="', SYN_PUNCT), ("YOUR_TENANT_ID",SYN_VAL),('"',SYN_PUNCT)]),
    (16, [("    api-key", SYN_ATTR), ('="', SYN_PUNCT), ("algv_YOUR_KEY", SYN_VAL),('"',SYN_PUNCT)]),
    (17, [("  >", SYN_TAG), ("</", SYN_TAG), ("algovoi-x402", SYN_TAG), (">", SYN_TAG)]),
    (18, [("",                                    SYN_PLAIN)]),
    (19, [("</body>", SYN_TAG)]),
    (20, [("</html>", SYN_TAG)]),
]

HIGHLIGHT_LINES = {8, 11, 12, 13, 14, 15, 16, 17}

def draw_editor(d, reveal_lines, show_annotation=False):
    # Editor chrome
    EX, EY, EW, EH = 40, 50, W-80, H-80
    rrect(d, [EX, EY, EX+EW, EY+EH], r=10, fill=EDITOR_BG, outline=CARD_BORDER, width=1)

    # Title bar
    rrect(d, [EX, EY, EX+EW, EY+28], r=10, fill=GUTTER_BG)
    d.rectangle([EX, EY+18, EX+EW, EY+28], fill=GUTTER_BG)
    for i, col in enumerate([(220,80,80),(220,185,80),(80,185,80)]):
        d.ellipse([EX+12+i*18, EY+9, EX+22+i*18, EY+19], fill=col)
    d.text((EX+EW//2, EY+14), "your-page.html", font=SANS_SM, fill=GRAY1, anchor="mm")

    # Lines
    GW   = 32
    LH   = 19
    YS   = EY + 36

    for idx, (num, tokens) in enumerate(CODE_LINES):
        if idx >= reveal_lines:
            break
        ly = YS + idx * LH
        if ly > EY + EH - 10:
            break

        is_hl = num in HIGHLIGHT_LINES
        if is_hl:
            d.rectangle([EX+GW+1, ly-1, EX+EW-1, ly+LH-2], fill=(30,38,60))

        # Gutter
        d.text((EX+GW-6, ly+1), str(num), font=MONO_SM,
               fill=BLUE if is_hl else GRAY2, anchor="ra")

        # Tokens
        tx = EX + GW + 8
        for text, col in tokens:
            d.text((tx, ly+1), text, font=MONO_SM, fill=col)
            tx += int(d.textlength(text, font=MONO_SM))

    # Annotation callout
    if show_annotation:
        AX, AY = EX + EW - 230, EY + EH - 95
        AW, AH = 210, 80
        rrect(d, [AX, AY, AX+AW, AY+AH], r=8,
              fill=(20,40,20), outline=GREEN, width=1)
        d.text((AX+10, AY+10), "✓  2 lines of HTML", font=SANS_SM, fill=GREEN)
        d.text((AX+10, AY+28), "✓  Works on any domain", font=SANS_SM, fill=GREEN)
        d.text((AX+10, AY+46), "✓  No backend required", font=SANS_SM, fill=GREEN)
        d.text((AX+10, AY+64), "✓  4 chains out of the box", font=SANS_SM, fill=GREEN)

def scene_editor(frames):
    total = len(CODE_LINES)
    # Reveal lines one by one (40 frames), then hold with annotation (10)
    for i in range(40):
        reveal = max(1, round((i / 30) * total))
        img, d = new_frame()
        draw_editor(d, reveal, show_annotation=False)
        frames.append(img)
    for _ in range(20):
        img, d = new_frame()
        draw_editor(d, total, show_annotation=True)
        frames.append(img)

# ── Widget card helpers ────────────────────────────────────────────────────
CX, CY, CW, CH = 220, 30, 280, 420   # card bounds

def draw_widget_shell(d, amount="$0.01", show_buttons=True, disabled=False):
    # Card
    rrect(d, [CX, CY, CX+CW, CY+CH], r=16, fill=CARD_BG, outline=CARD_BORDER, width=1)

    # Badge row
    d.ellipse([CX+18, CY+20, CX+25, CY+27], fill=BLUE)
    d.text((CX+30, CY+18), "USDC · MULTI-CHAIN · POWERED BY ALGOVOI",
           font=SANS_SM, fill=GRAY2)

    # Amount card
    AX, AY = CX+14, CY+48
    rrect(d, [AX, AY, AX+252, AY+72], r=12, fill=BG, outline=CARD_BORDER, width=1)
    d.text((AX+14, AY+10), "AMOUNT", font=SANS_SM, fill=GRAY1)
    d.text((AX+14, AY+28), amount, font=SANS_XL, fill=GREEN)
    d.text((AX+14, AY+58), "USD · stablecoin", font=SANS_SM, fill=GRAY1)
    d.text((AX+230, AY+24), "⚡", font=SANS_XL, fill=(60,60,60))

    # Chain buttons
    if show_buttons:
        chains = [("Algorand", BLUE), ("VOI", INDIGO), ("Stellar", GREEN), ("Hedera", (0,165,120))]
        bw, bh = 116, 36
        for idx, (label, col) in enumerate(chains):
            bx = CX + 14 + (idx % 2) * (bw + 8)
            by = CY + 136 + (idx // 2) * (bh + 8)
            bc = tuple(int(v * 0.55) for v in col) if disabled else col
            rrect(d, [bx, by, bx+bw, by+bh], r=10, fill=bc)
            d.text((bx+bw//2, by+bh//2), label, font=SANS_MD,
                   fill=DIM if disabled else WHITE, anchor="mm")

    # Footer
    d.text((CX+14, CY+CH-24), "Instant · On-chain · No chargebacks",
           font=SANS_SM, fill=GRAY2)
    d.text((CX+CW-14, CY+CH-24), "AlgoVoi", font=SANS_SM, fill=BLUE, anchor="ra")

def draw_loading_overlay(d):
    # Spinner button
    BX, BY = CX+14, CY+136
    rrect(d, [BX, BY, BX+252, BY+36], r=10, fill=BLUE)
    d.text((BX+126, BY+18), "Creating link…", font=SANS_MD, fill=WHITE, anchor="mm")

def draw_ready_box(d, url_preview="api1.ilovechicken.co.uk/checkout/…"):
    BX, BY, BW, BH = CX+14, CY+220, 252, 80
    rrect(d, [BX, BY, BX+BW, BY+BH], r=10, fill=BG, outline=CARD_BORDER, width=1)
    d.text((BX+BW//2, BY+14), "Your secure checkout is ready.",
           font=SANS_SM, fill=DIM, anchor="mm")
    rrect(d, [BX+20, BY+32, BX+BW-20, BY+60], r=8, fill=BLUE)
    d.text((BX+BW//2, BY+46), "Complete Payment →",
           font=SANS_MD, fill=WHITE, anchor="mm")
    d.text((BX+BW//2, BY+70), url_preview,
           font=SANS_SM, fill=GRAY2, anchor="mm")

def draw_annotation(d, text_lines, x, y, colour=BLUE):
    lh = 18
    w  = max(int(d.textlength(t, font=SANS_SM)) for t in text_lines) + 20
    h  = lh * len(text_lines) + 12
    rrect(d, [x, y, x+w, y+h], r=7, fill=(15,25,45), outline=colour, width=1)
    for i, t in enumerate(text_lines):
        d.text((x+10, y+8+i*lh), t, font=SANS_SM, fill=colour)
    # Connector dot
    d.ellipse([CX+CW-4, y+h//2-4, CX+CW+4, y+h//2+4], fill=colour)
    d.line([(CX+CW, y+h//2), (x, y+h//2)], fill=colour, width=1)

# ── Scene 3 — Widget idle (20 frames) ─────────────────────────────────────
def scene_idle(frames):
    for i in range(20):
        alpha = min(1.0, i / 8)
        img, d = new_frame()
        # Left: code snippet (condensed)
        d.text((30, 20), "your-page.html", font=SANS_SM, fill=GRAY2)
        snippet = [
            ('<script src="…/widget.js"></script>', SYN_TAG),
            ('', SYN_PLAIN),
            ('<algovoi-x402', SYN_TAG),
            ('  amount="0.01"', SYN_ATTR),
            ('  chains="ALGO,VOI,XLM,HBAR"', SYN_ATTR),
            ('  tenant-id="…"', SYN_ATTR),
            ('  api-key="algv_…">', SYN_ATTR),
            ('</algovoi-x402>', SYN_TAG),
        ]
        SX, SY = 20, 44
        rrect(d, [SX-8, SY-6, SX+195, SY+len(snippet)*17+6], r=6,
              fill=EDITOR_BG, outline=CARD_BORDER, width=1)
        for j, (txt, col) in enumerate(snippet):
            d.text((SX, SY + j*17), txt, font=MONO_SM,
                   fill=tuple(int(v*alpha) for v in col))

        # Arrow
        ax = 220
        d.line([(210, H//2), (ax-6, H//2)], fill=GRAY2, width=2)
        d.polygon([(ax-6,H//2-5),(ax+2,H//2),(ax-6,H//2+5)], fill=GRAY2)

        # Widget card
        draw_widget_shell(d, show_buttons=True)

        # Annotation
        if i >= 12:
            draw_annotation(d,
                ["Renders instantly", "Zero config"],
                CX+CW+10, CY+130, BLUE)
        frames.append(img)

# ── Scene 4 — Click + loading (16 frames) ────────────────────────────────
def scene_loading(frames):
    for i in range(16):
        img, d = new_frame()
        draw_widget_shell(d, show_buttons=False, disabled=True)
        draw_loading_overlay(d)
        # Animated progress bar
        pct = min(1.0, i / 14)
        progress_bar(d, CX+14, CY+180, 252, 6, pct)
        draw_annotation(d,
            ["POST /api/x402/demo", "→ AlgoVoi gateway"],
            CX+CW+10, CY+130, INDIGO)
        frames.append(img)

# ── Scene 5 — Ready state (24 frames) ────────────────────────────────────
def scene_ready(frames):
    for i in range(24):
        img, d = new_frame()
        draw_widget_shell(d, show_buttons=True)
        draw_ready_box(d)
        if i >= 6:
            draw_annotation(d,
                ["Checkout link created", "30-min expiry", "On-chain settlement"],
                CX+CW+10, CY+215, GREEN)
        frames.append(img)

# ── Scene 6 — Final call-to-action (20 frames) ───────────────────────────
def scene_cta(frames):
    for i in range(25):
        alpha = min(1.0, i / 10)
        img, d = new_frame()

        def fa(c): return tuple(int(v*alpha) for v in c)

        draw_widget_shell(d, show_buttons=True)

        # Right panel CTA
        RX = CX + CW + 20
        d.text((RX, 60),  "That's it.",           font=SANS_XL,  fill=fa(WHITE))
        d.text((RX, 100), "Two lines of HTML.",    font=SANS_LG,  fill=fa(GRAY1))
        d.text((RX, 125), "Any website. Any chain.", font=SANS_MD, fill=fa(GRAY2))

        steps = [
            ("1", "Get your AlgoVoi tenant ID + API key"),
            ("2", "Add the <script> tag"),
            ("3", "Add <algovoi-x402> element"),
            ("4", "Done — collect crypto payments"),
        ]
        for j, (num, txt) in enumerate(steps):
            sy = 170 + j * 40
            rrect(d, [RX, sy, RX+20, sy+20], r=4, fill=fa(BLUE))
            d.text((RX+10, sy+10), num, font=SANS_SM, fill=fa(WHITE), anchor="mm")
            for line in textwrap.wrap(txt, width=22):
                d.text((RX+28, sy+3), line, font=SANS_SM, fill=fa(DIM))
                sy += 15

        d.text((RX, H-60), "worker.ilovechicken.co.uk", font=MONO_SM, fill=fa(BLUE))

        frames.append(img)

# ── Assemble ───────────────────────────────────────────────────────────────
def main():
    frames = []
    scene_title(frames)
    scene_editor(frames)
    scene_idle(frames)
    scene_loading(frames)
    scene_ready(frames)
    scene_cta(frames)

    # Hold last frame for 3 s
    for _ in range(int(3 * FPS)):
        frames.append(frames[-1].copy())

    out = os.path.join(os.path.dirname(__file__), "algovoi_widget_embed.gif")
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=DELAY,
        optimize=False,
    )
    size_kb = os.path.getsize(out) / 1024
    print(f"Saved {out}  ({len(frames)} frames, {size_kb:.0f} KB)")

if __name__ == "__main__":
    main()
