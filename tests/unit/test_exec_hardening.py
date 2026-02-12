"""Tests for exec hardening: env sanitization, output limits, secret masking,
network egress controls (bd-1pwb.8.2, bd-1pwb.8.3)."""

import pytest
from boring_ui.api.modules.sandbox.policy import (
    sanitize_exec_env,
    mask_secrets,
    truncate_output,
    SandboxPolicies,
    NetworkEgressPolicy,
    SENSITIVE_ENV_PREFIXES,
    SENSITIVE_ENV_EXACT,
    PROXY_ENV_VARS,
)


class TestSanitizeExecEnv:
    """Tests for child process environment sanitization."""

    def test_strips_anthropic_api_key(self):
        env = {"ANTHROPIC_API_KEY": "sk-ant-secret", "PATH": "/usr/bin"}
        result = sanitize_exec_env(env)
        assert "ANTHROPIC_API_KEY" not in result
        assert result["PATH"] == "/usr/bin"

    def test_strips_vault_token(self):
        env = {"VAULT_TOKEN": "hvs.secret", "VAULT_ADDR": "http://vault:8200", "HOME": "/home/user"}
        result = sanitize_exec_env(env)
        assert "VAULT_TOKEN" not in result
        assert "VAULT_ADDR" not in result
        assert result["HOME"] == "/home/user"

    def test_strips_service_auth_secret(self):
        env = {"SERVICE_AUTH_SECRET": "hex-key", "USER": "ubuntu"}
        result = sanitize_exec_env(env)
        assert "SERVICE_AUTH_SECRET" not in result
        assert result["USER"] == "ubuntu"

    def test_strips_oidc_variables(self):
        env = {"OIDC_ISSUER": "https://idp", "OIDC_AUDIENCE": "api", "TERM": "xterm"}
        result = sanitize_exec_env(env)
        assert "OIDC_ISSUER" not in result
        assert "OIDC_AUDIENCE" not in result
        assert result["TERM"] == "xterm"

    def test_strips_hosted_api_token(self):
        env = {"HOSTED_API_TOKEN": "bearer-token", "LANG": "en_US.UTF-8"}
        result = sanitize_exec_env(env)
        assert "HOSTED_API_TOKEN" not in result
        assert result["LANG"] == "en_US.UTF-8"

    def test_strips_openai_key(self):
        env = {"OPENAI_API_KEY": "sk-openai-secret", "PWD": "/workspace"}
        result = sanitize_exec_env(env)
        assert "OPENAI_API_KEY" not in result
        assert result["PWD"] == "/workspace"

    def test_strips_signing_key(self):
        env = {"SIGNING_KEY_HEX": "deadbeef", "SHELL": "/bin/bash"}
        result = sanitize_exec_env(env)
        assert "SIGNING_KEY_HEX" not in result
        assert result["SHELL"] == "/bin/bash"

    def test_strips_database_url(self):
        env = {"DATABASE_URL": "postgres://user:pass@host/db", "NODE_ENV": "production"}
        result = sanitize_exec_env(env)
        assert "DATABASE_URL" not in result
        assert result["NODE_ENV"] == "production"

    def test_preserves_safe_variables(self):
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/home/user",
            "USER": "ubuntu",
            "TERM": "xterm-256color",
            "LANG": "en_US.UTF-8",
            "PWD": "/workspace",
            "SHELL": "/bin/bash",
            "NODE_ENV": "production",
        }
        result = sanitize_exec_env(env)
        assert result == env

    def test_case_insensitive_prefix_match(self):
        env = {"anthropic_api_key": "secret", "Vault_Token": "hvs.x", "PATH": "/bin"}
        result = sanitize_exec_env(env)
        assert "anthropic_api_key" not in result
        assert "Vault_Token" not in result
        assert result["PATH"] == "/bin"

    def test_empty_env(self):
        result = sanitize_exec_env({})
        assert result == {}

    def test_returns_copy_not_reference(self):
        env = {"PATH": "/usr/bin"}
        result = sanitize_exec_env(env)
        result["EXTRA"] = "value"
        assert "EXTRA" not in env


