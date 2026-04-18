# How to Post a Test Tweet with AlgoVoi X Adapter

## Step 1 — Get X API credentials

1. Go to **https://developer.x.com/en/portal/dashboard**
2. Click **"+ Add Project"** → give it any name → select **"Making a bot"** use case
3. Inside the project, create an **App**
4. Go to your app → **"Settings"** tab → **User authentication settings** → click **Edit**
   - App permissions: **Read and Write**
   - Type of App: **Web App, Automated App or Bot**
   - Callback URI: `https://localhost` (placeholder, not used)
   - Website URL: `https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters`
   - Save
5. Go to **"Keys and Tokens"** tab and copy/generate:
   - **API Key** → this is `X_API_KEY`
   - **API Key Secret** → this is `X_API_KEY_SECRET`
   - **Access Token** → this is `X_ACCESS_TOKEN`  
   - **Access Token Secret** → this is `X_ACCESS_TOKEN_SECRET`

> **Important:** Access Token and Secret must be generated *after* setting Read+Write
> permissions. If you generated them before, regenerate them now.

---

## Step 2 — Run the test script

From the repo root (`C:\algo\platform-adapters`):

```bash
cd C:\algo\platform-adapters

X_API_KEY=your_api_key \
X_API_KEY_SECRET=your_api_key_secret \
X_ACCESS_TOKEN=your_access_token \
X_ACCESS_TOKEN_SECRET=your_access_token_secret \
    python no-code/x/post_test_tweet.py
```

Or on Windows CMD:

```cmd
set X_API_KEY=your_api_key
set X_API_KEY_SECRET=your_api_key_secret
set X_ACCESS_TOKEN=your_access_token
set X_ACCESS_TOKEN_SECRET=your_access_token_secret
python no-code\x\post_test_tweet.py
```

---

## Step 3 — Check the output

Success looks like:

```
Posting tweet...
✓ Tweet posted!
  ID  : 1234567890123456789
  URL : https://x.com/i/web/status/1234567890123456789
  Text: AlgoVoi test tweet — crypto payments on Algorand, VOI, Hedera & Stellar 🚀
```

Open the URL to confirm it appeared on X.

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `401 Unauthorized` | Wrong keys or wrong key type | Regenerate Access Token *after* setting Read+Write |
| `403 Forbidden` | App has Read-only permissions | Edit app → set Read+Write → regenerate tokens |
| `429 Too Many Requests` | Rate limit hit | Wait 15 min (or 1 month if monthly limit hit) |
| `duplicate content` | Same tweet text posted twice | Change the tweet text |
