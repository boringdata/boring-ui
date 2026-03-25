package cmd

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/boringdata/boring-ui/bui/config"
	"github.com/boringdata/boring-ui/bui/framework"
	"github.com/spf13/cobra"
)

var buildCmd = &cobra.Command{
	Use:   "build",
	Short: "Build frontend (vite build → dist/web/)",
	RunE: func(cmd *cobra.Command, args []string) error {
		cfg, root := config.MustLoad()
		fwPath, err := framework.Resolve(cfg, "dev")
		if err != nil {
			return fmt.Errorf("resolve framework: %w", err)
		}

		outDir := filepath.Join(root, "dist", "web")

		fmt.Printf("[bui] building %s → %s\n", cfg.App.Name, outDir)

		vite := exec.Command("npx", "vite", "build", "--outDir", outDir)
		vite.Dir = fwPath
		vite.Stdout = os.Stdout
		vite.Stderr = os.Stderr
		vite.Env = append(os.Environ(),
			fmt.Sprintf("BUI_APP_TOML=%s", filepath.Join(root, config.ConfigFile)),
		)

		if err := vite.Run(); err != nil {
			return fmt.Errorf("vite build: %w", err)
		}

		// TypeScript backend: also run type-check
		bt := strings.TrimSpace(strings.ToLower(cfg.Backend.Type))
		if bt == "typescript" || bt == "ts" {
			fmt.Println("[bui] type-checking server...")
			tsc := exec.Command("npx", "tsc", "--noEmit", "--project", "tsconfig.server.json")
			tsc.Dir = root
			tsc.Stdout = os.Stdout
			tsc.Stderr = os.Stderr
			if err := tsc.Run(); err != nil {
				return fmt.Errorf("tsc: %w", err)
			}
		}

		fmt.Printf("[bui] build complete: %s\n", outDir)
		return nil
	},
}