class TestMaskSecrets:
    """Tests for secret masking in command output."""

    def test_masks_anthropic_api_key(self):
        text = "Found key: sk-ant-abcdefghijklmnopqrstuvwxyz1234"
        result = mask_secrets(text)
        assert "sk-ant-" not in result
        assert "[REDACTED]" in result

    def test_masks_sk_prefix_key(self):
        text = "API_KEY=sk-abcdefghijklmnopqrstuvwxyz"
        result = mask_secrets(text)
        assert "sk-abc" not in result
        assert "[REDACTED]" in result

    def test_masks_vault_token(self):
        text = "export VAULT_TOKEN=hvs.CAESIAuabcdefghijklmnopqr"
        result = mask_secrets(text)
        assert "hvs." not in result
        assert "[REDACTED]" in result

    def test_masks_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"
        result = mask_secrets(text)
        assert "eyJhbGci" not in result
        assert "[REDACTED]" in result

    def test_masks_long_hex_string(self):
        hex_key = "a" * 64
        text = f"signing_key={hex_key}"
        result = mask_secrets(text)
        assert hex_key not in result
        assert "[REDACTED]" in result

    def test_preserves_normal_text(self):
        text = "Hello world, this is normal output with no secrets"
        result = mask_secrets(text)
        assert result == text

    def test_preserves_short_hex(self):
        text = "commit abc123def456"
        result = mask_secrets(text)
        assert result == text

    def test_empty_string(self):
        assert mask_secrets("") == ""

    def test_none_passthrough(self):
        assert mask_secrets(None) is None

    def test_multiple_secrets_in_one_line(self):
        text = "key1=sk-abcdefghijklmnopqrstuvwxyz key2=hvs.abcdefghijklmnopqrstuvwxyz"
        result = mask_secrets(text)
        assert "sk-abc" not in result
        assert "hvs." not in result
        assert result.count("[REDACTED]") >= 2


class TestTruncateOutput:
    """Tests for output line truncation."""

    def test_truncates_beyond_limit(self):
        lines = "\n".join(f"line {i}" for i in range(100))
        result, was_truncated = truncate_output(lines, 50)
        assert was_truncated is True
        result_lines = result.split("\n")
        assert result_lines[0] == "line 0"
        assert result_lines[49] == "line 49"
        assert "50 lines omitted" in result_lines[-1]

    def test_no_truncation_under_limit(self):
        lines = "\n".join(f"line {i}" for i in range(10))
        result, was_truncated = truncate_output(lines, 50)
        assert was_truncated is False
        assert result == lines

    def test_exact_limit_no_truncation(self):
        lines = "\n".join(f"line {i}" for i in range(50))
        result, was_truncated = truncate_output(lines, 50)
        assert was_truncated is False
        assert result == lines

    def test_empty_string(self):
        result, was_truncated = truncate_output("", 50)
        assert was_truncated is False
        assert result == ""

    def test_none_passthrough(self):
        result, was_truncated = truncate_output(None, 50)
        assert was_truncated is False
        assert result is None

    def test_single_line_no_truncation(self):
        result, was_truncated = truncate_output("hello", 50)
        assert was_truncated is False
        assert result == "hello"

    def test_truncation_message_includes_count(self):
        lines = "\n".join(f"line {i}" for i in range(200))
        result, was_truncated = truncate_output(lines, 100)
        assert was_truncated is True
        assert "100 lines omitted" in result

    def test_policy_default_limit(self):
        """Resource limits match expected defaults."""
        policies = SandboxPolicies()
        limits = policies.get_resource_limits()
        assert limits["max_output_lines"] == 10000


class TestSensitiveEnvCoverage:
    """Verify sensitive env lists cover critical control-plane secrets."""

    def test_all_critical_prefixes_covered(self):
        critical = ["ANTHROPIC_", "OPENAI_", "VAULT_", "SERVICE_AUTH_", "OIDC_", "HOSTED_API_"]
        for prefix in critical:
            assert prefix in SENSITIVE_ENV_PREFIXES, f"Missing prefix: {prefix}"

    def test_all_critical_exact_matches_covered(self):
        critical = ["VAULT_TOKEN", "SERVICE_AUTH_SECRET", "HOSTED_API_TOKEN", "DATABASE_URL", "SECRET_KEY"]
        for var in critical:
            assert var in SENSITIVE_ENV_EXACT, f"Missing exact match: {var}"


# --- Network egress controls (bd-1pwb.8.3) ---

