#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# AlgoVoi AI Adapters — Demo Recording Script
#
# Records a terminal demo showing payment-gated AI APIs across all three
# adapters (OpenAI, Claude, Gemini) using MPP on Algorand mainnet.
#
# Prerequisites:
#   pip install asciinema agg
#   Set environment variables (or edit the defaults below)
#
# Usage:
#   bash record_demo.sh            # record the demo
#   agg demo.cast demo.gif         # convert to GIF for GitHub READMEs
#   ffmpeg -i demo.gif demo.mp4    # convert to MP4 for YouTube / social
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

CAST_FILE="${1:-algovoi_ai_demo.cast}"
HOST="${DEMO_HOST:-http://localhost:5000}"
PROOF="${DEMO_PROOF:-}"   # base64-encoded MPP proof — set before recording

echo ""
echo "AlgoVoi AI Adapters Demo"
echo "========================"
echo "Output: $CAST_FILE"
echo ""
echo "Make sure your server is running:"
echo "  cd ai-adapters/claude && python example.py flask"
echo ""
echo "Set DEMO_PROOF to a valid MPP payment proof before recording."
echo "Press ENTER to start recording (Ctrl-D to stop)..."
read -r

asciinema rec "$CAST_FILE" --title "AlgoVoi — Payment-Gated AI APIs"
echo "Recorded to $CAST_FILE"
