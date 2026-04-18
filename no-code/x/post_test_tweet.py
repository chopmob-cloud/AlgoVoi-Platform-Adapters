"""
AlgoVoi X adapter — quick test tweet script.

Usage (from repo root):
    X_API_KEY=... X_API_KEY_SECRET=... X_ACCESS_TOKEN=... X_ACCESS_TOKEN_SECRET=... \\
        python no-code/x/post_test_tweet.py

Windows CMD:
    set X_API_KEY=...
    set X_API_KEY_SECRET=...
    set X_ACCESS_TOKEN=...
    set X_ACCESS_TOKEN_SECRET=...
    python no-code\\x\\post_test_tweet.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from x_algovoi import AlgoVoiX

def _load_keys_txt() -> dict:
    """Read X credentials from keys.txt in the repo root (supports both naming conventions)."""
    creds: dict = {}
    keys_path = os.path.join(os.path.dirname(__file__), "..", "..", "keys.txt")
    try:
        with open(keys_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    creds[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    # Normalise: X_API_SECRET → X_API_KEY_SECRET, X_ACCESS_SECRET → X_ACCESS_TOKEN_SECRET
    if "X_API_SECRET" in creds and "X_API_KEY_SECRET" not in creds:
        creds["X_API_KEY_SECRET"] = creds["X_API_SECRET"]
    if "X_ACCESS_SECRET" in creds and "X_ACCESS_TOKEN_SECRET" not in creds:
        creds["X_ACCESS_TOKEN_SECRET"] = creds["X_ACCESS_SECRET"]
    return creds

# Merge: env vars take priority over keys.txt
_file_creds = _load_keys_txt()
CREDS = {k: os.environ.get(k) or _file_creds.get(k, "") for k in
         ["X_API_KEY", "X_API_KEY_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]}

missing = [k for k, v in CREDS.items() if not v]
if missing:
    print(f"ERROR: missing credentials: {', '.join(missing)}")
    print("Set them as env vars or add to keys.txt (X_API_KEY=..., X_API_SECRET=..., etc.)")
    sys.exit(1)

x = AlgoVoiX(
    algovoi_key=             os.environ.get("ALGOVOI_API_KEY", "algv_" + "x" * 40),
    tenant_id=               os.environ.get("ALGOVOI_TENANT_ID", "00000000-0000-0000-0000-000000000000"),
    payout_algorand=         "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ",
    x_api_key=               CREDS["X_API_KEY"],
    x_api_key_secret=        CREDS["X_API_KEY_SECRET"],
    x_access_token=          CREDS["X_ACCESS_TOKEN"],
    x_access_token_secret=   CREDS["X_ACCESS_TOKEN_SECRET"],
)

TWEET = (
    "AlgoVoi — open-source crypto payment adapters for any platform.\n\n"
    "Accept USDC & native tokens on Algorand, VOI, Hedera & Stellar. "
    "Works with Zapier, Make, n8n, AI agents (Claude, GPT) & more. "
    "Verified on-chain, no banks.\n\n"
    "https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters\n"
    "#AlgoVoi #crypto"
)

print("Posting tweet...")
result = x.post_tweet(TWEET)

if result.success:
    print(f"✓ Tweet posted!")
    print(f"  ID  : {result.data['tweet_id']}")
    print(f"  URL : {result.data['tweet_url']}")
    print(f"  Text: {result.data['text']}")
    sys.exit(0)
else:
    print(f"✗ Failed: {result.error}")
    sys.exit(1)
