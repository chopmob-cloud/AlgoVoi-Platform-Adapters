"""
AlgoVoi x402 Widget — Embed Demo GIF
=====================================
Shows how simple it is to add crypto payments to any website:
  Scene 1 — Title card with logo
  Scene 2 — Minimal HTML snippet typing out (credentials as placeholders)
  Scene 3 — Widget rendering: idle state
  Scene 4 — Click → loading → API call annotation
  Scene 5 — Ready state with checkout link annotation
  Scene 6 — CTA / summary card

Usage:
    python -X utf8 make_widget_gif.py
"""

from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Theme (matches AI-adapter demo GIFs) ──────────────────────────────────
BG          = (13,  17,  23)
TEXT        = (201, 209, 217)
PROMPT      = (88,  166, 255)
MUTED       = (110, 118, 135)
TITLE_FG    = (255, 255, 255)
TITLE_BG    = (36,   41,  46)
CURSOR_COL  = (88,  166, 255)

# Syntax colours
SYN_TAG     = (129, 182, 255)
SYN_ATTR    = (255, 198, 109)
SYN_VAL     = (152, 195, 121)
SYN_PH      = (255, 135,  80)   # placeholder (tenant-id / api-key values)
SYN_COMMENT = (110, 118, 135)
SYN_PLAIN   = (201, 209, 217)
SYN_PUNCT   = (171, 178, 191)

# Widget colours
GREEN       = (16,  185, 129)
BLUE        = (59,  130, 246)
INDIGO      = (99,  102, 241)
GRAY1       = (107, 114, 128)
GRAY2       = (75,   85,  99)
DIM         = (156, 163, 175)
CARD_BG     = (26,  29,  46)
CARD_BORDER = (42,  45,  58)
EDITOR_BG   = (18,  20,  30)

# Annotation overlay (identical to AI-adapter GIFs)
ANN_BG      = (22,  27,  34)
ANN_BORDER  = (48,  54,  61)
ANN_TITLE   = (88,  166, 255)
ANN_BODY    = (201, 209, 217)
ANN_ICON_BG = (31,  111, 235)

# ── Canvas ─────────────────────────────────────────────────────────────────
W, H     = 900, 520
LPAD     = 28
LINE_H   = 22
TOP      = 72
FRAME_MS = 50   # 20 fps — same as AI-adapter GIFs

# ── Fonts ──────────────────────────────────────────────────────────────────
def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in [r"C:\Windows\Fonts\consola.ttf",
              r"C:\Windows\Fonts\cour.ttf",
              r"C:\Windows\Fonts\lucon.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()

FONT     = _font(14)
FONT_B   = _font(15)
FONT_SM  = _font(12)
FONT_LG  = _font(18)
FONT_XL  = _font(24)
FONT_XXL = _font(30)
FONT_ANN = _font(13)
FONT_ANH = _font(14)

# ── Helpers ────────────────────────────────────────────────────────────────
def _new_frame():
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)

