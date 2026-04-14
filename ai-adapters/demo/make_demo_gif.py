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
from PIL import Image, ImageDraw, ImageFont

# ── Theme ─────────────────────────────────────────────────────────────────────

BG       = (13,  17,  23)   # GitHub dark background
DIM      = (33,  38,  45)   # secondary background / prompt line
TEXT     = (201, 209, 217)  # normal text
PROMPT   = (88,  166, 255)  # blue prompt $
CMD      = (201, 209, 217)  # command text
KEY      = (255, 123, 114)  # header key (red)
VAL      = (121, 192,  57)  # header value (green)
STATUS2  = (255, 123, 114)  # 402 status
STATUS2B = (255, 180,  80)  # 402 body
STATUS0  = (121, 192,  57)  # 200 status
JSON_KEY = (121, 192,  57)  # JSON key
JSON_VAL = (173, 216, 230)  # JSON string value
MUTED    = (110, 118, 135)  # muted / comment
TITLE_FG = (255, 255, 255)
TITLE_BG = (36,  41,  46)
CURSOR   = (88,  166, 255)
BADGE_BLUE   = (31,  111, 235)
BADGE_GREEN  = (35,  134,  54)

# ── Dimensions ────────────────────────────────────────────────────────────────

W, H   = 900, 520
MARGIN = 20
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


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _new_frame() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    return img, d


