// Package vault resolves secrets from HashiCorp Vault.
package vault

import (
	"fmt"
	"os/exec"
	"strings"

	"github.com/boringdata/boring-ui/bui/config"
)

// ResolveSecrets resolves all secrets from Vault, returning resolved values
// and a list of names that failed (instead of aborting on first error).
func ResolveSecrets(secrets map[string]config.SecretRef) (resolved map[string]string, failed []string) {
	resolved = make(map[string]string, len(secrets))

	for name, ref := range secrets {
		val, err := Get(ref.Vault, ref.Field)
		if err != nil {
			failed = append(failed, name)
			continue
		}
		resolved[name] = val
	}

	return resolved, failed
}

// Get fetches a single field from a Vault KV path.
func Get(path, field string) (string, error) {
	args := []string{"kv", "get", "-field", field, path}
	out, err := exec.Command("vault", args...).Output()
	if err != nil {
		return "", fmt.Errorf("vault kv get -field %s %s: %w", field, path, err)
	}
	return strings.TrimSpace(string(out)), nil
}

// Put writes key=value pairs to a Vault KV path.
func Put(path string, data map[string]string) error {
	args := []string{"kv", "put", path}
	for k, v := range data {
		args = append(args, k+"="+v)
	}
	cmd := exec.Command("vault", args...)
	_, err := cmd.CombinedOutput()
	if err != nil {
		// Don't include output — it may echo secret values
		return fmt.Errorf("vault kv put %s: %w", path, err)
	}
	return nil
}

// Delete removes a Vault KV path.
func Delete(path string) error {
	cmd := exec.Command("vault", "kv", "delete", path)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("vault kv delete %s: %w\n%s", path, err, string(out))
	}
	return nil
}