def _title_bar(d, right_label="x402 Embeddable Widget"):
    d.rectangle([0, 0, W, 46], fill=TITLE_BG)
    for x, c in [(18,(255,95,86)),(38,(255,189,46)),(58,(39,201,63))]:
        d.ellipse([x-6,17,x+6,29], fill=c)
    d.text((W//2, 23), f"AlgoVoi — {right_label}",
           font=FONT_B, fill=TITLE_FG, anchor="mm")
    d.rectangle([0, H-28, W, H], fill=TITLE_BG)
    d.text((LPAD, H-20), "worker.ilovechicken.co.uk",
           font=FONT_SM, fill=MUTED, anchor="lm")
    d.text((W-LPAD, H-20),
           "github.com/chopmob-cloud/AlgoVoi-Platform-Adapters",
           font=FONT_SM, fill=MUTED, anchor="rm")

def _badge(d, x, y, text, color):
    tw = int(d.textlength(text, font=FONT_SM)) + 12
    d.rounded_rectangle([x, y-2, x+tw, y+16], radius=4, fill=color)
    d.text((x+6, y+7), text, font=FONT_SM, fill=(255,255,255), anchor="lm")
    return x + tw + 8

def _cursor(d, x, y):
    d.rectangle([x, y+2, x+9, y+16], fill=CURSOR_COL)

# ── Logo loader (identical to AI-adapter GIFs) ─────────────────────────────
def _make_logo(width=460, height=120):
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "algovoi_logo.png")
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((width, height), Image.LANCZOS)
        canvas = Image.new("RGBA", (width, height), (*BG, 255))
        x = (width  - logo.width)  // 2
        y = (height - logo.height) // 2
        r, g, b, a = logo.split()
        if a.getextrema() == (255, 255):
            import PIL.ImageChops as chops
            cr, cg, cb, _ = logo.getpixel((0, 0))
            ref  = Image.new("RGBA", logo.size, (cr, cg, cb, 255))
            diff = chops.difference(logo, ref).convert("L")
            diff = diff.point(lambda v: min(255, v * 8))
            logo.putalpha(diff)
        canvas.paste(logo, (x, y), logo)
        return canvas.convert("RGB")

    # Drawn fallback
    canvas = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(canvas)
    sz = height - 10
    grad = Image.new("RGB", (sz, sz))
    gd   = ImageDraw.Draw(grad)
    for px in range(sz):
        for py in range(sz):
            t = (px+py) / (sz*2-2)
            gd.point((px,py), fill=(
                int(0   + 180*t), int(212 - 132*t), int(255 + 0*t)))
    mask = Image.new("L", (sz, sz), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0,0,sz-1,sz-1], radius=sz//5, fill=255)
    icon = Image.composite(grad, Image.new("RGB",(sz,sz),BG), mask)
    canvas.paste(icon, (5, 5))
    d.text((5+sz//2, 5+sz//2), "AV", font=_font(sz//3),
           fill=(10,10,10), anchor="mm")
    d.text((5+sz+18, 5+sz//2), "AlgoVoi", font=_font(sz//2),
           fill=(255,255,255), anchor="lm")
    return canvas

# ── Annotation overlay (identical to AI-adapter GIFs) ─────────────────────
def _annotate(img, heading, lines, alpha=1.0):
    if alpha <= 0:
        return img
    overlay = img.copy()
    d = ImageDraw.Draw(overlay)
    pad    = 16
    lh     = 20
    ph     = pad*2 + lh + len(lines)*lh + 4
    y0     = H - 28 - ph - 8
    y1     = H - 28 - 8
    x0, x1 = LPAD-4, W-LPAD+4
    d.rounded_rectangle([x0,y0,x1,y1], radius=6, fill=ANN_BG)
    d.rounded_rectangle([x0,y0,x1,y1], radius=6, outline=ANN_BORDER, width=1)
    ix, iy = x0+pad, y0+pad+lh//2
    d.ellipse([ix-9,iy-9,ix+9,iy+9], fill=ANN_ICON_BG)
    d.text((ix,iy), "i", font=FONT_B, fill=(255,255,255), anchor="mm")
    tx = ix+18
    d.text((tx, y0+pad), heading, font=FONT_ANH, fill=ANN_TITLE)
    for i, line in enumerate(lines):
        d.text((tx, y0+pad+lh+4+i*lh), line, font=FONT_ANN, fill=ANN_BODY)
    return Image.blend(img, overlay, alpha)

def _ann_frames(base, heading, lines, hold=60):
    fade = 8
    out  = []
    for i in range(fade):
        out.append(_annotate(base.copy(), heading, lines, (i+1)/fade))
    for _ in range(hold):
        out.append(_annotate(base.copy(), heading, lines, 1.0))
    for i in range(fade):
        out.append(_annotate(base.copy(), heading, lines, 1.0-(i+1)/fade))
    return out

# ── Scene 1 — Title card ───────────────────────────────────────────────────
def scene_title():
    logo   = _make_logo(width=460, height=120)
    frames = []

    for i in range(40):
        img, d = _new_frame()
        _title_bar(d)

        alpha = min(1.0, i / 12)
        def fa(c): return tuple(int(v*alpha) for v in c)

        # Logo centred
        lx = (W - logo.width)  // 2
        ly = 90
        if alpha < 1.0:
            dark = Image.new("RGB", logo.size, BG)
            img.paste(Image.blend(dark, logo, alpha), (lx, ly))
        else:
            img.paste(logo, (lx, ly))

        d.text((W//2, ly+logo.height+22),
               "x402 Embeddable Payment Widget",
               font=FONT_LG, fill=fa(MUTED), anchor="mm")

        # Chain badges
        chains = [("ALGO",(31,111,235)),("VOI",(80,70,200)),
                  ("XLM",(16,185,129)),("HBAR",(0,165,120))]
        bw_total = sum(int(d.textlength(l, font=FONT_SM))+12+8 for l,_ in chains) - 8
        bx = W//2 - bw_total//2
        by = ly + logo.height + 52
        for label, col in chains:
            col_f = fa(col)
            tw = int(d.textlength(label, font=FONT_SM)) + 12
            d.rounded_rectangle([bx,by-2,bx+tw,by+16], radius=4, fill=col_f)
            d.text((bx+6,by+7), label, font=FONT_SM, fill=fa((255,255,255)), anchor="lm")
            bx += tw + 8

        d.text((W//2, by+38),
               "Embed on any website · no backend · any chain",
               font=FONT_SM, fill=fa(MUTED), anchor="mm")
        frames.append(img)

    # Hold
    for _ in range(20):
        frames.append(frames[-1].copy())
    return frames

# ── Code lines definition ──────────────────────────────────────────────────
# Each entry: (line_num, [(text, colour), ...])
CODE = [
    (1,  [("<!DOCTYPE html>",                           SYN_PLAIN)]),
    (2,  [("<html>",                                    SYN_TAG)]),
    (3,  [("<head>...",                                 SYN_COMMENT)]),
    (4,  [("",                                          SYN_PLAIN)]),
    (5,  [("<body>",                                    SYN_TAG)]),
    (6,  [("",                                          SYN_PLAIN)]),
    (7,  [("  <!-- 1. Load widget script -->",          SYN_COMMENT)]),
    (8,  [("  <",SYN_TAG),("script ",SYN_TAG),
          ("type",SYN_ATTR),('="',SYN_PUNCT),("module",SYN_VAL),('" ',SYN_PUNCT),
          ("src",SYN_ATTR),('="',SYN_PUNCT),
          ("https://worker.ilovechicken.co.uk/widget.js",SYN_VAL),('"',SYN_PUNCT),
          ("></",SYN_TAG),("script",SYN_TAG),(">",SYN_TAG)]),
    (9,  [("",                                          SYN_PLAIN)]),
    (10, [("  <!-- 2. Drop in the element -->",         SYN_COMMENT)]),
    (11, [("  <",SYN_TAG),("algovoi-x402",              SYN_TAG)]),
    (12, [("    amount",SYN_ATTR),('="',SYN_PUNCT),("0.01",SYN_VAL),('"',SYN_PUNCT)]),
    (13, [("    currency",SYN_ATTR),('="',SYN_PUNCT),("USD",SYN_VAL),('"',SYN_PUNCT)]),
    (14, [("    chains",SYN_ATTR),('="',SYN_PUNCT),("ALGO,VOI,XLM,HBAR",SYN_VAL),('"',SYN_PUNCT)]),
    (15, [("    tenant-id",SYN_ATTR),('="',SYN_PUNCT),("YOUR_TENANT_ID",SYN_PH),('"',SYN_PUNCT)]),
    (16, [("    api-key",SYN_ATTR),('="',SYN_PUNCT),("algv_YOUR_KEY",SYN_PH),('"',SYN_PUNCT)]),
    (17, [("  >",SYN_TAG),("</",SYN_TAG),("algovoi-x402",SYN_TAG),(">",SYN_TAG)]),
    (18, [("",                                          SYN_PLAIN)]),
    (19, [("</body>",                                   SYN_TAG)]),
    (20, [("</html>",                                   SYN_TAG)]),
]
HL_LINES = {8, 11, 12, 13, 14, 15, 16, 17}

def _draw_editor(d, img, reveal, title="your-page.html"):
    EX, EY, EW, EH = 30, 52, W-60, H-90
    # Shadow
    for s in range(4, 0, -1):
        d.rounded_rectangle([EX+s,EY+s,EX+EW+s,EY+EH+s],
                             radius=10, fill=(8,10,15))
    d.rounded_rectangle([EX,EY,EX+EW,EY+EH], radius=10,
                         fill=EDITOR_BG, outline=(40,44,56), width=1)

    # Title bar
    d.rounded_rectangle([EX,EY,EX+EW,EY+30], radius=10, fill=TITLE_BG)
    d.rectangle([EX,EY+20,EX+EW,EY+30], fill=TITLE_BG)
    for i,(col) in enumerate([(255,95,86),(255,189,46),(39,201,63)]):
        d.ellipse([EX+14+i*20-5, EY+10-5, EX+14+i*20+5, EY+10+5], fill=col)
    d.text((EX+EW//2, EY+15), title, font=FONT_SM, fill=MUTED, anchor="mm")

    GW, LH = 36, 19
    YS = EY + 38

    for idx, (num, tokens) in enumerate(CODE):
        if idx >= reveal:
            break
        ly = YS + idx * LH
        if ly > EY + EH - 12:
            break
        is_hl = num in HL_LINES
        if is_hl:
            d.rectangle([EX+GW+1, ly-1, EX+EW-2, ly+LH-1], fill=(22,32,52))
        # Gutter line
        gutter_col = BLUE if is_hl else (50,55,68)
        d.text((EX+GW-4, ly+2), str(num), font=FONT_SM,
               fill=gutter_col, anchor="ra")
        # Tokens
        tx = EX + GW + 10
        for text, col in tokens:
            d.text((tx, ly+2), text, font=FONT, fill=col)
            tx += int(d.textlength(text, font=FONT))

def _draw_legend(d):
    """Colour legend for placeholder values."""
    lx, ly = 30, H - 60
    d.text((lx, ly), "●", font=FONT_SM, fill=SYN_PH)
    d.text((lx+14, ly), "= replace with your AlgoVoi credentials",
           font=FONT_SM, fill=MUTED)

# ── Scene 2 — Code editor typing out ──────────────────────────────────────
def scene_editor():
    frames = []
    total  = len(CODE)

    # Reveal lines one-by-one over ~50 frames
    for i in range(55):
        reveal = max(1, round((i / 42) * total))
        img, d = _new_frame()
        _title_bar(d, "Embed in 2 lines of HTML")
        _draw_editor(d, img, reveal)
        # Blinking cursor on current line
        if reveal < total:
            idx = reveal - 1
            ly  = 52 + 38 + idx * 19
            tx  = 30 + 36 + 10
            for _, tokens in [CODE[idx]]:
                for text, _ in tokens:
                    tx += int(d.textlength(text, font=FONT))
            if (i // 4) % 2 == 0:
                _cursor(d, tx, ly)
        frames.append(img)

    # Fully revealed — add annotation with fade
    img_full, d_full = _new_frame()
    _title_bar(d_full, "Embed in 2 lines of HTML")
    _draw_editor(d_full, img_full, total)
    _draw_legend(d_full)

    frames += _ann_frames(
        img_full,
        "That's the entire integration",
        [
            "One <script> tag loads the widget from worker.ilovechicken.co.uk",
            "One <algovoi-x402> element drops the payment card onto your page",
            "Set amount, chains, tenant-id and api-key — or use api-url for a backend proxy",
            "See README: Option A (algvw_ domain key) or Option B (api-url proxy, zero creds in HTML)",
        ],
        hold=55,
    )
    return frames

# ── Widget card drawing helpers ────────────────────────────────────────────
CX, CY, CW, CH = 240, 52, 320, 400

def _card(d, amount="$0.01", state="idle", checkout_url="", err_msg=""):
    # Shadow
    for s in range(5, 0, -1):
        d.rounded_rectangle([CX+s, CY+s, CX+CW+s, CY+CH+s],
                             radius=16, fill=(8,10,15))
    # Card
    d.rounded_rectangle([CX, CY, CX+CW, CY+CH], radius=16,
                         fill=CARD_BG, outline=CARD_BORDER, width=1)
    # Badge
    d.ellipse([CX+16, CY+18, CX+23, CY+25], fill=BLUE)
    d.text((CX+28, CY+17), "USDC · MULTI-CHAIN · POWERED BY ALGOVOI",
           font=FONT_SM, fill=GRAY2)

    # Amount card
    AX, AY = CX+12, CY+42
    d.rounded_rectangle([AX, AY, AX+296, AY+76], radius=12,
                         fill=BG, outline=CARD_BORDER, width=1)
    d.text((AX+12, AY+8),  "AMOUNT",  font=FONT_SM, fill=GRAY1)
    d.text((AX+12, AY+28), amount,    font=FONT_XL,  fill=GREEN)
    d.text((AX+12, AY+60), "USD · stablecoin", font=FONT_SM, fill=GRAY1)
    d.text((AX+278, AY+30), "⚡", font=FONT_LG, fill=(45,50,65), anchor="ra")

    # Chain buttons
    if state in ("idle", "ready", "done", "error"):
        chains = [("Algorand",BLUE),("VOI",INDIGO),("Stellar",GREEN),("Hedera",(0,165,120))]
        bw, bh = 140, 38
        for idx, (label, col) in enumerate(chains):
            bx = CX + 12 + (idx % 2) * (bw + 8)
            by = CY + 134 + (idx // 2) * (bh + 10)
            dim_col = tuple(int(v*0.45) for v in col)
            use_col = dim_col if state in ("done",) else col
            d.rounded_rectangle([bx, by, bx+bw, by+bh], radius=10, fill=use_col)
            d.text((bx+bw//2, by+bh//2), label, font=FONT_B,
                   fill=DIM if state=="done" else (255,255,255), anchor="mm")

    # Loading state
    if state == "loading":
        d.rounded_rectangle([CX+12, CY+134, CX+12+296, CY+172], radius=10, fill=BLUE)
        d.text((CX+12+148, CY+153), "Creating link…",
               font=FONT_B, fill=(255,255,255), anchor="mm")

    # Ready box
    if state == "ready":
        RX, RY, RW, RH = CX+12, CY+220, 296, 90
        d.rounded_rectangle([RX,RY,RX+RW,RY+RH], radius=10,
                             fill=BG, outline=CARD_BORDER, width=1)
        d.text((RX+RW//2, RY+14), "Your secure checkout is ready.",
               font=FONT_SM, fill=DIM, anchor="mm")
        d.rounded_rectangle([RX+16,RY+30,RX+RW-16,RY+62], radius=8, fill=BLUE)
        d.text((RX+RW//2, RY+46), "Complete Payment →",
               font=FONT_B, fill=(255,255,255), anchor="mm")
        short = checkout_url[-38:] if len(checkout_url) > 38 else checkout_url
        d.text((RX+RW//2, RY+76), short, font=FONT_SM, fill=GRAY2, anchor="mm")

    # Error
    if state == "error":
        EX2, EY2 = CX+12, CY+224
        d.rounded_rectangle([EX2, EY2, EX2+296, EY2+32], radius=8,
                             fill=(40,16,16), outline=(120,30,30), width=1)
        d.text((EX2+10, EY2+10), err_msg or "Something went wrong. Try again.",
               font=FONT_SM, fill=(239,68,68))

    # Footer
    d.text((CX+12, CY+CH-20), "Instant · On-chain · No chargebacks",
           font=FONT_SM, fill=GRAY2)
    d.text((CX+CW-12, CY+CH-20), "AlgoVoi", font=FONT_SM, fill=BLUE, anchor="ra")

def _left_snippet(d):
    """Condensed code snippet shown to the left of the widget card."""
    sx, sy = 18, 60
    lines = [
        ('<script src="…/widget.js">', SYN_TAG),
        ('</script>',                  SYN_TAG),
        ('',                           SYN_PLAIN),
        ('<algovoi-x402',              SYN_TAG),
        ('  amount="0.01"',            SYN_ATTR),
        ('  chains="ALGO,VOI…"',       SYN_ATTR),
        ('  tenant-id="…"',            SYN_PH),
        ('  api-key="algv_…"',         SYN_PH),
        ('>',                          SYN_TAG),
        ('</algovoi-x402>',            SYN_TAG),
    ]
    # Mini editor background
    max_w = max(int(d.textlength(t, font=FONT_SM))+4 for t,_ in lines if t)
    d.rounded_rectangle([sx-6, sy-4, sx+max_w+8, sy+len(lines)*16+6],
                         radius=6, fill=EDITOR_BG, outline=(35,40,55), width=1)
    for j, (txt, col) in enumerate(lines):
        d.text((sx, sy+j*16), txt, font=FONT_SM, fill=col)

    # Colour key
    d.text((sx, sy+len(lines)*16+12), "● replace with your credentials",
           font=FONT_SM, fill=SYN_PH)

# ── Scene 3 — Idle state ──────────────────────────────────────────────────
def scene_idle():
    frames = []
    for i in range(30):
        alpha = min(1.0, i / 10)
        img, d = _new_frame()
        _title_bar(d, "Any page + 2 tags = crypto payments")

        def fa(c): return tuple(int(v*alpha) for v in c)

        # Left snippet (fading in)
        sx, sy = 18, 60
        lines = [
            ('<script src="…/widget.js">',   SYN_TAG),
            ('</script>',                    SYN_TAG),
            ('',                             SYN_PLAIN),
            ('<algovoi-x402',               SYN_TAG),
            ('  amount="0.01"',              SYN_ATTR),
            ('  chains="ALGO,VOI…"',         SYN_ATTR),
            ('  tenant-id="…"',              SYN_PH),
            ('  api-key="algv_…"',           SYN_PH),
            ('>',                            SYN_TAG),
            ('</algovoi-x402>',             SYN_TAG),
        ]
        max_w = max(int(d.textlength(t, font=FONT_SM))+4 for t,_ in lines if t)
        d.rounded_rectangle([sx-6, sy-4, sx+max_w+8, sy+len(lines)*16+6],
                             radius=6, fill=EDITOR_BG, outline=(35,40,55), width=1)
        for j, (txt, col) in enumerate(lines):
            d.text((sx, sy+j*16), txt, font=FONT_SM, fill=fa(col))
        d.text((sx, sy+len(lines)*16+14), "● = your credentials",
               font=FONT_SM, fill=fa(SYN_PH))

        # Arrow
        ax = CX - 10
        d.line([(sx+max_w+10, H//2-10), (ax-4, H//2-10)],
               fill=fa(MUTED), width=2)
        d.polygon([(ax-4,H//2-15),(ax+4,H//2-10),(ax-4,H//2-5)], fill=fa(MUTED))

        # Widget
        _card(d, state="idle")
        frames.append(img)

    # Hold with annotation
    img_hold, d_hold = _new_frame()
    _title_bar(d_hold, "Any page + 2 tags = crypto payments")
    _left_snippet(d_hold)
    _card(d_hold, state="idle")
    ax = CX - 10
    d_hold.line([(200, H//2-10),(ax-4,H//2-10)], fill=MUTED, width=2)
    d_hold.polygon([(ax-4,H//2-15),(ax+4,H//2-10),(ax-4,H//2-5)], fill=MUTED)

    frames += _ann_frames(
        img_hold,
        "Works on any website — zero server changes",
        [
            "The widget script is served from Cloudflare Pages (global CDN)",
            "CORS: Access-Control-Allow-Origin: * — embed from any domain",
            "Supports Algorand, VOI, Stellar and Hedera out of the box",
        ],
        hold=50,
    )
    return frames

# ── Scene 4 — Loading ──────────────────────────────────────────────────────
def scene_loading():
    frames = []
    for i in range(30):
        img, d = _new_frame()
        _title_bar(d, "Click a chain — payment link created instantly")
        _left_snippet(d)
        _card(d, state="loading")

        # Animated progress bar
        pct = min(0.95, i / 26)
        BX, BY = CX+12, CY+178
        d.rounded_rectangle([BX,BY,BX+296,BY+5], radius=2, fill=(30,35,50))
        if pct > 0:
            d.rounded_rectangle([BX,BY,BX+int(296*pct),BY+5], radius=2, fill=BLUE)
        frames.append(img)

    img_load, d_load = _new_frame()
    _title_bar(d_load, "Click a chain — payment link created instantly")
    _left_snippet(d_load)
    _card(d_load, state="loading")
    d_load.rounded_rectangle([CX+12,CY+178,CX+12+296,CY+183], radius=2, fill=BLUE)

    frames += _ann_frames(
        img_load,
        "POST api-url → AlgoVoi gateway",
        [
            "Widget POSTs to api-url — default worker endpoint, or your own backend",
            "AlgoVoi creates a hosted checkout link valid for 30 minutes",
            "No wallet SDK, no Web3 library — the widget handles everything",
        ],
        hold=45,
    )
    return frames

# ── Scene 5 — Ready ────────────────────────────────────────────────────────
def scene_ready():
    frames = []
    checkout = "api1.ilovechicken.co.uk/checkout/abc…xyz"

    for i in range(20):
        alpha = min(1.0, i / 8)
        img, d = _new_frame()
        _title_bar(d, "Checkout link ready — buyer pays on-chain")
        _left_snippet(d)
        _card(d, state="ready" if alpha > 0.5 else "idle",
              checkout_url=checkout)
        frames.append(img)

    img_ready, d_ready = _new_frame()
    _title_bar(d_ready, "Checkout link ready — buyer pays on-chain")
    _left_snippet(d_ready)
    _card(d_ready, state="ready", checkout_url=checkout)

    frames += _ann_frames(
        img_ready,
        "On-chain settlement — instant, no chargebacks",
        [
            "Buyer opens the checkout link — QR code + wallet deep-link shown",
            "Payment confirmed on Algorand / VOI / Stellar / Hedera in seconds",
            "Funds arrive directly in your payout wallet — no intermediary",
        ],
        hold=55,
    )
    return frames

# ── Scene 6 — Security options ────────────────────────────────────────────
OPTION_A_CODE = [
    ("<!-- Option A: origin-restricted widget key -->", SYN_COMMENT),
    ("<algovoi-x402",                                   SYN_TAG),
    ('  amount="29.99"  currency="USD"',                SYN_ATTR),
    ('  chains="ALGO,VOI,XLM,HBAR"',                   SYN_ATTR),
    ('  tenant-id="YOUR_TENANT_ID"',                    SYN_PH),
    ('  api-key="algvw_YOUR_KEY">',                     SYN_PH),
    ("</algovoi-x402>",                                 SYN_TAG),
]

OPTION_B_CODE = [
    ("<!-- Option B: backend proxy, zero creds in HTML -->", SYN_COMMENT),
    ("<algovoi-x402",                                         SYN_TAG),
    ('  amount="29.99"  currency="USD"',                     SYN_ATTR),
    ('  chains="ALGO,VOI,XLM,HBAR"',                         SYN_ATTR),
    ('  api-url="/api/create-payment">',                      SYN_VAL),
    ("</algovoi-x402>",                                       SYN_TAG),
    ("",                                                       SYN_PLAIN),
]

def _draw_sec_panels(d, alpha=1.0):
    def fa(c): return tuple(int(v*alpha) for v in c)

    PA_X = 30
    PB_X = W // 2 + 12
    CODE_Y = 108
    LH = 19

    # ── Panel A ──
    # Header pill
    d.rounded_rectangle([PA_X, 58, PA_X+178, 80], radius=6, fill=fa((20,40,80)))
    d.text((PA_X+8, 69), "Option A — Widget key (algvw_)",
           font=FONT_SM, fill=fa(BLUE), anchor="lm")
    d.text((PA_X, 86), "Visible in source, locked to your domain",
           font=FONT_SM, fill=fa(MUTED))

    # Code block A
    max_w_a = max(int(d.textlength(t, font=FONT_SM))+4 for t,_ in OPTION_A_CODE if t)
    d.rounded_rectangle([PA_X-4, CODE_Y-4, PA_X+max_w_a+8, CODE_Y+len(OPTION_A_CODE)*LH+6],
                         radius=6, fill=fa(EDITOR_BG))
    for j, (txt, col) in enumerate(OPTION_A_CODE):
        d.text((PA_X, CODE_Y+j*LH), txt, font=FONT_SM, fill=fa(col))

    note_y = CODE_Y + len(OPTION_A_CODE)*LH + 14
    d.text((PA_X, note_y),    "● algvw_ key = domain-locked",  font=FONT_SM, fill=fa(SYN_PH))
    d.text((PA_X, note_y+16), "● X-Widget-Origin forwarded automatically",
           font=FONT_SM, fill=fa(MUTED))
    d.text((PA_X, note_y+32), "✓ Works on static sites, Webflow, Framer",
           font=FONT_SM, fill=fa(GREEN))

    # ── Divider ──
    mid = W // 2
    d.line([(mid, 54), (mid, H-38)], fill=fa((40,45,60)), width=1)

    # ── Panel B ──
    d.rounded_rectangle([PB_X, 58, PB_X+208, 80], radius=6, fill=fa((10,50,30)))
    d.text((PB_X+8, 69), "Option B — Server proxy (api-url)",
           font=FONT_SM, fill=fa(GREEN), anchor="lm")
    d.text((PB_X, 86), "No credentials reach the browser",
           font=FONT_SM, fill=fa(MUTED))

    # Code block B
    max_w_b = max(int(d.textlength(t, font=FONT_SM))+4 for t,_ in OPTION_B_CODE if t)
    d.rounded_rectangle([PB_X-4, CODE_Y-4, PB_X+max_w_b+8, CODE_Y+len(OPTION_B_CODE)*LH+6],
                         radius=6, fill=fa(EDITOR_BG))
    for j, (txt, col) in enumerate(OPTION_B_CODE):
        d.text((PB_X, CODE_Y+j*LH), txt, font=FONT_SM, fill=fa(col))

    note_y = CODE_Y + len(OPTION_B_CODE)*LH + 14
    d.text((PB_X, note_y),    "● api-url = your CF Pages / Next.js / Express route",
           font=FONT_SM, fill=fa(BLUE))
    d.text((PB_X, note_y+16), "● Backend holds ALGOVOI_API_KEY in env vars",
           font=FONT_SM, fill=fa(MUTED))
    d.text((PB_X, note_y+32), "✓ Zero credentials exposed — best for production",
           font=FONT_SM, fill=fa(GREEN))

def scene_security():
    frames = []

    for i in range(30):
        alpha = min(1.0, i / 10)
        img, d = _new_frame()
        _title_bar(d, "Securing your credentials — two options")
        _draw_sec_panels(d, alpha)
        frames.append(img)

    img_sec, d_sec = _new_frame()
    _title_bar(d_sec, "Securing your credentials — two options")
    _draw_sec_panels(d_sec, 1.0)

    frames += _ann_frames(
        img_sec,
        "Protect your API credentials in production",
        [
            "Option A: algvw_ widget key — domain-locked, safe to embed in static HTML",
            "Option B: api-url proxy — credentials live in env vars, never sent to browser",
            "CF Pages, Next.js and Express examples in the widget README",
        ],
        hold=65,
    )
    return frames


# ── Scene 7 — Summary / CTA ────────────────────────────────────────────────
def scene_cta():
    frames = []
    steps = [
        ("1", BLUE,       "Sign up for an AlgoVoi account"),
        ("2", INDIGO,     "Set your payout wallet & chain"),
        ("3", GREEN,      "Add 2 lines of HTML to any page"),
        ("4", (255,165,0),"Choose your security approach — done"),
    ]

    for i in range(50):
        alpha = min(1.0, i / 14)
        img, d = _new_frame()
        _title_bar(d, "x402 Embeddable Widget")
        _card(d, state="idle")

        def fa(c): return tuple(int(v*alpha) for v in c)

        # Right panel
        RX = CX + CW + 28
        d.text((RX, 62), "Get started in",    font=FONT_LG,  fill=fa(MUTED))
        d.text((RX, 86), "60 seconds.",        font=FONT_XXL, fill=fa((255,255,255)))

        for j, (num, col, txt) in enumerate(steps):
            show = i >= 10 + j * 6
            if not show:
                break
            sy = 148 + j * 52
            step_alpha = min(1.0, max(0,(i - 10 - j*6) / 8))
            def fs(c): return tuple(int(v*step_alpha) for v in c)
            d.rounded_rectangle([RX, sy, RX+24, sy+24], radius=5, fill=fs(col))
            d.text((RX+12, sy+12), num, font=FONT_B,
                   fill=fs((255,255,255)), anchor="mm")
            d.text((RX+32, sy+6), txt, font=FONT_ANH, fill=fs(TEXT))

        # URL
        if i >= 36:
            url_alpha = min(1.0, (i-36)/8)
            def fu(c): return tuple(int(v*url_alpha) for v in c)
            d.text((RX, 380), "worker.ilovechicken.co.uk",
                   font=FONT, fill=fu(BLUE))
            d.text((RX, 400), "Full docs in the repo README",
                   font=FONT_SM, fill=fu(MUTED))

        frames.append(img)

    # Hold final
    for _ in range(int(3.5 * (1000/FRAME_MS))):
        frames.append(frames[-1].copy())
    return frames

# ── Save ───────────────────────────────────────────────────────────────────
def main():
    frames = (
        scene_title()    +
        scene_editor()   +
        scene_idle()     +
        scene_loading()  +
        scene_ready()    +
        scene_security() +
        scene_cta()
    )
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "algovoi_widget_embed.gif")
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=FRAME_MS,
        optimize=False,
    )
    kb = os.path.getsize(out) / 1024
    print(f"Saved {out}  ({len(frames)} frames @ {FRAME_MS}ms, {kb:.0f} KB)")

if __name__ == "__main__":
    main()