class TestNetworkEgressPolicy:
    """Tests for network egress policy enforcement."""

    def test_default_policy_is_workspace_only(self):
        p = SandboxPolicies()
        assert p.network_egress_policy == NetworkEgressPolicy.WORKSPACE_ONLY

    def test_workspace_only_allows_safe_commands(self):
        p = SandboxPolicies()
        assert p.allow_network_command("ls -la") is True
        assert p.allow_network_command("git status") is True
        assert p.allow_network_command("npm install") is True
        assert p.allow_network_command("python script.py") is True
        assert p.allow_network_command("pip install requests") is True

    def test_workspace_only_blocks_raw_network_tools(self):
        p = SandboxPolicies()
        assert p.allow_network_command("curl http://evil.com") is False
        assert p.allow_network_command("wget http://evil.com") is False
        assert p.allow_network_command("ssh user@host") is False
        assert p.allow_network_command("scp file user@host:") is False
        assert p.allow_network_command("nc -l 1234") is False
        assert p.allow_network_command("ncat host 80") is False
        assert p.allow_network_command("netcat host 80") is False
        assert p.allow_network_command("telnet host 25") is False
        assert p.allow_network_command("ftp ftp.example.com") is False
        assert p.allow_network_command("nmap 192.168.1.0/24") is False
        assert p.allow_network_command("ping 8.8.8.8") is False

    def test_deny_all_blocks_network_commands(self):
        p = SandboxPolicies(network_egress_policy=NetworkEgressPolicy.DENY_ALL)
        assert p.allow_network_command("curl http://x") is False
        assert p.allow_network_command("rsync -avz src/ dst/") is False
        assert p.allow_network_command("ssh host") is False

    def test_deny_all_allows_non_network_commands(self):
        p = SandboxPolicies(network_egress_policy=NetworkEgressPolicy.DENY_ALL)
        assert p.allow_network_command("ls") is True
        assert p.allow_network_command("cat file.txt") is True
        assert p.allow_network_command("git status") is True

    def test_allow_all_permits_everything(self):
        p = SandboxPolicies(network_egress_policy=NetworkEgressPolicy.ALLOW_ALL)
        assert p.allow_network_command("curl http://x") is True
        assert p.allow_network_command("wget http://x") is True
        assert p.allow_network_command("ssh user@host") is True
        assert p.allow_network_command("nmap 10.0.0.0/8") is True

    def test_allowlist_overrides_workspace_only(self):
        p = SandboxPolicies(egress_allowlist={"curl"})
        assert p.allow_network_command("curl http://api.internal") is True
        assert p.allow_network_command("wget http://evil.com") is False

    def test_allowlist_multiple_entries(self):
        p = SandboxPolicies(egress_allowlist={"curl", "rsync"})
        assert p.allow_network_command("curl http://api") is True
        assert p.allow_network_command("rsync -avz src/ dst/") is True
        assert p.allow_network_command("wget http://evil.com") is False

    def test_empty_command_allowed(self):
        p = SandboxPolicies()
        assert p.allow_network_command("") is True
        assert p.allow_network_command("   ") is True


class TestEgressPosture:
    """Tests for egress posture reporting."""

    def test_workspace_only_posture(self):
        p = SandboxPolicies()
        posture = p.get_egress_posture()
        assert posture["policy"] == "workspace_only"
        assert len(posture["blocked_commands"]) > 0
        assert "curl" in posture["blocked_commands"]
        assert posture["allowlist"] == []

    def test_allow_all_posture_no_blocked(self):
        p = SandboxPolicies(network_egress_policy=NetworkEgressPolicy.ALLOW_ALL)
        posture = p.get_egress_posture()
        assert posture["policy"] == "allow_all"
        assert posture["blocked_commands"] == []

    def test_deny_all_posture(self):
        p = SandboxPolicies(network_egress_policy=NetworkEgressPolicy.DENY_ALL)
        posture = p.get_egress_posture()
        assert posture["policy"] == "deny_all"
        assert len(posture["blocked_commands"]) > 0

    def test_posture_with_allowlist(self):
        p = SandboxPolicies(egress_allowlist={"curl", "wget"})
        posture = p.get_egress_posture()
        assert posture["allowlist"] == ["curl", "wget"]  # sorted


class TestProxyEnvStripping:
    """Tests for proxy environment variable stripping."""

    def test_strips_http_proxy(self):
        env = {"HTTP_PROXY": "http://proxy:8080", "PATH": "/bin"}
        result = sanitize_exec_env(env, strip_proxy=True)
        assert "HTTP_PROXY" not in result
        assert result["PATH"] == "/bin"

    def test_strips_https_proxy(self):
        env = {"HTTPS_PROXY": "http://proxy:8080", "HOME": "/home/user"}
        result = sanitize_exec_env(env, strip_proxy=True)
        assert "HTTPS_PROXY" not in result

    def test_strips_all_proxy_variants(self):
        env = {
            "HTTP_PROXY": "http://p:80",
            "HTTPS_PROXY": "http://p:80",
            "ALL_PROXY": "socks5://p:1080",
            "NO_PROXY": "localhost",
            "http_proxy": "http://p:80",
            "https_proxy": "http://p:80",
            "all_proxy": "socks5://p:1080",
            "no_proxy": "localhost",
            "PATH": "/bin",
        }
        result = sanitize_exec_env(env, strip_proxy=True)
        for proxy_var in PROXY_ENV_VARS:
            assert proxy_var not in result, f"{proxy_var} should be stripped"
        assert result["PATH"] == "/bin"

    def test_preserves_proxy_when_disabled(self):
        env = {"HTTP_PROXY": "http://proxy:8080", "PATH": "/bin"}
        result = sanitize_exec_env(env, strip_proxy=False)
        assert result["HTTP_PROXY"] == "http://proxy:8080"

    def test_default_strips_proxy(self):
        """Default behavior strips proxy vars."""
        env = {"HTTP_PROXY": "http://proxy:8080", "PATH": "/bin"}
        result = sanitize_exec_env(env)
        assert "HTTP_PROXY" not in result
