# PI Agent API Keys

The PI agent runs LLM calls directly from the browser. It needs provider API keys (OpenAI, Anthropic, Google) in the browser's IndexedDB.

## Production

Users enter their own keys via a browser prompt when they first use the PI agent. Keys persist in IndexedDB across page reloads until the user clears browser storage. **The server never sees or stores these keys.**

## Dev Mode

In dev mode, keys are automatically seeded from Vite environment variables on page load, so you don't get prompted every time.

### Option 1: `.env` file

Add to your local env file (gitignored via `.env.*.local`):

```bash
# .env.core.local (docker-compose / CORE_ prefix)
CORE_VITE_PI_ANTHROPIC_API_KEY=sk-ant-...
CORE_VITE_PI_OPENAI_API_KEY=sk-...
CORE_VITE_PI_GOOGLE_API_KEY=AIza...
```

Or if running Vite directly (no docker-compose), use the `VITE_` prefix:

```bash
# .env.local
VITE_PI_ANTHROPIC_API_KEY=sk-ant-...
VITE_PI_OPENAI_API_KEY=sk-...
VITE_PI_GOOGLE_API_KEY=AIza...
```

### Option 2: Vault (one-liner)

Fetch from Vault and pass inline:

```bash
VITE_PI_ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic) \
  npx vite --host 0.0.0.0 --port 5173
```

### Option 3: Shell export

```bash
export VITE_PI_ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic)
export VITE_PI_OPENAI_API_KEY=$(vault kv get -field=api_key secret/agent/openai)
npx vite --host 0.0.0.0 --port 5173
```

## How It Works

- `src/front/providers/pi/nativeAdapter.jsx` checks `import.meta.env.DEV` on mount
- If true, reads `import.meta.env.VITE_PI_{OPENAI,ANTHROPIC,GOOGLE}_API_KEY`
- Non-empty values are written to `runtime.providerKeys` (IndexedDB-backed store)
- Keys persist across reloads; clear browser storage to reset
- In production builds, `import.meta.env.DEV` is `false` so this code is tree-shaken out

## Security Notes

- API keys never leave the browser (no server endpoint, no network transmission)
- `.env.*.local` files are gitignored — keys won't be committed
- Vite only exposes env vars prefixed with `VITE_` to the browser bundle
- Production users are responsible for their own keys
