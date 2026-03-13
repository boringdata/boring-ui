package cmd

import (
	"fmt"
	"os"
	"os/exec"
	"strings"

	"github.com/boringdata/boring-ui/bui/config"
	"github.com/spf13/cobra"
)

var runCmd = &cobra.Command{
	Use:   "run <command> [args...]",
	Short: "Execute a CLI command from [cli.commands]",
	Args:  cobra.MinimumNArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		cfg, root := config.MustLoad()

		name := args[0]
		command, ok := cfg.CLI.Commands[name]
		if !ok {
			fmt.Fprintf(os.Stderr, "Unknown command: %s\n\nAvailable commands:\n", name)
			for n, c := range cfg.CLI.Commands {
				fmt.Fprintf(os.Stderr, "  %-15s %s\n", n, c.Description)
			}
			return fmt.Errorf("command %q not found in [cli.commands]", name)
		}

		// Build the full command: base command + extra args
		parts := strings.Fields(command.Run)
		if len(args) > 1 {
			parts = append(parts, args[1:]...)
		}

		c := exec.Command(parts[0], parts[1:]...)
		c.Dir = root
		c.Stdin = os.Stdin
		c.Stdout = os.Stdout
		c.Stderr = os.Stderr

		// Load .env
		c.Env = os.Environ()
		for k, v := range loadDotEnv(root) {
			c.Env = append(c.Env, k+"="+v)
		}

		return c.Run()
	},
}
