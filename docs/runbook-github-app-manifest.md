# Runbook: Create a GitHub App (Manifest Flow)

Reusable runbook for creating GitHub Apps for any boring-* service.
Uses the manifest flow — one browser click, everything else scripted.

## Quick Start

```bash
# 1. Generate the creation page
./scripts/github-app-create.sh \
  --name "Boring UI" \
  --homepage "https://github.com/boringdata/boring-ui" \
  --callback "https://your-domain.com/api/v1/auth/github/callback" \
  --vault-path "secret/agent/github-app-boring-ui"

# 2. Open the printed URL in your browser, click "Create GitHub App"
# 3. Paste the code from the redirect URL
# 4. Done — credentials stored in Vault
```

---

## How It Works

```
You run the script
  |
  v
Script generates an HTML page and serves it
  |
  v
You open the URL in your browser → auto-POSTs manifest to GitHub
  |
  v
GitHub shows "Create GitHub App" → you click it
  |
  v
GitHub redirects to redirect_url?code=XXXXX
  |
  v
You paste the code → script exchanges it for credentials via API
  |
  v
Credentials stored in Vault (app_id, client_id, client_secret, pem)
```

---

## Manual Steps (if the script isn't available)

### Step 1: Create the App

Open this HTML locally (save as a file, open in browser). Replace the 3
placeholders with your values:

```html
<!DOCTYPE html>
<html><body>
<h2>Create GitHub App</h2>
<form id="f" action="https://github.com/settings/apps/new" method="post">
  <input type="hidden" name="manifest" id="m">
  <button type="submit" style="font-size:18px;padding:10px 24px">
    Create GitHub App
  </button>
</form>
<script>
document.getElementById('m').value = JSON.stringify({
  "name":        "YOUR_APP_NAME",
  "url":         "YOUR_HOMEPAGE_URL",
  "description": "Git sync integration for YOUR_APP_NAME",
  "redirect_url":"YOUR_CALLBACK_URL",
  "callback_urls":["YOUR_CALLBACK_URL"],
  "public":       false,
  "default_permissions": {"contents":"write","metadata":"read"},
  "default_events": []
});
</script>
</body></html>
```

IMPORTANT: Do NOT include `hook_attributes` unless you need webhooks.
GitHub requires `hook_attributes.url` whenever the object is present,
even with `active: false`. Omit it entirely for apps that don't use webhooks.

Click the button. GitHub shows a confirmation page. Click "Create GitHub App".

After creation, GitHub redirects to `YOUR_CALLBACK_URL?code=v1.XXXXX`.
Copy the `code` value from the URL bar.

### Step 2: Exchange the Code for Credentials

The code is valid for 1 hour, single-use.

```bash
CODE="v1.XXXXX"  # paste your code here

gh api --method POST "/app-manifests/${CODE}/conversions" \
  > /tmp/github-app-creds.json

# Inspect what we got
python3 -c "
import json
c = json.load(open('/tmp/github-app-creds.json'))
print(f'App ID:        {c[\"id\"]}')
print(f'Slug:          {c[\"slug\"]}')
print(f'Client ID:     {c[\"client_id\"]}')
print(f'Client Secret: {c[\"client_secret\"][:8]}...')
print(f'PEM:           {len(c[\"pem\"])} bytes')
print(f'Webhook Secret:{c.get(\"webhook_secret\", \"(none)\")}')
"
```

### Step 3: Store in Vault

```bash
APP_ID=$(python3 -c "import json; print(json.load(open('/tmp/github-app-creds.json'))['id'])")
SLUG=$(python3 -c "import json; print(json.load(open('/tmp/github-app-creds.json'))['slug'])")
CLIENT_ID=$(python3 -c "import json; print(json.load(open('/tmp/github-app-creds.json'))['client_id'])")
CLIENT_SECRET=$(python3 -c "import json; print(json.load(open('/tmp/github-app-creds.json'))['client_secret'])")
PEM=$(python3 -c "import json; print(json.load(open('/tmp/github-app-creds.json'))['pem'])")
WEBHOOK_SECRET=$(python3 -c "import json; print(json.load(open('/tmp/github-app-creds.json')).get('webhook_secret',''))")

# Store (requires Vault write access)
vault kv put secret/agent/github-app-YOUR-APP \
  app_id="$APP_ID" \
  slug="$SLUG" \
  client_id="$CLIENT_ID" \
  client_secret="$CLIENT_SECRET" \
  private_key="$PEM" \
  webhook_secret="$WEBHOOK_SECRET"

# Verify
vault kv get secret/agent/github-app-YOUR-APP

# Clean up
rm -f /tmp/github-app-creds.json
```

### Step 4: Verify the App Works

