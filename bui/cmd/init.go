package cmd

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/spf13/cobra"
)

var initCmd = &cobra.Command{
	Use:   "init <name>",
	Short: "Scaffold a new boring-ui child app",
	Long: `Scaffold boring.app.toml, pyproject.toml, routers, and deploy skeleton.

Run 'bui docs init' for the full child app guide.`,
	Args: cobra.ExactArgs(1),
	RunE: runInit,
}

func init() {
	rootCmd.AddCommand(initCmd)
}

func runInit(cmd *cobra.Command, args []string) error {
	name := args[0]

	// Validate name (alphanumeric + hyphens)
	for _, c := range name {
		if !((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-') {
			return fmt.Errorf("app name must be lowercase alphanumeric with hyphens, got %q", name)
		}
	}

	// Create directory
	if _, err := os.Stat(name); err == nil {
		return fmt.Errorf("directory %q already exists", name)
	}

	fmt.Printf("[bui] creating %s/\n", name)

	// Python package name (hyphens → underscores)
	pyName := strings.ReplaceAll(name, "-", "_")

	// Create directory structure
	dirs := []string{
		name,
		filepath.Join(name, "src", pyName, "routers"),
		filepath.Join(name, "panels"),
		filepath.Join(name, "deploy", "sql"),
	}
	for _, d := range dirs {
		if err := os.MkdirAll(d, 0o755); err != nil {
			return fmt.Errorf("mkdir %s: %w", d, err)
		}
	}

	// Detect framework commit from sibling boring-ui
	fwCommit := ""
	siblingBUI := filepath.Join(".", "boring-ui")
	if _, err := os.Stat(filepath.Join(siblingBUI, "boring.app.toml")); err != nil {
		// Try parent directory (if running from projects/)
		siblingBUI = filepath.Join("..", "boring-ui")
	}
	if _, err := os.Stat(filepath.Join(siblingBUI, ".git")); err == nil {
		headCmd := exec.Command("git", "rev-parse", "HEAD")
		headCmd.Dir = siblingBUI
		if out, err := headCmd.Output(); err == nil {
			fwCommit = strings.TrimSpace(string(out))
		}
	}

	// boring.app.toml
	fwSection := ""
	if fwCommit != "" {
		fwSection = fmt.Sprintf(`
[framework]
repo   = "github.com/boringdata/boring-ui"
commit = %q
`, fwCommit)
	} else {
		fwSection = `
# [framework]
# repo   = "github.com/boringdata/boring-ui"
# commit = ""  # set with 'bui upgrade'
`
	}

	toml := fmt.Sprintf(`# boring.app.toml — Configuration for %s

[app]
name = %q
logo = %q
id   = %q
%s
# ─── Backend ───────────────────────────────────────────────
[backend]
entry   = "%s.app:create_app"
port    = 8000
routers = []

# ─── Frontend ──────────────────────────────────────────────
[frontend]
port = 5173

[frontend.branding]
name = %q

[frontend.features]
agentRailMode = "all"

[frontend.data]
backend = "http"

[frontend.panels]

# ─── CLI commands (agent-discoverable) ────────────────────
[cli]
[cli.commands]

# ─── Auth ─────────────────────────────────────────────────
[auth]
provider       = "local"
session_cookie = "boring_session"
session_ttl    = 86400

# ─── Deploy ──────────────────────────────────────────────
[deploy]
platform = "modal"
env      = "prod"

[deploy.secrets]
ANTHROPIC_API_KEY = { vault = "secret/agent/anthropic", field = "api_key" }

[deploy.neon]
# Populated by 'bui neon setup'

[deploy.modal]
app_name       = %q
min_containers = 0
`, name, name, strings.ToUpper(name[:1]), name, fwSection, pyName, name, name)

	writeFile(filepath.Join(name, "boring.app.toml"), toml)

	// pyproject.toml
	pyproject := fmt.Sprintf(`[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = %q
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[tool.setuptools.packages.find]
where = ["src"]
`, name)
	writeFile(filepath.Join(name, "pyproject.toml"), pyproject)

	// Python package __init__.py
	writeFile(filepath.Join(name, "src", pyName, "__init__.py"), "")
	writeFile(filepath.Join(name, "src", pyName, "routers", "__init__.py"), "")

	// Example router
	exampleRouter := fmt.Sprintf(`"""Example router for %s."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/%s", tags=[%q])


@router.get("/health")
async def health():
    return {"ok": True, "app": %q}
`, name, pyName, name, name)
	writeFile(filepath.Join(name, "src", pyName, "routers", "example.py"), exampleRouter)

	// .gitignore
	gitignore := `.boring/
.venv/
dist/
node_modules/
__pycache__/
*.pyc
.env
`
	writeFile(filepath.Join(name, ".gitignore"), gitignore)

	// .env.example
	envExample := `# Local dev secrets — copy to .env and fill in
ANTHROPIC_API_KEY=sk-ant-...
BORING_UI_SESSION_SECRET=dev-only-local-secret
`
	writeFile(filepath.Join(name, ".env.example"), envExample)

	fmt.Println()
	fmt.Printf("[bui] %s created!\n\n", name)
	fmt.Println("Next steps:")
	fmt.Printf("  cd %s\n", name)
	fmt.Println("  cp .env.example .env       # add your API keys")
	fmt.Println("  bui dev                    # start dev server")
	fmt.Println()
	fmt.Println("For production:")
	fmt.Println("  bui neon setup             # provision database + auth")
	fmt.Println("  bui deploy                 # build + deploy to Modal")
	return nil
}

func writeFile(path, content string) {
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "warn: write %s: %v\n", path, err)
	}
}
