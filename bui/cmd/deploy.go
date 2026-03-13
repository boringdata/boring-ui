package cmd

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/boringdata/boring-ui/bui/config"
	"github.com/boringdata/boring-ui/bui/framework"
	vaultpkg "github.com/boringdata/boring-ui/bui/vault"
	"github.com/spf13/cobra"
)

var (
	deploySkipBuild bool
	deployEnv       string
)

var deployCmd = &cobra.Command{
	Use:   "deploy",
	Short: "Build frontend, resolve secrets, deploy to Modal",
	Long: `Build frontend, resolve Vault secrets, deploy to Modal.
Use --env to target staging/dev (separate Vault path + Modal app name).

Run 'bui docs deploy' for the full deploy workflow.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		cfg, root := config.MustLoad()
		if deployEnv != "" {
			cfg.Deploy.Env = deployEnv
		}

		// 1. Safety: warn if local boring-ui differs from pin
		checkFrameworkDrift(cfg)

		// 2. Build frontend
		if !deploySkipBuild {
			fmt.Println("[bui] building frontend...")
			if err := buildFrontend(cfg, root); err != nil {
				return fmt.Errorf("build: %w", err)
			}
		}

		// 3. Resolve secrets from Vault (best-effort, fallbacks below)
		fmt.Println("[bui] resolving secrets from Vault...")
		secrets, failed := vaultpkg.ResolveSecrets(cfg.Deploy.Secrets)
		for k := range secrets {
			fmt.Printf("  ✓ %s\n", k)
		}
		for _, k := range failed {
			fmt.Printf("  ✗ %s (Vault failed)\n", k)
		}

		// 4. Inject Neon config values from boring.app.toml (non-secret URLs)
		if cfg.Deploy.Neon.AuthURL != "" {
			secrets["NEON_AUTH_BASE_URL"] = cfg.Deploy.Neon.AuthURL
			fmt.Println("  ✓ NEON_AUTH_BASE_URL (from config)")
		}
		if cfg.Deploy.Neon.JWKSURL != "" {
			secrets["NEON_AUTH_JWKS_URL"] = cfg.Deploy.Neon.JWKSURL
			fmt.Println("  ✓ NEON_AUTH_JWKS_URL (from config)")
		}

		// 5. Fallbacks from .boring/neon-config.env for secrets that failed Vault
		if _, ok := secrets["DATABASE_URL"]; !ok {
			if dbURL := loadNeonEnvField(root, "DATABASE_POOLER_URL"); dbURL != "" {
				secrets["DATABASE_URL"] = dbURL
				fmt.Println("  ✓ DATABASE_URL (from .boring/neon-config.env)")
			}
		}
		if _, ok := secrets["BORING_UI_SESSION_SECRET"]; !ok {
			if ss := loadNeonEnvField(root, "BORING_UI_SESSION_SECRET"); ss != "" {
				secrets["BORING_UI_SESSION_SECRET"] = ss
				fmt.Println("  ✓ BORING_UI_SESSION_SECRET (from .boring/neon-config.env)")
			} else {
				secret, err := ensureSessionSecret(root)
				if err != nil {
					return fmt.Errorf("session secret: %w", err)
				}
				secrets["BORING_UI_SESSION_SECRET"] = secret
				fmt.Println("  ✓ BORING_UI_SESSION_SECRET (generated)")
			}
		}

		// 5b. Fallback for BORING_SETTINGS_KEY (encryption for workspace settings + GitHub connection)
		if _, ok := secrets["BORING_SETTINGS_KEY"]; !ok {
			if sk := loadNeonEnvField(root, "BORING_SETTINGS_KEY"); sk != "" {
				secrets["BORING_SETTINGS_KEY"] = sk
				fmt.Println("  ✓ BORING_SETTINGS_KEY (from .boring/neon-config.env)")
			} else {
				sk, err := ensureSettingsKey(root)
				if err != nil {
					return fmt.Errorf("settings key: %w", err)
				}
				secrets["BORING_SETTINGS_KEY"] = sk
				fmt.Println("  ✓ BORING_SETTINGS_KEY (generated)")
			}
		}

		// Check that all declared secrets were resolved
		if len(failed) > 0 {
			fmt.Printf("[bui] warn: %d secret(s) unresolved: %s\n", len(failed), strings.Join(failed, ", "))
		}

		// 6. Find modal_app.py
		modalFile := findModalFile(root)
		if modalFile == "" {
			return fmt.Errorf("no modal_app.py found in deploy/")
		}
		fmt.Printf("[bui] using %s\n", modalFile)

		// 7. Deploy (env-aware app naming)
		modalAppName := cfg.Deploy.Modal.AppName
		if modalAppName == "" {
			modalAppName = cfg.App.Name
		}
		if cfg.Deploy.Env != "" && cfg.Deploy.Env != "prod" {
			modalAppName = modalAppName + "-" + cfg.Deploy.Env
		}

		fmt.Printf("[bui] deploying %s (env=%s)...\n", modalAppName, cfg.Deploy.Env)
		modal := exec.Command("modal", "deploy", modalFile)
		modal.Dir = root
		modal.Stdout = os.Stdout
		modal.Stderr = os.Stderr

		// Inject resolved secrets as env vars (reject null bytes)
		modal.Env = os.Environ()
		for k, v := range secrets {
			if strings.Contains(v, "\x00") {
				return fmt.Errorf("secret %s contains null byte — cannot inject as env var", k)
			}
			modal.Env = append(modal.Env, k+"="+v)
		}
		// Resolve framework path for modal_app.py to mount
		fwPath, _ := framework.Resolve(cfg, "deploy")
		if fwPath == "" {
			// Fallback: try dev resolution (sibling)
			fwPath, _ = framework.Resolve(cfg, "dev")
		}

		// Pass config path, app name, and framework path so modal_app.py can use them
		modal.Env = append(modal.Env,
			fmt.Sprintf("BUI_APP_TOML=%s", filepath.Join(root, config.ConfigFile)),
			fmt.Sprintf("BUI_MODAL_APP_NAME=%s", modalAppName),
			fmt.Sprintf("BUI_DEPLOY_ENV=%s", cfg.Deploy.Env),
		)
		if fwPath != "" {
			modal.Env = append(modal.Env, fmt.Sprintf("BUI_FRAMEWORK_PATH=%s", fwPath))
			fmt.Printf("[bui] framework: %s\n", fwPath)
		}

		if err := modal.Run(); err != nil {
			return fmt.Errorf("modal deploy: %w", err)
		}

		fmt.Println("[bui] deploy complete")
		return nil
	},
}

// ensureSessionSecret reads or creates a stable session secret in .boring/session-secret.
func ensureSessionSecret(root string) (string, error) {
	boringDir := filepath.Join(root, ".boring")
	secretFile := filepath.Join(boringDir, "session-secret")

	data, err := os.ReadFile(secretFile)
	if err == nil {
		s := strings.TrimSpace(string(data))
		if len(s) >= 32 {
			return s, nil
		}
	}

	// Generate new secret
	buf := make([]byte, 32)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	secret := hex.EncodeToString(buf)

	os.MkdirAll(boringDir, 0o700)
	if err := os.WriteFile(secretFile, []byte(secret+"\n"), 0o600); err != nil {
		return "", err
	}
	fmt.Printf("[bui] generated new session secret → %s\n", secretFile)
	return secret, nil
}

// ensureSettingsKey reads or creates a stable settings encryption key in .boring/settings-key.
func ensureSettingsKey(root string) (string, error) {
	boringDir := filepath.Join(root, ".boring")
	keyFile := filepath.Join(boringDir, "settings-key")

	data, err := os.ReadFile(keyFile)
	if err == nil {
		s := strings.TrimSpace(string(data))
		if len(s) >= 32 {
			return s, nil
		}
	}

	// Generate new key
	buf := make([]byte, 32)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	key := hex.EncodeToString(buf)

	os.MkdirAll(boringDir, 0o700)
	if err := os.WriteFile(keyFile, []byte(key+"\n"), 0o600); err != nil {
		return "", err
	}
	fmt.Printf("[bui] generated new settings key → %s\n", keyFile)
	return key, nil
}

func init() {
	deployCmd.Flags().BoolVar(&deploySkipBuild, "skip-build", false, "Skip frontend build")
	deployCmd.Flags().StringVar(&deployEnv, "env", "", "Override deploy environment (default from config)")
}

func checkFrameworkDrift(cfg *config.AppConfig) {
	fwPath, _ := framework.Resolve(cfg, "dev")
	if fwPath == "" || cfg.Framework.Commit == "" {
		return
	}
	cmd := exec.Command("git", "rev-parse", "HEAD")
	cmd.Dir = fwPath
	out, err := cmd.Output()
	if err != nil {
		return
	}
	head := strings.TrimSpace(string(out))
	pin := cfg.Framework.Commit
	if !strings.HasPrefix(head, pin) && !strings.HasPrefix(pin, head) {
		short := pin
		if len(short) > 7 {
			short = short[:7]
		}
		fmt.Printf("[bui] WARN: ../boring-ui HEAD=%s, config pins %s. Run `bui upgrade`?\n", head[:7], short)
	}
}

func buildFrontend(cfg *config.AppConfig, root string) error {
	fwPath, err := framework.Resolve(cfg, "dev")
	if err != nil {
		return err
	}

	// Build dir: frontend root if set, otherwise framework path
	buildDir := fwPath
	if cfg.Frontend.Root != "" {
		buildDir = filepath.Join(root, cfg.Frontend.Root)
		// Ensure boring-ui symlink exists for the build
		if err := framework.LinkFrontend(fwPath, buildDir); err != nil {
			fmt.Printf("[bui] warn: frontend symlink: %v\n", err)
		}
	}

	outDir := filepath.Join(root, "dist", "web")
	vite := exec.Command("npx", "vite", "build", "--outDir", outDir)
	vite.Dir = buildDir
	vite.Stdout = os.Stdout
	vite.Stderr = os.Stderr
	vite.Env = append(os.Environ(),
		fmt.Sprintf("BUI_APP_TOML=%s", filepath.Join(root, config.ConfigFile)),
	)
	return vite.Run()
}

// loadNeonEnvField reads a field from .boring/neon-config.env (fallback when Vault is unavailable).
func loadNeonEnvField(root, key string) string {
	data, err := os.ReadFile(filepath.Join(root, ".boring", "neon-config.env"))
	if err != nil {
		return ""
	}
	for _, line := range strings.Split(string(data), "\n") {
		if strings.HasPrefix(line, key+"=") {
			return strings.TrimPrefix(line, key+"=")
		}
	}
	return ""
}

func findModalFile(root string) string {
	// Check common locations
	candidates := []string{
		filepath.Join(root, "deploy", "modal_app.py"),
		filepath.Join(root, "deploy", "core", "modal_app.py"),
		filepath.Join(root, "deploy", "edge", "modal_app.py"),
		filepath.Join(root, "modal_app.py"),
	}
	for _, c := range candidates {
		if _, err := os.Stat(c); err == nil {
			return c
		}
	}
	return ""
}
