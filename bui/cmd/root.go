package cmd

import (
	"github.com/spf13/cobra"
)

var rootCmd = &cobra.Command{
	Use:   "bui",
	Short: "boring-ui framework CLI",
	Long: `bui manages boring-ui child apps from a single boring.app.toml config.

Quick start (create → deploy a new app):
  bui docs quickstart         Full autonomous walkthrough

Common workflow:
  bui init <name>             Scaffold a new child app
  bui dev                     Start dev server (auto-detects framework)
  bui doctor                  Validate project config
  bui neon setup              Provision database + auth (production)
  bui deploy                  Build + resolve secrets + deploy to Fly

All guides:
  bui docs                    List all documentation topics
  bui docs quickstart         End-to-end: init → deploy (start here)
  bui docs config             boring.app.toml reference`,
}

func Execute() error {
	return rootCmd.Execute()
}

func init() {
	rootCmd.AddCommand(devCmd)
	rootCmd.AddCommand(buildCmd)
	rootCmd.AddCommand(deployCmd)
	rootCmd.AddCommand(neonCmd)
	rootCmd.AddCommand(statusCmd)
	rootCmd.AddCommand(runCmd)
	rootCmd.AddCommand(infoCmd)
	rootCmd.AddCommand(upgradeCmd)
	// doctorCmd registers itself in doctor.go init()
}