```bash
# Generate a JWT from the private key
JWT=$(python3 << 'PYSCRIPT'
import jwt, time, subprocess
app_id = subprocess.run(
    ['vault', 'kv', 'get', '-field=app_id', 'secret/agent/github-app-YOUR-APP'],
    capture_output=True, text=True).stdout.strip()
pem = subprocess.run(
    ['vault', 'kv', 'get', '-field=private_key', 'secret/agent/github-app-YOUR-APP'],
    capture_output=True, text=True).stdout.strip()
now = int(time.time())
token = jwt.encode({'iat': now - 60, 'exp': now + 600, 'iss': app_id}, pem, algorithm='RS256')
print(token)
PYSCRIPT
)

# Check the app identity
curl -s -H "Authorization: Bearer $JWT" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/app | python3 -c "
import json,sys
app = json.load(sys.stdin)
print(f'App: {app[\"name\"]} (id={app[\"id\"]})')
print(f'Slug: {app[\"slug\"]}')
print(f'Permissions: {json.dumps(app.get(\"permissions\",{}), indent=2)}')
"
```

### Step 5: Install on Repos

```bash
SLUG=$(vault kv get -field=slug secret/agent/github-app-YOUR-APP)
echo "Install at: https://github.com/apps/${SLUG}/installations/new"
```

Open that URL, select repos, click Install.

### Step 6: Get an Installation Token (for git ops)

```bash
# List installations
curl -s -H "Authorization: Bearer $JWT" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/app/installations \
  | python3 -c "
import json,sys
for i in json.load(sys.stdin):
    print(f'  id={i[\"id\"]}  account={i[\"account\"][\"login\"]}')
"

# Create installation token
INSTALLATION_ID="<from above>"
TOKEN=$(curl -s -X POST \
  -H "Authorization: Bearer $JWT" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/app/installations/${INSTALLATION_ID}/access_tokens" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['token'])")

echo "Installation token: ${TOKEN}"
echo "Valid for 1 hour. Use as git password with username x-access-token."

# Test: clone a private repo
git clone "https://x-access-token:${TOKEN}@github.com/OWNER/REPO.git" /tmp/test-clone
```

---

## Token Lifecycle

```
App Private Key (permanent, in Vault)
    |  sign JWT (valid 10 min)
    v
App JWT
    |  POST /app/installations/{id}/access_tokens
    v
Installation Token (valid 1 hour, auto-renewable)
    |  used as git credential
    v
git push / pull / clone
```

Backend should:
- Cache installation tokens in memory
- Refresh when < 5 min remaining
- Map workspace_id -> installation_id in DB/config

---

## Permissions Reference

| Permission | Level | Use case |
|---|---|---|
| `contents` | `write` | Push, pull, clone, read files |
| `contents` | `read` | Clone, read files only |
| `metadata` | `read` | List repos, check access (always included) |
| `pull_requests` | `write` | Create/update PRs |
| `pull_requests` | `read` | Read PR status |
| `issues` | `write` | Create/update issues |
| `actions` | `read` | Read CI status |

Only request what you need. Users see the permission list during installation.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Manifest error: "url wasn't supplied" | Remove `hook_attributes` entirely. GitHub requires `hook_attributes.url` whenever the object is present. |
| Code exchange fails | Code is single-use, 1-hour TTL. Re-create the app if expired. |
| `bad credentials` on JWT | Check PEM key. Check system clock (JWT uses `iat`). |
| `resource not accessible` | App not installed on that repo. Run Step 5. |
| `suspended` installation | User revoked. Prompt to re-install. |
| Installation token expired | Tokens last 1 hour. Backend must auto-refresh. |

---

## Rollback

```bash
# Delete the app (irreversible — all installations removed)
SLUG=$(vault kv get -field=slug secret/agent/github-app-YOUR-APP)
JWT="<generate as above>"
curl -X DELETE -H "Authorization: Bearer $JWT" \
  "https://api.github.com/app"

# Or via web: https://github.com/settings/apps/<slug>/advanced -> Delete

# Remove from Vault
vault kv delete secret/agent/github-app-YOUR-APP
```

---

## For boring-ui Specifically

Vault path: `secret/agent/github-app-boring-ui`

Backend env vars:
```bash
export GITHUB_APP_ID=$(vault kv get -field=app_id secret/agent/github-app-boring-ui)
export GITHUB_APP_CLIENT_ID=$(vault kv get -field=client_id secret/agent/github-app-boring-ui)
export GITHUB_APP_CLIENT_SECRET=$(vault kv get -field=client_secret secret/agent/github-app-boring-ui)
export GITHUB_APP_PRIVATE_KEY=$(vault kv get -field=private_key secret/agent/github-app-boring-ui)
```

Backend endpoints to implement:
| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/auth/github/authorize` | GET | Redirect to GitHub OAuth |
| `/api/v1/auth/github/callback` | GET | Exchange code, store installation |
| `/api/v1/auth/github/status` | GET | Check connection status |
| `/api/v1/auth/github/disconnect` | POST | Remove stored tokens |
