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
ASSETS   = os.path.join(ROOT, "assets")
LOGO     = os.path.join(ASSETS, "algovoi_logo.png")   # canonical AV+wordmark
OUTPUT_GIF = os.path.join(ROOT, "algovoi_howto.gif")
OUTPUT_MP4 = os.path.join(ROOT, "algovoi_howto.mp4")

# ── Theme (matches canonical AlgoVoi panel palette) ──────────────────────────
W, H = 1800, 1200    # 2x previous; sharp on retina + scales down crisply
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

FPS = 30
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


def load_logo(target_height: int) -> Image.Image:
    """Load the canonical AV-mark + wordmark logo, scaled to target height.

    The asset is the same logo used in the existing x402-widget and
    ai-adapters demo GIFs (1080x360 RGB, gradient AV mark on dark).
    Falls back to a tiny synthesized rounded-square if the file is missing.
    """
    if os.path.exists(LOGO):
        im = Image.open(LOGO).convert("RGBA")
        ratio = target_height / im.height
        return im.resize((int(im.width * ratio), target_height), Image.LANCZOS)
    # Fallback (should never trigger if assets/ is present)
    fallback = Image.new("RGBA", (target_height * 3, target_height), BG + (255,))
    return fallback


def load_mark_only(target_height: int) -> Image.Image:
    """Crop just the AV-mark (left ~28%) from the wordmark logo, square."""
    if not os.path.exists(LOGO):
        return load_logo(target_height)
    im = Image.open(LOGO).convert("RGBA")
    # The mark is the leftmost ~28% of the logo width on a square area
    side = im.height
    mark = im.crop((0, 0, side, side))
    return mark.resize((target_height, target_height), Image.LANCZOS)


def make_canvas() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    return img


