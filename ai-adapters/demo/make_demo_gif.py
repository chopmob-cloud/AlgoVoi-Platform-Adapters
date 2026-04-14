"""
AlgoVoi AI Adapters — Demo GIF Generator
=========================================
Generates terminal-style animated GIFs showing the payment-gated AI API flow.

Produces three GIFs (one per adapter):
    algovoi_claude_demo.gif
    algovoi_openai_demo.gif
    algovoi_gemini_demo.gif

Requirements:
    pip install Pillow    (usually already installed)

Usage:
    python make_demo_gif.py
"""

from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Theme ─────────────────────────────────────────────────────────────────────

BG       = (13,  17,  23)   # GitHub dark background
TEXT     = (201, 209, 217)  # normal text
PROMPT   = (88,  166, 255)  # blue prompt $
CMD      = (201, 209, 217)  # command text
KEY      = (255, 123, 114)  # header key (red)
VAL      = (121, 192,  57)  # header value (green)
STATUS2  = (255, 123, 114)  # 402 status
STATUS0  = (121, 192,  57)  # 200 status
JSON_KEY = (121, 192,  57)  # JSON key
JSON_VAL = (173, 216, 230)  # JSON string value
MUTED    = (110, 118, 135)  # muted / comment
TITLE_FG = (255, 255, 255)
TITLE_BG = (36,  41,  46)
CURSOR   = (88,  166, 255)
BADGE_BLUE   = (31,  111, 235)
BADGE_GREEN  = (35,  134,  54)

# Annotation overlay colours
ANN_BG      = (22,  27,  34)   # overlay panel bg (matches GitHub dark)
ANN_BORDER  = (48,  54,  61)   # panel border
ANN_TITLE   = (88,  166, 255)  # annotation heading (blue)
ANN_BODY    = (201, 209, 217)  # annotation body text
ANN_ICON_BG = (31,  111, 235)  # icon circle

# ── Dimensions ────────────────────────────────────────────────────────────────

W, H   = 900, 520
LPAD   = 28       # left text padding
LINE_H = 22       # line height
TOP    = 72       # first line y (below title bar)

# ── Font ──────────────────────────────────────────────────────────────────────

def _load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\consola.ttf",
        r"C:\Windows\Fonts\cour.ttf",
        r"C:\Windows\Fonts\lucon.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

FONT      = _load_font(14)
FONT_BOLD = _load_font(15)
FONT_SM   = _load_font(12)
FONT_LG   = _load_font(18)
FONT_ANN  = _load_font(13)
FONT_ANN_H = _load_font(14)


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _new_frame() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    return img, d


