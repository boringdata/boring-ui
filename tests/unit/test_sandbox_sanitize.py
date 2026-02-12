"""Tests for input sanitization utilities."""
import pytest

from boring_ui.api.modules.sandbox.sanitize import (
    quote_for_shell,
    sanitize_branch,
    sanitize_git_ref,
    sanitize_repo_url,
)


# ─────────────────────── sanitize_repo_url ───────────────────────


class TestSanitizeRepoUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/org/repo.git",
            "http://example.com/repo",
            "ssh://git@github.com/org/repo.git",
            "git://example.com/repo.git",
            "git@github.com:org/repo.git",
        ],
    )
    def test_valid_urls(self, url):
        assert sanitize_repo_url(url) == url

    def test_strips_whitespace(self):
        assert sanitize_repo_url("  https://x.com/r  ") == "https://x.com/r"

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="empty"):
            sanitize_repo_url("")

    def test_rejects_whitespace_only(self):
        with pytest.raises(ValueError, match="empty"):
            sanitize_repo_url("   ")

    def test_rejects_too_long(self):
        url = "https://example.com/" + "a" * 2100
        with pytest.raises(ValueError, match="exceeds"):
            sanitize_repo_url(url)

    @pytest.mark.parametrize(
        "bad_url",
        [
            "ftp://evil.com/repo",
            "file:///etc/passwd",
            "javascript://alert(1)",
        ],
    )
    def test_rejects_disallowed_schemes(self, bad_url):
        with pytest.raises(ValueError, match="scheme"):
            sanitize_repo_url(bad_url)

    @pytest.mark.parametrize(
        "malicious",
        [
            "https://example.com/repo;rm -rf /",
            "https://example.com/repo|cat /etc/passwd",
            "https://example.com/repo&whoami",
            "https://example.com/repo`id`",
            "https://example.com/repo$(id)",
            "https://example.com/repo\nwhoami",
            "https://example.com/repo\x00evil",
            "https://example.com/repo'DROP TABLE",
            'https://example.com/repo"--',
        ],
    )
    def test_rejects_shell_metacharacters(self, malicious):
        with pytest.raises(ValueError, match="disallowed"):
            sanitize_repo_url(malicious)

    def test_rejects_no_scheme(self):
        with pytest.raises(ValueError, match="scheme"):
            sanitize_repo_url("just-a-string")


# ─────────────────────── sanitize_git_ref ───────────────────────


class TestSanitizeGitRef:
    @pytest.mark.parametrize(
        "ref",
        [
            "main",
            "feature/add-login",
            "v1.0.0",
            "release-2026.01",
            "my_branch",
        ],
    )
    def test_valid_refs(self, ref):
        assert sanitize_git_ref(ref) == ref

    def test_strips_whitespace(self):
        assert sanitize_git_ref("  main  ") == "main"

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="empty"):
            sanitize_git_ref("")

    def test_rejects_too_long(self):
        ref = "a" * 257
        with pytest.raises(ValueError, match="exceeds"):
            sanitize_git_ref(ref)

    def test_rejects_double_dot(self):
        with pytest.raises(ValueError, match="\\.\\."):
            sanitize_git_ref("main..develop")

    def test_rejects_leading_dot(self):
        with pytest.raises(ValueError, match="start or end with '\\.'"):
            sanitize_git_ref(".hidden")

    def test_rejects_trailing_dot(self):
        with pytest.raises(ValueError, match="start or end with '\\.'"):
            sanitize_git_ref("branch.")

    def test_rejects_leading_slash(self):
        with pytest.raises(ValueError, match="start or end with '/'"):
            sanitize_git_ref("/branch")

    def test_rejects_trailing_slash(self):
        with pytest.raises(ValueError, match="start or end with '/'"):
            sanitize_git_ref("branch/")

    def test_rejects_dot_lock_suffix(self):
        with pytest.raises(ValueError, match="\\.lock"):
            sanitize_git_ref("branch.lock")

    @pytest.mark.parametrize(
        "bad_ref",
        [
            "branch name",
            "branch\ttab",
            "branch;evil",
            "branch|pipe",
            "branch&and",
            "branch$var",
            "branch`tick`",
            "brånch",
            "branch\x00null",
            "branch~1",
            "branch^2",
            "branch:ref",
        ],
    )
    def test_rejects_disallowed_characters(self, bad_ref):
        with pytest.raises(ValueError):
            sanitize_git_ref(bad_ref)

    def test_custom_label(self):
        with pytest.raises(ValueError, match="Tag name"):
            sanitize_git_ref("", label="Tag name")


# ─────────────────────── sanitize_branch ───────────────────────


class TestSanitizeBranch:
    def test_valid(self):
        assert sanitize_branch("feature/x") == "feature/x"

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Branch name"):
            sanitize_branch("")


# ─────────────────────── quote_for_shell ───────────────────────


class TestQuoteForShell:
    def test_simple_value(self):
        assert quote_for_shell("hello") == "hello"

    def test_value_with_spaces(self):
        result = quote_for_shell("hello world")
        assert "hello world" in result
        assert result.startswith("'") or result.startswith('"')

    def test_value_with_semicolon(self):
        result = quote_for_shell("a;b")
        # Must be quoted so shell doesn't interpret ;
        assert ";" in result
        assert result != "a;b"

    def test_value_with_single_quote(self):
        result = quote_for_shell("it's")
        # shlex.quote handles single quotes safely
        assert "it" in result
        assert "s" in result

    def test_empty_string(self):
        result = quote_for_shell("")
        assert result == "''"
