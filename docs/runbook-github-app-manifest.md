# Runbook: GitHub App Creation via Manifest Flow

## Overview

This runbook creates a GitHub App for boring-ui using the [App Manifest flow](https://docs.github.com/en/apps/sharing-github-apps/registering-a-github-app-from-a-manifest). The manifest flow lets us define the app's permissions, webhooks, and callback URLs in a JSON file, then create the app with a single browser confirmation.

The resulting app provides:
- OAuth-based user authentication (no PATs needed)
- Installation tokens for git push/pull operations
- Fine-grained repo permissions (only repos the user explicitly grants)

## Prerequisites

- `gh` CLI authenticated (`gh auth status`)
- Access to HashiCorp Vault for storing secrets
- A publicly reachable callback URL (or ngrok/tunnel for local dev)
- Browser access to github.com

## Architecture

```
User clicks "Connect GitHub"
       |
       v
boring-ui backend redirects to GitHub OAuth
       |
       v
GitHub prompts user to authorize + install app
       |
       v
GitHub redirects to /api/v1/auth/github/callback?code=XXX
       |
       v
Backend exchanges code for user access token
Backend uses app private key to get installation token
Installation token injected into git push/pull
```

---

## Step 1: Define the App Manifest

The manifest JSON describes everything about the app.

```bash
# Choose your base URL (production or dev tunnel)
export APP_BASE_URL="https://your-boring-ui-domain.com"
# For local dev: export APP_BASE_URL="https://xxxx.ngrok.io"
```

Create the manifest:

```json
{
  "name": "Boring UI Git Sync",
  "url": "https://github.com/boringdata/boring-ui",
  "hook_attributes": {
    "active": false
  },
  "redirect_url": "${APP_BASE_URL}/api/v1/auth/github/callback",
  "setup_url": "${APP_BASE_URL}/api/v1/auth/github/setup",
  "callback_urls": [
    "${APP_BASE_URL}/api/v1/auth/github/callback"
  ],
  "setup_on_update": true,
  "public": false,
  "default_permissions": {
    "contents": "write",
    "metadata": "read",
    "pull_requests": "read"
  },
  "default_events": []
}
```

### Permissions explained

| Permission | Level | Why |
|---|---|---|
| `contents` | `write` | Push/pull/clone repo contents |
| `metadata` | `read` | List repos, check access |
| `pull_requests` | `read` | Optional: show PR status in UI |

No webhook events needed (we poll, not push).

---

## Step 2: Create the App via Manifest Flow

The manifest flow requires a brief browser interaction. There are two ways:

### Option 2A: Automated (script + browser confirm)

```bash
# 1. Generate the manifest with actual URLs substituted
export APP_BASE_URL="https://your-boring-ui-domain.com"

cat > /tmp/github-app-manifest.json << 'MANIFEST'
{
  "name": "Boring UI Git Sync",
  "url": "https://github.com/boringdata/boring-ui",
  "hook_attributes": {
    "active": false
  },
  "redirect_url": "APP_BASE_URL_PLACEHOLDER/api/v1/auth/github/callback",
  "setup_url": "APP_BASE_URL_PLACEHOLDER/api/v1/auth/github/setup",
  "callback_urls": [
    "APP_BASE_URL_PLACEHOLDER/api/v1/auth/github/callback"
  ],
  "setup_on_update": true,
  "public": false,
  "default_permissions": {
    "contents": "write",
    "metadata": "read"
  },
  "default_events": []
}
MANIFEST

sed -i "s|APP_BASE_URL_PLACEHOLDER|${APP_BASE_URL}|g" /tmp/github-app-manifest.json

# 2. Start a temporary local server to receive the manifest code
#    (GitHub redirects here after user clicks "Create")
python3 -c "
import http.server, urllib.parse, json, sys

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        code = params.get('code', [''])[0]
        if code:
            print(f'\n=== MANIFEST CODE: {code} ===\n', file=sys.stderr)
            with open('/tmp/github-app-manifest-code.txt', 'w') as f:
                f.write(code)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'<h1>GitHub App created! You can close this tab.</h1>')
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Missing code parameter')

httpd = http.server.HTTPServer(('127.0.0.1', 3456), Handler)
print('Waiting for GitHub manifest callback on http://127.0.0.1:3456 ...', file=sys.stderr)
httpd.handle_request()  # serve exactly one request
" &
RECEIVER_PID=$!

# 3. Open the manifest creation page in the browser
#    For personal account:
echo "Open this URL in your browser:"
echo "https://github.com/settings/apps/new?manifest=$(python3 -c "
import json, urllib.parse
with open('/tmp/github-app-manifest.json') as f:
    manifest = f.read()
# Override redirect_url to point to our local receiver
m = json.loads(manifest)
m['redirect_url'] = 'http://127.0.0.1:3456/callback'
print(urllib.parse.quote(json.dumps(m)))
")"

#    For org account (replace ORG):
#    https://github.com/organizations/ORG/settings/apps/new?manifest=...

# 4. Click "Create GitHub App" in the browser
#    GitHub will redirect to http://127.0.0.1:3456/callback?code=XXXXX
#    The code is captured automatically

wait $RECEIVER_PID 2>/dev/null
```

### Option 2B: Manual (simplest)

1. Go to https://github.com/settings/apps/new
2. Fill in:
   - **Name**: `Boring UI Git Sync`
   - **Homepage URL**: `https://github.com/boringdata/boring-ui`
   - **Callback URL**: `${APP_BASE_URL}/api/v1/auth/github/callback`
   - **Setup URL**: `${APP_BASE_URL}/api/v1/auth/github/setup`
   - **Webhooks**: uncheck "Active"
   - **Permissions**: Repository > Contents: Read & Write, Metadata: Read
3. Click "Create GitHub App"
4. Note the **App ID** and **Client ID**
5. Generate a **Private Key** (.pem) — download it
6. Generate a **Client Secret** — copy it
7. Skip to Step 4 (store in Vault)

---

## Step 3: Exchange the Manifest Code for Credentials

The manifest code (from Step 2A) is valid for 1 hour, single-use.

```bash
# Read the code captured by our receiver
MANIFEST_CODE=$(cat /tmp/github-app-manifest-code.txt)

# Exchange for full app credentials
gh api \
  --method POST \
  "/app-manifests/${MANIFEST_CODE}/conversions" \
  > /tmp/github-app-credentials.json

# Extract the important fields
python3 -c "
import json
with open('/tmp/github-app-credentials.json') as f:
    creds = json.load(f)
print(f'App ID:        {creds[\"id\"]}')
print(f'App slug:      {creds[\"slug\"]}')
print(f'Client ID:     {creds[\"client_id\"]}')
print(f'Client Secret: {creds[\"client_secret\"]}')
print(f'PEM Key:       (saved to /tmp/github-app-private-key.pem)')
print(f'Webhook Secret:{creds.get(\"webhook_secret\", \"(none)\")}')
with open('/tmp/github-app-private-key.pem', 'w') as f:
    f.write(creds['pem'])
"
```

**IMPORTANT**: The `/app-manifests/{code}/conversions` endpoint returns credentials **exactly once**. If it fails, you must delete the app and repeat from Step 2.

---

## Step 4: Store Credentials in Vault

```bash
# Parse credentials
APP_ID=$(python3 -c "import json; print(json.load(open('/tmp/github-app-credentials.json'))['id'])")
CLIENT_ID=$(python3 -c "import json; print(json.load(open('/tmp/github-app-credentials.json'))['client_id'])")
CLIENT_SECRET=$(python3 -c "import json; print(json.load(open('/tmp/github-app-credentials.json'))['client_secret'])")
PEM_KEY=$(cat /tmp/github-app-private-key.pem)

# Store in Vault (requires write access — run from admin machine)
vault kv put secret/agent/github-app \
  app_id="$APP_ID" \
  client_id="$CLIENT_ID" \
  client_secret="$CLIENT_SECRET" \
  private_key="$PEM_KEY"

# Verify
vault kv get -field=app_id secret/agent/github-app
```

### Clean up sensitive files

```bash
rm -f /tmp/github-app-credentials.json
rm -f /tmp/github-app-private-key.pem
rm -f /tmp/github-app-manifest-code.txt
```

---

## Step 5: Backend Configuration

The backend reads credentials from Vault (or env vars) at startup:

```bash
# Environment variables the backend expects
export GITHUB_APP_ID=$(vault kv get -field=app_id secret/agent/github-app)
export GITHUB_APP_CLIENT_ID=$(vault kv get -field=client_id secret/agent/github-app)
export GITHUB_APP_CLIENT_SECRET=$(vault kv get -field=client_secret secret/agent/github-app)
export GITHUB_APP_PRIVATE_KEY=$(vault kv get -field=private_key secret/agent/github-app)
```

---

## Step 6: Test the OAuth Flow

### 6a. Generate the OAuth authorization URL

```bash
CLIENT_ID=$(vault kv get -field=client_id secret/agent/github-app)
REDIRECT_URI="${APP_BASE_URL}/api/v1/auth/github/callback"
STATE=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

echo "Open in browser:"
echo "https://github.com/login/oauth/authorize?client_id=${CLIENT_ID}&redirect_uri=${REDIRECT_URI}&state=${STATE}"
```

### 6b. Exchange the callback code for a user token

After the user authorizes, GitHub redirects to the callback with `?code=XXX&state=YYY`.

```bash
# The backend does this automatically, but to test manually:
CODE="<paste code from callback URL>"

gh api --method POST \
  "https://github.com/login/oauth/access_token" \
  -f client_id="$CLIENT_ID" \
  -f client_secret="$(vault kv get -field=client_secret secret/agent/github-app)" \
  -f code="$CODE" \
  -H "Accept: application/json"

# Returns: { "access_token": "ghu_XXXX", "token_type": "bearer", "scope": "" }
```

### 6c. Get an installation token (for git operations)

```bash
# 1. Generate a JWT from the app's private key
JWT=$(python3 -c "
import jwt, time
APP_ID = '$(vault kv get -field=app_id secret/agent/github-app)'
with open('/dev/stdin') as f:
    private_key = f.read()
now = int(time.time())
payload = {'iat': now - 60, 'exp': now + (10 * 60), 'iss': APP_ID}
print(jwt.encode(payload, private_key, algorithm='RS256'))
" <<< "$(vault kv get -field=private_key secret/agent/github-app)")

# 2. List installations
curl -s -H "Authorization: Bearer $JWT" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/app/installations | python3 -m json.tool

# 3. Create installation token (replace INSTALLATION_ID)
INSTALLATION_ID="<from step above>"
curl -s -X POST \
  -H "Authorization: Bearer $JWT" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/app/installations/${INSTALLATION_ID}/access_tokens" \
  | python3 -m json.tool

# Returns: { "token": "ghs_XXXX", "expires_at": "...", "permissions": {...} }
```

### 6d. Test git operations with the installation token

```bash
INSTALL_TOKEN="ghs_XXXX"  # from step 6c

# Clone a private repo
git clone https://x-access-token:${INSTALL_TOKEN}@github.com/owner/repo.git /tmp/test-clone

# Or configure as credential helper
git -c "credential.helper=!f(){ echo username=x-access-token; echo password=${INSTALL_TOKEN}; }; f" \
  push origin main
```

---

## Step 7: Install the App on Target Repos

```bash
APP_SLUG=$(vault kv get -field=app_slug secret/agent/github-app 2>/dev/null || echo "boring-ui-git-sync")
echo "Install the app at:"
echo "https://github.com/apps/${APP_SLUG}/installations/new"
```

Select the repositories you want boring-ui to access, then click "Install".

---

## Backend Endpoints to Implement

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/auth/github/authorize` | GET | Redirect user to GitHub OAuth |
| `/api/v1/auth/github/callback` | GET | Exchange code for user token, store installation |
| `/api/v1/auth/github/setup` | GET | Handle post-installation redirect |
| `/api/v1/auth/github/status` | GET | Check if GitHub is connected for current workspace |
| `/api/v1/auth/github/disconnect` | POST | Remove stored tokens |

### Token lifecycle

```
App Private Key (long-lived, in Vault)
    |
    v  [JWT signed with private key, valid 10 min]
Installation Token (short-lived, 1 hour)
    |
    v  [injected as git credential]
git push/pull operations
```

The backend should:
1. Cache installation tokens in memory (they last 1 hour)
2. Refresh automatically when expired
3. Map workspace -> installation_id (persisted in workspace config)

---

## Rollback / Delete

```bash
# Delete the GitHub App (irreversible)
APP_SLUG="boring-ui-git-sync"
gh api --method DELETE "/apps/${APP_SLUG}"

# Or via web: https://github.com/settings/apps/<app-slug>/advanced -> Delete

# Remove from Vault
vault kv delete secret/agent/github-app
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `manifest code expired` | Code is valid 1 hour. Re-run from Step 2. |
| `resource not accessible by integration` | App not installed on the repo. Run Step 7. |
| `bad credentials` (JWT) | Check PEM key in Vault matches. Check clock skew (JWT uses `iat`). |
| `installation token expired` | Tokens last 1 hour. Backend must auto-refresh. |
| OAuth callback 404 | Verify `redirect_url` matches exactly (scheme, host, path). |
| `suspended` installation | User revoked access. Prompt to re-install. |

---

## Security Notes

- **Private key**: Never expose. Store only in Vault. Never log.
- **Installation tokens**: Short-lived (1h), scoped to specific repos. Safe to hold in memory.
- **User tokens**: Scoped by what the user authorized. Store encrypted if persisted.
- **State parameter**: Always validate in OAuth callback to prevent CSRF.
- **Webhook secret**: Not used (webhooks disabled), but store anyway for future use.