def _title_bar(d: ImageDraw.ImageDraw, adapter: str, model: str) -> None:
    d.rectangle([0, 0, W, 46], fill=TITLE_BG)
    for x, c in [(18, (255, 95, 86)), (38, (255, 189, 46)), (58, (39, 201, 63))]:
        d.ellipse([x - 6, 17, x + 6, 29], fill=c)
    title = f"AlgoVoi — {adapter} Payment Gate"
    d.text((W // 2, 23), title, font=FONT_BOLD, fill=TITLE_FG, anchor="mm")
    d.rectangle([0, H - 28, W, H], fill=TITLE_BG)
    d.text((LPAD, H - 20), f"model: {model}", font=FONT_SM, fill=MUTED, anchor="lm")
    d.text((W - LPAD, H - 20), "github.com/chopmob-cloud/AlgoVoi-Platform-Adapters",
           font=FONT_SM, fill=MUTED, anchor="rm")


def _prompt(d: ImageDraw.ImageDraw, y: int, cmd: str) -> None:
    d.text((LPAD, y), "$", font=FONT_BOLD, fill=PROMPT)
    d.text((LPAD + 16, y), cmd, font=FONT, fill=CMD)


def _out(d: ImageDraw.ImageDraw, y: int, text: str, color: tuple = TEXT) -> None:
    d.text((LPAD + 4, y), text, font=FONT, fill=color)


def _divider(d: ImageDraw.ImageDraw, y: int, label: str) -> None:
    d.line([(LPAD, y + 9), (LPAD + 30, y + 9)], fill=MUTED, width=1)
    d.text((LPAD + 36, y), label, font=FONT_SM, fill=MUTED)
    d.line([(LPAD + 36 + len(label) * 7 + 6, y + 9), (W - LPAD, y + 9)],
           fill=MUTED, width=1)


def _badge(d: ImageDraw.ImageDraw, x: int, y: int, text: str, color: tuple) -> int:
    tw = len(text) * 8 + 12
    d.rounded_rectangle([x, y - 2, x + tw, y + 16], radius=4, fill=color)
    d.text((x + 6, y + 7), text, font=FONT_SM, fill=(255, 255, 255), anchor="lm")
    return x + tw + 8


def _cursor(d: ImageDraw.ImageDraw, x: int, y: int) -> None:
    d.rectangle([x, y + 2, x + 9, y + 16], fill=CURSOR)


# ── Annotation overlay ────────────────────────────────────────────────────────

def _annotate(img: Image.Image, heading: str, lines: list[str],
              alpha: float = 1.0) -> Image.Image:
    """
    Draw a callout panel over the bottom of the frame.

    heading  — bold blue title line
    lines    — body text lines (plain white)
    alpha    — 0.0 (invisible) → 1.0 (fully opaque), for fade-in effect
    """
    if alpha <= 0:
        return img

    overlay = img.copy()
    d = ImageDraw.Draw(overlay)

    pad    = 16
    lh     = 20
    panel_h = pad * 2 + lh + len(lines) * lh + 4
    y0     = H - 28 - panel_h - 8   # sit just above bottom status bar
    y1     = H - 28 - 8
    x0, x1 = LPAD - 4, W - LPAD + 4

    # Panel background + border
    d.rounded_rectangle([x0, y0, x1, y1], radius=6, fill=ANN_BG)
    d.rounded_rectangle([x0, y0, x1, y1], radius=6, outline=ANN_BORDER, width=1)

    # Icon circle
    ix = x0 + pad
    iy = y0 + pad + lh // 2
    d.ellipse([ix - 9, iy - 9, ix + 9, iy + 9], fill=ANN_ICON_BG)
    d.text((ix, iy), "i", font=FONT_BOLD, fill=(255, 255, 255), anchor="mm")

    # Heading
    tx = ix + 18
    d.text((tx, y0 + pad), heading, font=FONT_ANN_H, fill=ANN_TITLE)

    # Body lines
    for i, line in enumerate(lines):
        d.text((tx, y0 + pad + lh + 4 + i * lh), line, font=FONT_ANN, fill=ANN_BODY)

    # Blend with original at requested alpha
    return Image.blend(img, overlay, alpha)


def _annotation_frames(base_img: Image.Image, heading: str,
                        lines: list[str], hold_frames: int = 60) -> list[Image.Image]:
    """
    Return a sequence of frames: fade-in annotation → hold → fade-out.
    base_img is kept unchanged; the overlay is composited on top.
    hold_frames controls how long the annotation is fully visible (50ms each).
    """
    fade_steps = 8
    frames: list[Image.Image] = []

    # Fade in
    for i in range(fade_steps):
        frames.append(_annotate(base_img.copy(), heading, lines,
                                alpha=(i + 1) / fade_steps))
    # Hold
    for _ in range(hold_frames):
        frames.append(_annotate(base_img.copy(), heading, lines, alpha=1.0))
    # Fade out
    for i in range(fade_steps):
        frames.append(_annotate(base_img.copy(), heading, lines,
                                alpha=1.0 - (i + 1) / fade_steps))

    return frames


# ── Scenes ────────────────────────────────────────────────────────────────────

def _make_logo(width: int = 420, height: int = 110) -> Image.Image:
    """
    Render the AlgoVoi logo.

    Looks for algovoi_logo.png in the same directory first.
    Falls back to a Pillow-drawn version matching the brand logo:
      [AV gradient icon]  AlgoVoi
    """
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "algovoi_logo.png")
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        # Fit to requested size preserving aspect ratio
        logo.thumbnail((width, height), Image.LANCZOS)
        # Start with a canvas filled with the GIF background colour
        canvas = Image.new("RGBA", (width, height), (*BG, 255))
        x = (width  - logo.width)  // 2
        y = (height - logo.height) // 2
        # If the logo has real transparency, use it; otherwise key out the
        # background using the top-left corner pixel as the background colour
        r, g, b, a = logo.split()
        if a.getextrema() == (255, 255):
            import struct
            corner_r, corner_g, corner_b, _ = logo.getpixel((0, 0))
            # Build alpha mask: pixels far from corner colour become opaque
            import PIL.ImageChops as chops
            ref = Image.new("RGBA", logo.size, (corner_r, corner_g, corner_b, 255))
            diff = chops.difference(logo, ref).convert("L")
            # Stretch contrast so near-background → transparent, logo → opaque
            diff = diff.point(lambda v: min(255, v * 8))
            logo.putalpha(diff)
        canvas.paste(logo, (x, y), logo)
        return canvas.convert("RGB")

    # ── Drawn fallback ────────────────────────────────────────────────────────
    canvas = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(canvas)

    icon_size = height - 10
    ix, iy = 5, 5

    # Gradient rounded square: cyan top-left → purple bottom-right
    grad = Image.new("RGB", (icon_size, icon_size))
    gd   = ImageDraw.Draw(grad)
    cyan   = (0,   212, 255)
    purple = (180,  80, 255)
    for px in range(icon_size):
        for py in range(icon_size):
            t = (px + py) / (icon_size * 2 - 2)
            r = int(cyan[0] + (purple[0] - cyan[0]) * t)
            g = int(cyan[1] + (purple[1] - cyan[1]) * t)
            b = int(cyan[2] + (purple[2] - cyan[2]) * t)
            gd.point((px, py), fill=(r, g, b))

    # Rounded mask
    mask = Image.new("L", (icon_size, icon_size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, icon_size - 1, icon_size - 1], radius=icon_size // 5, fill=255
    )
    bg_patch = Image.new("RGB", (icon_size, icon_size), BG)
    icon = Image.composite(grad, bg_patch, mask)
    canvas.paste(icon, (ix, iy))

    # "AV" text inside icon
    font_av = _load_font(icon_size // 3)
    av_x = ix + icon_size // 2
    av_y = iy + icon_size // 2
    d.text((av_x, av_y), "AV", font=font_av, fill=(10, 10, 10), anchor="mm")

    # "AlgoVoi" text to the right
    font_brand = _load_font(icon_size // 2)
    tx = ix + icon_size + 18
    ty = iy + icon_size // 2
    d.text((tx, ty), "AlgoVoi", font=font_brand, fill=(255, 255, 255), anchor="lm")

    return canvas


def scene_title(adapter: str, model: str, protocol: str) -> list[Image.Image]:
    """Opening title card — 2 s, using the AlgoVoi logo."""
    logo = _make_logo(width=460, height=120)

    frames = []
    for _ in range(40):
        img, d = _new_frame()

        # Centre logo
        lx = (W - logo.width)  // 2
        ly = H // 2 - logo.height // 2 - 40
        img.paste(logo, (lx, ly))

        # Subtitle
        d.text((W // 2, ly + logo.height + 18), "Payment-Gated AI APIs",
               font=FONT_LG, fill=TEXT, anchor="mm")

        # Badges
        bx = W // 2 - 100
        bx = _badge(d, bx, ly + logo.height + 44, adapter,  BADGE_BLUE)
        bx = _badge(d, bx, ly + logo.height + 44, protocol, BADGE_GREEN)
        d.text((W // 2, ly + logo.height + 82), model, font=FONT_SM, fill=MUTED, anchor="mm")

        frames.append(img)
    return frames


def scene_health(adapter: str, model: str) -> list[Image.Image]:
    """Health check — curl /health → {status: ok} + annotation."""

    def base_frame(show_resp: bool, cursor: bool = False) -> Image.Image:
        img, d = _new_frame()
        _title_bar(d, adapter, model)
        y = TOP
        _divider(d, y, "1 · health check")
        y += LINE_H + 4
        _prompt(d, y, "curl http://localhost:5000/health")
        if cursor:
            _cursor(d, LPAD + 16 + 34 * 8, y)
        y += LINE_H
        if show_resp:
            _out(d, y, '{"status": "ok"}', JSON_KEY)
        return img

    frames = []
    for i in range(8):
        frames.append(base_frame(False, cursor=(i % 2 == 0)))
    # Show response briefly, then annotate
    resp_img = base_frame(True)
    for _ in range(10):
        frames.append(resp_img)
    frames += _annotation_frames(
        resp_img,
        heading="Server is running",
        lines=[
            "A simple health check confirms the payment-gated server",
            "is live. No payment needed for /health.",
        ],
        hold_frames=40,
    )
    return frames


def scene_402(adapter: str, model: str, protocol: str,
              payout: str) -> list[Image.Image]:
    """Request without payment → 402 + annotation."""
    cmd  = "curl -s -i -X POST http://localhost:5000/ai/chat \\"
    cmd2 = '  -H "Content-Type: application/json" \\'
    cmd3 = "  -d '{\"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}]}'"

    PROTOCOL_NOTES = {
        "mpp":  ("MPP — IETF Payment Auth (WWW-Authenticate)",
                 ["The server returns a 402 with a WWW-Authenticate: Payment header.",
                  "It tells the client which chain to pay on, how much (0.01 USDC),",
                  "and which address to send to. No payment = no AI response."]),
        "x402": ("x402 — HTTP Payment Protocol",
                 ["The server returns a 402 with an X-PAYMENT-REQUIRED header",
                  "containing a base64-encoded JSON payload with chain, amount,",
                  "and recipient. The client pays on-chain then retries."]),
        "ap2":  ("AP2 — Crypto-Algo Cart Mandate",
                 ["The server returns a 402 with an X-AP2-Cart-Mandate header.",
                  "The mandate encodes the payment terms as a signed JSON object.",
                  "The client fulfils the mandate then includes proof in the next request."]),
    }
    heading, ann_lines = PROTOCOL_NOTES.get(protocol, ("402 Payment Required", []))

    def base_frame(lines: int, cursor: bool = False) -> Image.Image:
        img, d = _new_frame()
        _title_bar(d, adapter, model)
        y = TOP
        _divider(d, y, "2 · request without payment")
        y += LINE_H + 4
        _prompt(d, y, cmd)
        y += LINE_H
        _out(d, y, cmd2, MUTED)
        y += LINE_H
        _out(d, y, cmd3, MUTED)
        if cursor:
            _cursor(d, LPAD + 4 + len(cmd3) * 8, y)
        y += LINE_H + 6
        if lines >= 1:
            _out(d, y, "HTTP/1.1 402 Payment Required", STATUS2)
        y += LINE_H
        if lines >= 2:
            if protocol == "mpp":
                _out(d, y, "WWW-Authenticate:", KEY)
                _out(d, y + LINE_H,
                     '  Payment realm="API Access", id="ch_abc123...",', VAL)
                _out(d, y + LINE_H * 2,
                     '  method="algorand-mainnet", amount="10000",', VAL)
                _out(d, y + LINE_H * 3,
                     f'  asset="31566704", payto="{payout[:24]}..."', VAL)
            elif protocol == "x402":
                _out(d, y, "X-PAYMENT-REQUIRED:", KEY)
                _out(d, y + LINE_H,
                     "  eyJuZXR3b3JrIjoiYWxnb3JhbmQtbWFpbm5ldCIsICJhbW91bnQiOiAiMTAwMDAifQ==",
                     VAL)
            elif protocol == "ap2":
                _out(d, y, "X-AP2-Cart-Mandate:", KEY)
                _out(d, y + LINE_H,
                     "  eyJ2IjogMSwgIm1lcmNoYW50IjogInlvdXItdGVuYW50LXV1aWQiLCAiYW1vdW50IjogMTAwMDB9",
                     VAL)
        return img

    frames = []
    for i in range(10):
        frames.append(base_frame(0, cursor=(i % 2 == 0)))
    for _ in range(10):
        frames.append(base_frame(1))
    # Show full 402 briefly then annotate
    full_402 = base_frame(2)
    for _ in range(10):
        frames.append(full_402)
    frames += _annotation_frames(full_402, heading, ann_lines, hold_frames=60)
    return frames


def scene_200(adapter: str, model: str, ai_reply: str) -> list[Image.Image]:
    """Request with proof → 200 + AI response + two annotations."""
    proof_cmd  = 'PROOF=$(python3 -c "import base64,json; print(base64.b64encode('
    proof_cmd2 = "  json.dumps({'network':'algorand-mainnet','payload':{'txId':'TX123...'}})"
    proof_cmd3 = '  .encode()).decode())")'
    curl_cmd   = "curl -s -X POST http://localhost:5000/ai/chat \\"
    curl_cmd2  = '  -H "Content-Type: application/json" \\'
    curl_cmd3  = '  -H "Authorization: Payment $PROOF" \\'
    curl_cmd4  = "  -d '{\"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}]}'"

    def base_frame(phase: int, n_reply_chars: int = 0) -> Image.Image:
        img, d = _new_frame()
        _title_bar(d, adapter, model)
        y = TOP
        _divider(d, y, "3 · request with payment proof")
        y += LINE_H + 4

        if phase >= 1:
            _prompt(d, y, proof_cmd)
            y += LINE_H
            _out(d, y, proof_cmd2, MUTED)
            y += LINE_H
            _out(d, y, proof_cmd3, MUTED)
            y += LINE_H
            d.text((LPAD, y), "$", font=FONT_BOLD, fill=PROMPT)
            _out(d, y, "echo $PROOF", CMD)
            y += LINE_H
            if phase >= 2:
                _out(d, y, "eyJuZXR3b3JrIjoiYWxnb3JhbmQtbWFpbm5ldCIsIn...", MUTED)
                y += LINE_H

        if phase >= 3:
            _prompt(d, y, curl_cmd)
            y += LINE_H
            _out(d, y, curl_cmd2, MUTED)
            y += LINE_H
            _out(d, y, curl_cmd3, MUTED)
            y += LINE_H
            _out(d, y, curl_cmd4, MUTED)
            y += LINE_H

        if phase >= 4:
            _out(d, y, "HTTP/1.1 200 OK", STATUS0)
            y += LINE_H

        if phase >= 5:
            reply_so_far = ai_reply[:n_reply_chars]
            display = '{"content": "' + reply_so_far
            if len(display) > 72:
                _out(d, y, display[:72], JSON_KEY)
                suffix = '"}' if n_reply_chars >= len(ai_reply) else "▊"
                _out(d, y + LINE_H, "  " + display[72:] + suffix, JSON_VAL)
            else:
                suffix = '"}' if n_reply_chars >= len(ai_reply) else "▊"
                _out(d, y, display + suffix, JSON_KEY)

        return img

    frames = []
    for _ in range(12):
        frames.append(base_frame(0))
    for _ in range(10):
        frames.append(base_frame(1))

    # Annotate: what the proof is
    proof_img = base_frame(2)
    for _ in range(6):
        frames.append(proof_img)
    frames += _annotation_frames(
        proof_img,
        heading="Payment proof = base64-encoded TX ID",
        lines=[
            "After paying on-chain (Algorand / VOI / Hedera / Stellar),",
            "the client base64-encodes the network + transaction ID",
            "and includes it in the Authorization: Payment header.",
        ],
        hold_frames=55,
    )

    for _ in range(10):
        frames.append(base_frame(3))
    for _ in range(8):
        frames.append(base_frame(4))

    # Streaming reply effect
    reply_len = len(ai_reply)
    step = max(1, reply_len // 30)
    for i in range(0, reply_len + 1, step):
        frames.append(base_frame(5, min(i, reply_len)))

    # Annotate: the 200 response
    done_img = base_frame(5, reply_len)
    for _ in range(10):
        frames.append(done_img)
    frames += _annotation_frames(
        done_img,
        heading="Payment verified — AI response returned",
        lines=[
            "AlgoVoi verified the transaction on-chain in real time.",
            "The adapter called the AI API and returned the response.",
            f"Cost: 0.01 USDC per call. Works across all 4 supported chains.",
        ],
        hold_frames=60,
    )
    return frames


# ── Adapter configs ───────────────────────────────────────────────────────────

ADAPTERS = [
    dict(
        name     = "Claude",
        model    = "claude-sonnet-4-5",
        protocol = "mpp",
        payout   = "YOUR_ALGORAND_ADDRESS",
        reply    = "Hello! I'm Claude, an AI assistant made by Anthropic. How can I help you today?",
        out      = "algovoi_claude_demo.gif",
    ),
    dict(
        name     = "OpenAI",
        model    = "gpt-4o",
        protocol = "x402",
        payout   = "YOUR_ALGORAND_ADDRESS",
        reply    = "Hello! I'm GPT-4o, powered by OpenAI. What can I help you with today?",
        out      = "algovoi_openai_demo.gif",
    ),
    dict(
        name     = "Gemini",
        model    = "gemini-2.0-flash",
        protocol = "ap2",
        payout   = "YOUR_ALGORAND_ADDRESS",
        reply    = "Hello! I'm Gemini, Google's AI assistant. How can I assist you today?",
        out      = "algovoi_gemini_demo.gif",
    ),
]


# ── GIF writer ────────────────────────────────────────────────────────────────

def _save_gif(frames: list[Image.Image], path: str, frame_ms: int = 50) -> None:
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=frame_ms,
        optimize=True,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def make_gif(cfg: dict, out_dir: str = ".") -> None:
    name     = cfg["name"]
    model    = cfg["model"]
    protocol = cfg["protocol"]
    payout   = cfg["payout"]
    reply    = cfg["reply"]
    out_path = os.path.join(out_dir, cfg["out"])

    print(f"  Generating {cfg['out']} …", end=" ", flush=True)

    frames: list[Image.Image] = []
    frames += scene_title(name, model, protocol)
    frames += scene_health(name, model)
    frames += scene_402(name, model, protocol, payout)
    frames += scene_200(name, model, reply)

    _save_gif(frames, out_path, frame_ms=50)
    size_kb = os.path.getsize(out_path) // 1024
    print(f"done  ({len(frames)} frames, {size_kb} KB)")


if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))
    print("AlgoVoi Demo GIF Generator")
    print("=" * 40)
    for cfg in ADAPTERS:
        make_gif(cfg, out_dir)
    print()
    print("Output files:")
    for cfg in ADAPTERS:
        p = os.path.join(out_dir, cfg["out"])
        print(f"  {p}")
    print()
    print("Embed in README:")
    for cfg in ADAPTERS:
        print(f"  ![{cfg['name']} demo](ai-adapters/demo/{cfg['out']})")
