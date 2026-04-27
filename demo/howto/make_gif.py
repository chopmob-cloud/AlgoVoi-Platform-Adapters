"""
Compose the captured panel screenshots into an animated 'how to pay with
crypto' demo GIF.

Output: demo/howto/algovoi_howto.gif

Pipeline (~10s @ 20fps, ~200 frames, 900x600 canvas):
  1. Title card  — "AlgoVoi  Pay with Crypto  7 chains"
  2. Panel        — "Customer chooses network" + panel_default.png
  3. Chain cycle  — VOI, Hedera, Solana panels (colour-dot animates per chain)
  4. Widget       — "Embed on any website" + widget_default.png
  5. End card     — "Same panel. Every platform." + GitHub URL

All scenes use 300ms cross-fades.
"""
from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
CAPTURES = os.path.join(ROOT, "captures")
OUTPUT = os.path.join(ROOT, "algovoi_howto.gif")

# ── Theme (matches canonical AlgoVoi panel palette) ──────────────────────────
W, H = 900, 600
BG          = (15,  17,  23)    # #0f1117
PANEL_BG    = (20,  22,  34)    # #141622
PANEL_BORD  = (31,  34,  53)    # #1f2235
TEXT        = (224, 224, 224)   # #e0e0e0
TEXT_DIM    = (156, 163, 175)   # #9ca3af
TEXT_MUTED  = (107, 114, 128)   # #6b7280
TEXT_BRIGHT = (255, 255, 255)
ACCENT      = ( 99, 102, 241)   # indigo
ACCENT_2    = (139,  92, 246)   # purple
BRAND       = ( 59, 130, 246)   # canonical AlgoVoi blue

FPS = 20
def F(seconds: float) -> int: return int(seconds * FPS)


