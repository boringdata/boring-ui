package cmd

import (
	"github.com/spf13/cobra"
)

var rootCmd = &cobra.Command{
	Use:   "bui",
	Short: "boring-ui framework CLI",
	Long: `bui manages boring-ui child apps from a single boring.app.toml config.

Run 'bui docs' for detailed guides on setup, deploy, and auth.`,
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
