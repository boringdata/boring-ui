"""Input sanitization for user-controlled values reaching shell or external services.

All public helpers raise ``ValueError`` on invalid input so callers
can translate to HTTP 400 at the API boundary.
"""
import re
import shlex

# ---------- repo URL ----------

_ALLOWED_URL_SCHEMES = {"https", "http", "ssh", "git"}

# Characters that are never valid in a repo URL and could be shell metacharacters
_URL_DANGEROUS_RE = re.compile(r"[\n\r\x00;|&$`\\'\"]")

MAX_URL_LENGTH = 2048


def sanitize_repo_url(url: str) -> str:
    """Validate and return a safe repository URL.

    Allows ``https://``, ``http://``, ``ssh://``, ``git://`` schemes.
    Rejects shell metacharacters, newlines, and null bytes.

    Raises:
        ValueError: on empty, too-long, disallowed-scheme, or dangerous-character input.
    """
    if not url or not url.strip():
        raise ValueError("Repository URL must not be empty")

    url = url.strip()

    if len(url) > MAX_URL_LENGTH:
        raise ValueError(f"Repository URL exceeds {MAX_URL_LENGTH} characters")

    if _URL_DANGEROUS_RE.search(url):
        raise ValueError("Repository URL contains disallowed characters")

    # Extract scheme
    scheme_match = re.match(r"^([a-zA-Z][a-zA-Z0-9+\-.]*):\/\/", url)
    if not scheme_match:
        # Allow git@host:path shorthand (SSH)
        if re.match(r"^[a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+:", url):
            return url
        raise ValueError(f"Repository URL has no recognized scheme: {url!r}")

    scheme = scheme_match.group(1).lower()
    if scheme not in _ALLOWED_URL_SCHEMES:
        raise ValueError(f"Disallowed URL scheme: {scheme!r}")

    return url


# ---------- git ref / branch ----------

# Git ref allowlist: alphanumeric, hyphen, underscore, dot, forward-slash
_GIT_REF_RE = re.compile(r"^[a-zA-Z0-9._/\-]+$")
MAX_GIT_REF_LENGTH = 256


def sanitize_git_ref(ref: str, *, label: str = "Git ref") -> str:
    """Validate a git branch name or ref.

    Rejects ``..``, leading/trailing dots or slashes, and non-allowlist
    characters.

    Raises:
        ValueError: on invalid ref.
    """
    if not ref or not ref.strip():
        raise ValueError(f"{label} must not be empty")

    ref = ref.strip()

    if len(ref) > MAX_GIT_REF_LENGTH:
        raise ValueError(f"{label} exceeds {MAX_GIT_REF_LENGTH} characters")

    if ".." in ref:
        raise ValueError(f"{label} must not contain '..'")

    if ref.startswith(".") or ref.endswith("."):
        raise ValueError(f"{label} must not start or end with '.'")

    if ref.startswith("/") or ref.endswith("/"):
        raise ValueError(f"{label} must not start or end with '/'")

    if ref.endswith(".lock"):
        raise ValueError(f"{label} must not end with '.lock'")

    if not _GIT_REF_RE.match(ref):
        raise ValueError(f"{label} contains disallowed characters")

    return ref


def sanitize_branch(branch: str) -> str:
    """Convenience wrapper for branch names."""
    return sanitize_git_ref(branch, label="Branch name")


# ---------- shell quoting ----------


def quote_for_shell(value: str) -> str:
    """Return a shell-safe quoted form of *value* via ``shlex.quote``."""
    return shlex.quote(value)