# ── Fonts ────────────────────────────────────────────────────────────────────
def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        # Bold variants
        ("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ── Drawing helpers ───────────────────────────────────────────────────────────
def text_w(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def gradient_icon(size: int = 48) -> Image.Image:
    """Render the AlgoVoi gradient diamond icon (matches the e-commerce panel)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Rounded square with gradient fill
    radius = max(8, size // 4)
    # Approximate the linear gradient with horizontal stripes
    for y in range(size):
        t = y / max(1, size - 1)
        r = int(ACCENT[0] * (1 - t) + ACCENT_2[0] * t)
        g = int(ACCENT[1] * (1 - t) + ACCENT_2[1] * t)
        b = int(ACCENT[2] * (1 - t) + ACCENT_2[2] * t)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))
    # Round-clip the corners
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size, size), radius=radius, fill=255)
    img.putalpha(mask)
    # Diamond glyph
    glyph = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glyph)
    cx, cy = size // 2, size // 2
    arm = max(8, size // 3)
    gd.polygon(
        [(cx, cy - arm), (cx + arm, cy), (cx, cy + arm), (cx - arm, cy)],
        fill=(255, 255, 255, 230),
    )
    img = Image.alpha_composite(img, glyph)
    return img


def make_canvas() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    return img


def draw_brand_header(draw: ImageDraw.ImageDraw, img: Image.Image, y_offset: int = 28) -> int:
    """Place icon + 'AlgoVoi' wordmark top-left.  Returns the y after the header."""
    icon = gradient_icon(40)
    img.paste(icon, (32, y_offset), icon)
    f = load_font(20, bold=True)
    draw.text((84, y_offset + 8), "AlgoVoi", font=f, fill=TEXT_BRIGHT)
    return y_offset + 40 + 16


def paste_centered(canvas: Image.Image, image: Image.Image, *, top: int) -> tuple[int, int]:
    """Paste `image` onto `canvas` centred horizontally at `top` offset.
    Returns the bounding box (x, y_bottom)."""
    iw, ih = image.size
    # If image is too wide, scale down
    max_w = W - 80
    if iw > max_w:
        scale = max_w / iw
        image = image.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)
        iw, ih = image.size
    x = (W - iw) // 2
    canvas.paste(image, (x, top), image if image.mode == "RGBA" else None)
    return x, top + ih


# ── Scenes ────────────────────────────────────────────────────────────────────
def scene_title() -> Image.Image:
    """Scene 1 — AlgoVoi title card."""
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    # Centred icon
    icon = gradient_icon(96)
    img.paste(icon, ((W - 96) // 2, 130), icon)
    # Title
    f_title = load_font(54, bold=True)
    f_sub   = load_font(22)
    title = "Pay with Crypto"
    draw.text(((W - text_w(draw, title, f_title)) // 2, 250), title, font=f_title, fill=TEXT_BRIGHT)
    sub = "USDC / aUSDC / USDCe  -  7 chains  -  one design"
    draw.text(((W - text_w(draw, sub, f_sub)) // 2, 322), sub, font=f_sub, fill=TEXT_DIM)
    # Wordmark above
    f_brand = load_font(18, bold=True)
    brand_text = "AlgoVoi"
    bx = (W - text_w(draw, brand_text, f_brand)) // 2
    draw.text((bx, 100), brand_text, font=f_brand, fill=BRAND)
    # Footer URL
    f_foot = load_font(14)
    foot = "github.com/chopmob-cloud/AlgoVoi-Platform-Adapters"
    draw.text(((W - text_w(draw, foot, f_foot)) // 2, H - 60), foot, font=f_foot, fill=TEXT_MUTED)
    return img


def scene_panel(capture_name: str, headline: str, sub: str) -> Image.Image:
    """A scene featuring the canonical panel + an annotation."""
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    draw_brand_header(draw, img)
    # Headline / sub
    f_head = load_font(28, bold=True)
    f_sub  = load_font(15)
    draw.text((32, 100), headline, font=f_head, fill=TEXT_BRIGHT)
    draw.text((32, 140), sub, font=f_sub, fill=TEXT_DIM)
    # Panel image
    panel = Image.open(os.path.join(CAPTURES, capture_name)).convert("RGB")
    pw, ph = panel.size
    # Panel screenshots from playwright at 2x DPR — scale down for canvas fit
    target_w = 460
    scale = target_w / pw
    panel = panel.resize((target_w, int(ph * scale)), Image.LANCZOS)
    pw, ph = panel.size
    px = (W - pw) // 2
    py = 195
    img.paste(panel, (px, py))
    return img


def scene_widget() -> Image.Image:
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    draw_brand_header(draw, img)
    f_head = load_font(28, bold=True)
    f_sub  = load_font(15)
    draw.text((32, 100), "Embeddable on any site", font=f_head, fill=TEXT_BRIGHT)
    draw.text((32, 140),
              "<script src='widget.algovoi.co.uk/widget.js'></script>  + one HTML element.  No backend.",
              font=f_sub, fill=TEXT_DIM)
    widget = Image.open(os.path.join(CAPTURES, "widget_default.png")).convert("RGB")
    ww, wh = widget.size
    target_w = 480
    scale = target_w / ww
    widget = widget.resize((target_w, int(wh * scale)), Image.LANCZOS)
    img.paste(widget, ((W - target_w) // 2, 185))
    return img


def scene_end() -> Image.Image:
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    icon = gradient_icon(72)
    img.paste(icon, ((W - 72) // 2, 110), icon)
    f_brand = load_font(16, bold=True)
    draw.text(((W - text_w(draw, "AlgoVoi", f_brand)) // 2, 200), "AlgoVoi", font=f_brand, fill=BRAND)
    f_h = load_font(40, bold=True)
    line1 = "Same panel."
    line2 = "Every platform."
    draw.text(((W - text_w(draw, line1, f_h)) // 2, 240), line1, font=f_h, fill=TEXT_BRIGHT)
    draw.text(((W - text_w(draw, line2, f_h)) // 2, 290), line2, font=f_h, fill=TEXT_BRIGHT)
    # Platform badges
    f_p = load_font(14)
    plats = ["Shopify", "WooCommerce", "PrestaShop", "OpenCart", "Shopware", "Magento 2", "x402 widget"]
    line = "  |  ".join(plats)
    draw.text(((W - text_w(draw, line, f_p)) // 2, 380), line, font=f_p, fill=TEXT_DIM)
    f_url = load_font(15, bold=True)
    url = "github.com/chopmob-cloud/AlgoVoi-Platform-Adapters"
    draw.text(((W - text_w(draw, url, f_url)) // 2, 440), url, font=f_url, fill=BRAND)
    return img


# ── Frame composition ────────────────────────────────────────────────────────
def crossfade(a: Image.Image, b: Image.Image, frames: int) -> list[Image.Image]:
    """Return `frames` blended frames from a -> b."""
    out = []
    for i in range(frames):
        t = (i + 1) / (frames + 1)
        out.append(Image.blend(a, b, t))
    return out


def hold(scene: Image.Image, frames: int) -> list[Image.Image]:
    return [scene.copy() for _ in range(frames)]


def main():
    print("Compositing scenes...")
    s1 = scene_title()
    s2 = scene_panel("panel_default.png", "Customer reaches checkout",
                     "The same AlgoVoi panel renders on every platform.")
    s3 = scene_panel("panel_voi.png",     "Switch network anytime",
                     "VOI selected - aUSDC for low-fee Algorand-VM payments.")
    s4 = scene_panel("panel_hedera.png",  "All 7 chains, one dropdown",
                     "Hedera, Stellar, Base, Solana, Tempo - same UX.")
    s5 = scene_panel("panel_solana.png",  "Pick. Pay. Done.",
                     "Live colour indicator, native form submission, no JS gymnastics.")
    s6 = scene_widget()
    s7 = scene_end()

    print("Building frames...")
    frames: list[Image.Image] = []
    XF = F(0.4)         # crossfade duration in frames

    frames += hold(s1, F(2.0))
    frames += crossfade(s1, s2, XF)
    frames += hold(s2, F(2.0))
    frames += crossfade(s2, s3, XF)
    frames += hold(s3, F(1.4))
    frames += crossfade(s3, s4, XF)
    frames += hold(s4, F(1.4))
    frames += crossfade(s4, s5, XF)
    frames += hold(s5, F(1.4))
    frames += crossfade(s5, s6, XF)
    frames += hold(s6, F(2.2))
    frames += crossfade(s6, s7, XF)
    frames += hold(s7, F(3.0))

    print(f"  total frames: {len(frames)}  (~{len(frames) / FPS:.1f}s @ {FPS}fps)")

    # Quantise to GIF palette in one batch
    print("Quantising + writing GIF...")
    quantised = [f.quantize(colors=256, method=Image.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG) for f in frames]
    quantised[0].save(
        OUTPUT,
        save_all=True,
        append_images=quantised[1:],
        duration=int(1000 / FPS),
        loop=0,
        optimize=True,
    )
    size_kb = os.path.getsize(OUTPUT) // 1024
    print(f"\nWritten: {OUTPUT}  ({size_kb} KB)")


if __name__ == "__main__":
    main()