def draw_brand_header(draw: ImageDraw.ImageDraw, img: Image.Image, y_offset: int = 56) -> int:
    """Place the canonical AlgoVoi wordmark logo top-left.  Returns y_after."""
    logo = load_logo(target_height=88)
    img.paste(logo, (56, y_offset), logo)
    return y_offset + logo.height + 32


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
    """Scene 1 — AlgoVoi title card.  Uses the canonical AV+wordmark logo."""
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    # Centred wordmark logo
    logo = load_logo(target_height=280)
    img.paste(logo, ((W - logo.width) // 2, 220), logo)
    # Tagline
    f_title = load_font(96, bold=True)
    f_sub   = load_font(40)
    title = "Pay with Crypto"
    draw.text(((W - text_w(draw, title, f_title)) // 2, 580), title, font=f_title, fill=TEXT_BRIGHT)
    sub = "USDC / aUSDC / USDCe  -  7 chains  -  one design"
    draw.text(((W - text_w(draw, sub, f_sub)) // 2, 716), sub, font=f_sub, fill=TEXT_DIM)
    # Footer URL
    f_foot = load_font(28)
    foot = "github.com/chopmob-cloud/AlgoVoi-Platform-Adapters"
    draw.text(((W - text_w(draw, foot, f_foot)) // 2, H - 120), foot, font=f_foot, fill=TEXT_MUTED)
    return img


def scene_panel(capture_name: str, headline: str, sub: str) -> Image.Image:
    """A scene featuring the canonical panel + an annotation."""
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    draw_brand_header(draw, img)
    # Headline / sub
    f_head = load_font(56, bold=True)
    f_sub  = load_font(28)
    draw.text((64, 200), headline, font=f_head, fill=TEXT_BRIGHT)
    draw.text((64, 280), sub, font=f_sub, fill=TEXT_DIM)
    # Panel image
    panel = Image.open(os.path.join(CAPTURES, capture_name)).convert("RGB")
    pw, ph = panel.size
    # Panel screenshots from playwright at 3x DPR — scale to fit canvas
    target_w = 920
    scale = target_w / pw
    panel = panel.resize((target_w, int(ph * scale)), Image.LANCZOS)
    pw, ph = panel.size
    px = (W - pw) // 2
    py = 390
    img.paste(panel, (px, py))
    return img


def scene_widget() -> Image.Image:
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    draw_brand_header(draw, img)
    f_head = load_font(56, bold=True)
    f_sub  = load_font(26)
    draw.text((64, 200), "Embeddable on any site", font=f_head, fill=TEXT_BRIGHT)
    draw.text((64, 280),
              "<script src='widget.algovoi.co.uk/widget.js'></script>  +  one HTML element.  No backend.",
              font=f_sub, fill=TEXT_DIM)
    widget = Image.open(os.path.join(CAPTURES, "widget_default.png")).convert("RGB")
    ww, wh = widget.size
    target_w = 960
    scale = target_w / ww
    widget = widget.resize((target_w, int(wh * scale)), Image.LANCZOS)
    img.paste(widget, ((W - target_w) // 2, 380))
    return img


def scene_end() -> Image.Image:
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    # Canonical wordmark logo, centred
    logo = load_logo(target_height=220)
    img.paste(logo, ((W - logo.width) // 2, 180), logo)
    # Tagline
    f_h = load_font(76, bold=True)
    line1 = "Same panel."
    line2 = "Every platform."
    draw.text(((W - text_w(draw, line1, f_h)) // 2, 480), line1, font=f_h, fill=TEXT_BRIGHT)
    draw.text(((W - text_w(draw, line2, f_h)) // 2, 580), line2, font=f_h, fill=TEXT_BRIGHT)
    # Platform list
    f_p = load_font(28)
    plats = ["Shopify", "WooCommerce", "PrestaShop", "OpenCart", "Shopware", "Magento 2", "x402 widget"]
    line = "   |   ".join(plats)
    draw.text(((W - text_w(draw, line, f_p)) // 2, 760), line, font=f_p, fill=TEXT_DIM)
    f_url = load_font(30, bold=True)
    url = "github.com/chopmob-cloud/AlgoVoi-Platform-Adapters"
    draw.text(((W - text_w(draw, url, f_url)) // 2, 880), url, font=f_url, fill=BRAND)
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

    # ── MP4 export (H.264) ───────────────────────────────────────────────
    # Much smaller filesize and far higher quality than the GIF for the
    # same canvas — preferred for social media and embedded README hero.
    print("Encoding MP4 (H.264 via imageio_ffmpeg)...")
    try:
        import imageio.v2 as imageio   # type: ignore
        import numpy as np             # type: ignore
        writer = imageio.get_writer(
            OUTPUT_MP4,
            fps=FPS,
            codec="libx264",
            quality=8,                 # 1-10 (low-high), 8 = visually lossless
            macro_block_size=1,         # allow non-multiple-of-16 dimensions
            pixelformat="yuv420p",      # max compatibility
            ffmpeg_params=["-movflags", "+faststart"],
        )
        for f in frames:
            writer.append_data(np.array(f))
        writer.close()
        mp4_kb = os.path.getsize(OUTPUT_MP4) // 1024
        print(f"  MP4: {OUTPUT_MP4}  ({mp4_kb} KB)")
    except Exception as exc:
        print(f"  MP4 skipped: {exc}")

    # ── GIF export (downscale for size — full HQ stays in the MP4) ───────
    # Animated GIFs blow up exponentially with resolution.  Render the GIF
    # at half-canvas (900x600) so it stays embeddable on GitHub READMEs.
    print("Encoding GIF (downsampled to 900x600 for GitHub-friendly size)...")
    gif_frames = [f.resize((W // 2, H // 2), Image.LANCZOS) for f in frames]
    quantised = [
        f.quantize(colors=256, method=Image.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
        for f in gif_frames
    ]
    quantised[0].save(
        OUTPUT_GIF,
        save_all=True,
        append_images=quantised[1:],
        duration=int(1000 / FPS),
        loop=0,
        optimize=True,
    )
    gif_kb = os.path.getsize(OUTPUT_GIF) // 1024
    print(f"  GIF: {OUTPUT_GIF}  ({gif_kb} KB)")


if __name__ == "__main__":
    main()