def _title_bar(d: ImageDraw.ImageDraw, adapter: str, model: str) -> None:
    """Draw top title bar and bottom status bar."""
    # Top bar
    d.rectangle([0, 0, W, 46], fill=TITLE_BG)
    # Traffic lights
    for x, c in [(18, (255, 95, 86)), (38, (255, 189, 46)), (58, (39, 201, 63))]:
        d.ellipse([x - 6, 17, x + 6, 29], fill=c)
    # Title
    title = f"AlgoVoi — {adapter} Payment Gate"
    d.text((W // 2, 23), title, font=FONT_BOLD, fill=TITLE_FG, anchor="mm")
    # Bottom status bar
    d.rectangle([0, H - 28, W, H], fill=TITLE_BG)
    d.text((LPAD, H - 20), f"model: {model}", font=FONT_SM, fill=MUTED, anchor="lm")
    d.text((W - LPAD, H - 20), "github.com/chopmob-cloud/AlgoVoi-Platform-Adapters",
           font=FONT_SM, fill=MUTED, anchor="rm")


def _prompt(d: ImageDraw.ImageDraw, y: int, cmd: str) -> None:
    d.text((LPAD, y), "$", font=FONT_BOLD, fill=PROMPT)
    d.text((LPAD + 16, y), cmd, font=FONT, fill=CMD)


def _out(d: ImageDraw.ImageDraw, y: int, text: str,
         color: tuple = TEXT) -> None:
    d.text((LPAD + 4, y), text, font=FONT, fill=color)


def _divider(d: ImageDraw.ImageDraw, y: int, label: str) -> None:
    d.line([(LPAD, y + 9), (LPAD + 30, y + 9)], fill=MUTED, width=1)
    d.text((LPAD + 36, y), label, font=FONT_SM, fill=MUTED)
    d.line([(LPAD + 36 + len(label) * 7 + 6, y + 9), (W - LPAD, y + 9)],
           fill=MUTED, width=1)


def _badge(d: ImageDraw.ImageDraw, x: int, y: int,
           text: str, color: tuple) -> int:
    tw = len(text) * 8 + 12
    d.rounded_rectangle([x, y - 2, x + tw, y + 16], radius=4, fill=color)
    d.text((x + 6, y + 7), text, font=FONT_SM, fill=(255, 255, 255), anchor="lm")
    return x + tw + 8


def _cursor(d: ImageDraw.ImageDraw, x: int, y: int) -> None:
    d.rectangle([x, y + 2, x + 9, y + 16], fill=CURSOR)


# ── Scenes ────────────────────────────────────────────────────────────────────

def scene_title(adapter: str, model: str, protocol: str) -> list[Image.Image]:
    """Opening title card — 2 s."""
    frames = []
    for _ in range(40):  # 40 × 50ms = 2 s
        img, d = _new_frame()
        # Big centred title
        d.text((W // 2, H // 2 - 60), "AlgoVoi", font=_load_font(48),
               fill=(88, 166, 255), anchor="mm")
        d.text((W // 2, H // 2 - 10), "Payment-Gated AI APIs",
               font=FONT_LG, fill=TEXT, anchor="mm")
        # Badges
        bx = W // 2 - 100
        bx = _badge(d, bx, H // 2 + 20, adapter,  BADGE_BLUE)
        bx = _badge(d, bx, H // 2 + 20, protocol, BADGE_GREEN)
        d.text((W // 2, H // 2 + 70), model, font=FONT_SM, fill=MUTED, anchor="mm")
        frames.append(img)
    return frames


def scene_health(adapter: str, model: str) -> list[Image.Image]:
    """Health check — curl /health → {"status":"ok"}."""
    frames = []

    def frame(show_resp: bool, cursor: bool = False) -> Image.Image:
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

    # Typing effect (brief)
    for i in range(8):
        frames.append(frame(False, cursor=(i % 2 == 0)))
    # Show response
    for _ in range(30):
        frames.append(frame(True))
    return frames


def scene_402(adapter: str, model: str, protocol: str,
              payout: str) -> list[Image.Image]:
    """Request without payment → 402."""
    cmd = "curl -s -i -X POST http://localhost:5000/ai/chat \\"
    cmd2 = '  -H "Content-Type: application/json" \\'
    cmd3 = "  -d '{\"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}]}'"

    def frame(lines: int, cursor: bool = False) -> Image.Image:
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
                     f'  Payment realm="API Access", id="ch_abc123...",', VAL)
                _out(d, y + LINE_H * 2,
                     f'  method="algorand-mainnet", amount="10000",', VAL)
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
        frames.append(frame(0, cursor=(i % 2 == 0)))
    for _ in range(15):
        frames.append(frame(1))
    for _ in range(40):
        frames.append(frame(2))
    return frames


def scene_200(adapter: str, model: str, ai_reply: str) -> list[Image.Image]:
    """Request with proof → 200 + AI response."""
    proof_cmd = 'PROOF=$(python3 -c "import base64,json; print(base64.b64encode('
    proof_cmd2 = '  json.dumps({\'network\':\'algorand-mainnet\',\'payload\':{\'txId\':\'TX123...\'}})'
    proof_cmd3 = '  .encode()).decode())")'

    curl_cmd  = "curl -s -X POST http://localhost:5000/ai/chat \\"
    curl_cmd2 = '  -H "Content-Type: application/json" \\'
    curl_cmd3 = '  -H "Authorization: Payment $PROOF" \\'
    curl_cmd4 = "  -d '{\"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}]}'"

    # Wrap long reply
    words     = ai_reply.split()
    line1, line2 = "", ""
    for w in words:
        if len(line1) + len(w) < 70:
            line1 += w + " "
        else:
            line2 += w + " "
    reply_lines = [line1.strip()]
    if line2.strip():
        reply_lines.append("  " + line2.strip())

    def frame(phase: int, n_reply_chars: int = 0) -> Image.Image:
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
            _out(d, y, "echo $PROOF", CMD)
            d.text((LPAD, y), "$", font=FONT_BOLD, fill=PROMPT)
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
            # Split to two display lines if long
            if len(display) > 72:
                _out(d, y, display[:72], JSON_KEY)
                _out(d, y + LINE_H, "  " + display[72:] + ('"}' if n_reply_chars >= len(ai_reply) else "▊"), JSON_VAL)
            else:
                suffix = '"}' if n_reply_chars >= len(ai_reply) else "▊"
                _out(d, y, display + suffix, JSON_KEY)

        return img

    frames = []
    for _ in range(15):
        frames.append(frame(0))
    for _ in range(12):
        frames.append(frame(1))
    for _ in range(12):
        frames.append(frame(2))
    for _ in range(12):
        frames.append(frame(3))
    for _ in range(10):
        frames.append(frame(4))
    # Streaming reply effect
    reply_len = len(ai_reply)
    step = max(1, reply_len // 30)
    for i in range(0, reply_len + 1, step):
        frames.append(frame(5, min(i, reply_len)))
    for _ in range(50):
        frames.append(frame(5, reply_len))
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

def _save_gif(frames: list[Image.Image], path: str,
              frame_ms: int = 50) -> None:
    """Save frames as an animated GIF."""
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
