package cmd

import (
	"fmt"
	"net/http"
	"time"

	"github.com/boringdata/boring-ui/bui/config"
	vaultpkg "github.com/boringdata/boring-ui/bui/vault"
	"github.com/spf13/cobra"
)

var statusCmd = &cobra.Command{
	Use:   "status",
	Short: "Check if services are running",
	RunE: func(cmd *cobra.Command, args []string) error {
		cfg, _ := config.MustLoad()

		fmt.Printf("\n%s status\n\n", cfg.App.Name)

		client := &http.Client{Timeout: 2 * time.Second}

		// Backend
		backendURL := fmt.Sprintf("http://localhost:%d/health", cfg.Backend.Port)
		if resp, err := client.Get(backendURL); err == nil {
			resp.Body.Close()
			fmt.Printf("  ✓ Backend:  up (port %d)\n", cfg.Backend.Port)
		} else {
			fmt.Printf("  ✗ Backend:  down (port %d)\n", cfg.Backend.Port)
		}

		// Frontend
		frontendURL := fmt.Sprintf("http://localhost:%d", cfg.Frontend.Port)
		if resp, err := client.Get(frontendURL); err == nil {
			resp.Body.Close()
			fmt.Printf("  ✓ Frontend: up (port %d)\n", cfg.Frontend.Port)
		} else {
			fmt.Printf("  ✗ Frontend: down (port %d)\n", cfg.Frontend.Port)
		}

		// Capabilities (more detailed backend check)
		capURL := fmt.Sprintf("http://localhost:%d/api/capabilities", cfg.Backend.Port)
		if resp, err := client.Get(capURL); err == nil {
			resp.Body.Close()
			if resp.StatusCode == 200 {
				fmt.Printf("  ✓ API:      capabilities responding\n")
			} else {
				fmt.Printf("  ! API:      capabilities returned %d\n", resp.StatusCode)
			}
		}

		// Neon connectivity
		if cfg.Deploy.Neon.AuthURL != "" {
			if resp, err := client.Get(cfg.Deploy.Neon.AuthURL + "/ok"); err == nil {
				resp.Body.Close()
				if resp.StatusCode == 200 {
					fmt.Printf("  ✓ Neon Auth: reachable\n")
				} else {
					fmt.Printf("  ✗ Neon Auth: HTTP %d\n", resp.StatusCode)
				}
			} else {
				fmt.Printf("  ✗ Neon Auth: unreachable\n")
			}
		}
		if cfg.Deploy.Neon.Project != "" {
			_, root := config.MustLoad()
			dbURL, _ := vaultpkg.Get(cfg.AppVaultPath(), "database_url")
			if dbURL == "" {
				dbURL = loadNeonEnvField(root, "DATABASE_POOLER_URL")
			}
			if dbURL != "" {
				fmt.Printf("  ✓ Neon DB:   configured (%s)\n", maskPassword(dbURL))
			} else {
				fmt.Printf("  ✗ Neon DB:   no connection URL found\n")
			}
		}

		fmt.Println()
		return nil
	},
}
