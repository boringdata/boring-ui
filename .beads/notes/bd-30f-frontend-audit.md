# Frontend Entry Points and Asset References Audit (bd-30f)

## 1. React Entry and Root Component Wiring

### Main Entry Point
- `index.html:23` - References `/src/main.jsx`
  - **After move**: Must update to `/src/front/main.jsx`

### Root Component Chain
- `src/main.jsx` → imports:
  - `./App` (App.jsx)
  - `./config` (ConfigProvider)
  - `./styles.css` (global styles)
- `src/App.jsx` → imports 12 modules (all relative paths)

## 2. Build and Tooling Configurations

### vite.config.ts
- Line 17: Alias `'@': path.resolve(__dirname, './src')`
  - **After move**: Update to `'./src/front'`
- Line 33: Library entry `'src/index.js'`
  - **After move**: Update to `'src/front/index.js'`
  - **NOTE**: `src/index.js` does not exist yet - needs to be created

### tsconfig.json
- Line 20: Path alias `"@/*": ["./src/*"]`
  - **After move**: Update to `["./src/front/*"]`
- Line 23: Include directive `"src"`
  - **After move**: Update to `"src/front"`

### tailwind.config.js
- Line 5: Content glob `'./src/**/*.{js,jsx,ts,tsx}'`
  - **After move**: Update to `'./src/front/**/*.{js,jsx,ts,tsx}'`

## 3. Test Configurations

### vitest.config.ts
- Line 9: Setup file `'./src/__tests__/setup.ts'`
  - **After move**: Update to `'./src/front/__tests__/setup.ts'`
- Line 10: Include pattern `'src/**/*.{test,spec}.{js,jsx,ts,tsx}'`
  - **After move**: Update to `'src/front/**/*.{test,spec}.{js,jsx,ts,tsx}'`
- Lines 14-15: Coverage include/exclude paths
  - **After move**: Prefix with `'src/front/'`

### playwright.config.js
- Line 14: Test directory `'./src/__tests__/e2e'`
  - **After move**: Update to `'./src/front/__tests__/e2e'`

## 4. Package Scripts

### package.json
- Line 38: Lint target `"lint": "eslint src/"`
  - **After move**: Update to `"eslint src/front/"`

## 5. Static Assets

### public/app.config.js
- Static file, no path changes needed
- Accessed via HTTP, not import path

## 6. CSS and Font References

### src/styles.css
- Line 1: External Google Fonts URL (no change needed)
- No hard-coded local asset paths

## 7. Relative Import Patterns

All imports use relative paths (good!):
- Panel files import from `../components/`
- Components import from `../utils/`, `../hooks/`
- Config/layout modules use relative paths

**No @ alias imports found** in current codebase - migration won't break any alias references.

## 8. LocalStorage Keys

- `index.html:12` - Hard-coded `'kurt-web-theme'` key
  - Consider updating to use config prefix
- `src/App.jsx` - Uses configurable `storagePrefix` (good!)

## Summary: Files Requiring Path Updates

| File | Lines | Change Required |
|------|-------|-----------------|
| index.html | 23 | /src/main.jsx → /src/front/main.jsx |
| vite.config.ts | 17, 33 | ./src → ./src/front |
| tsconfig.json | 20, 23 | ./src/* → ./src/front/* |
| tailwind.config.js | 5 | ./src/** → ./src/front/** |
| vitest.config.ts | 9, 10, 14, 15 | src/ → src/front/ |
| playwright.config.js | 14 | ./src/__tests__/e2e → ./src/front/__tests__/e2e |
| package.json | 38 | eslint src/ → eslint src/front/ |

## Additional Work Required

- Create `src/front/index.js` public API file (referenced in vite.config.ts but doesn't exist)

---
*Audit completed: 2026-02-05*
