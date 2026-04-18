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

REQUIRED = ["X_API_KEY", "X_API_KEY_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
missing  = [k for k in REQUIRED if not os.environ.get(k)]
if missing:
    print(f"ERROR: missing env vars: {', '.join(missing)}")
    print(__doc__)
    sys.exit(1)

x = AlgoVoiX(
    algovoi_key=             os.environ.get("ALGOVOI_API_KEY", "algv_" + "x" * 40),
    tenant_id=               os.environ.get("ALGOVOI_TENANT_ID", "00000000-0000-0000-0000-000000000000"),
    payout_algorand=         "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ",
    x_api_key=               os.environ["X_API_KEY"],
    x_api_key_secret=        os.environ["X_API_KEY_SECRET"],
    x_access_token=          os.environ["X_ACCESS_TOKEN"],
    x_access_token_secret=   os.environ["X_ACCESS_TOKEN_SECRET"],
)

TWEET = (
    "AlgoVoi test tweet — crypto payments on Algorand, VOI, Hedera & Stellar 🚀\n"
    "github.com/chopmob-cloud/AlgoVoi-Platform-Adapters\n"
    "#AlgoVoi #crypto #algorand"
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
