package main

import (
	"fmt"
	"os"

	"github.com/boringdata/boring-ui/bui/cmd"
)

func main() {
	if err := cmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
