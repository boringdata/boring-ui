package cmd

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/boringdata/boring-ui/bui/config"
	"github.com/spf13/cobra"
)

var upgradeCmd = &cobra.Command{
	Use:   "upgrade",
	Short: "Update [framework].commit to latest boring-ui main",
	RunE: func(cmd *cobra.Command, args []string) error {
		cfg, root := config.MustLoad()

		// Find boring-ui repo
		sibling := filepath.Join(filepath.Dir(root), "boring-ui")
		repoPath := sibling

		if _, err := os.Stat(filepath.Join(sibling, ".git")); err != nil {
			return fmt.Errorf("../boring-ui not found — can't determine latest commit")
		}

		// Fetch latest
		fmt.Println("[bui] fetching latest boring-ui...")
		fetch := exec.Command("git", "fetch", "origin")
		fetch.Dir = repoPath
		fetch.Stdout = os.Stdout
		fetch.Stderr = os.Stderr
		if err := fetch.Run(); err != nil {
			return fmt.Errorf("git fetch: %w", err)
		}

		// Get HEAD of main
		head := exec.Command("git", "rev-parse", "origin/main")
		head.Dir = repoPath
		out, err := head.Output()
		if err != nil {
			return fmt.Errorf("git rev-parse: %w", err)
		}
		newCommit := strings.TrimSpace(string(out))
		shortCommit := newCommit[:7]

		oldCommit := cfg.Framework.Commit
		oldShort := oldCommit
		if len(oldShort) > 7 {
			oldShort = oldShort[:7]
		}

		if strings.HasPrefix(newCommit, oldCommit) || strings.HasPrefix(oldCommit, newCommit) {
			fmt.Printf("[bui] already up to date: %s\n", shortCommit)
			return nil
		}

		// Update boring.app.toml
		tomlPath := filepath.Join(root, config.ConfigFile)
		data, err := os.ReadFile(tomlPath)
		if err != nil {
			return err
		}

		content := string(data)
		if oldCommit != "" {
			content = strings.Replace(content, oldCommit, newCommit, 1)
		} else {
			// No commit was set — can't auto-replace
			fmt.Printf("[bui] Set [framework].commit = %q in boring.app.toml\n", newCommit)
			return nil
		}

		if err := os.WriteFile(tomlPath, []byte(content), 0o644); err != nil {
			return err
		}

		fmt.Printf("[bui] upgraded: %s → %s\n", oldShort, shortCommit)
		return nil
	},
}
