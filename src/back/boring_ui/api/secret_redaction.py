"""Secret redaction for logs and browser-facing errors.

Ensures that internal auth tokens, API keys, session secrets, and
provider credentials never leak to browser-facing error responses
or log output.

Usage:
    redactor = SecretRedactor()
    redactor.register('my-api-token-value')
    safe_message = redactor.redact('Error with token my-api-token-value')
    # -> 'Error with token [REDACTED]'
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Minimum secret length to register (avoid redacting short common strings).
MIN_SECRET_LENGTH = 8

# Patterns that look like secrets even if not explicitly registered.
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Bearer tokens
    re.compile(r'Bearer\s+[A-Za-z0-9._~+/=-]{20,}'),
    # HMAC auth tokens (our internal format)
    re.compile(r'hmac-sha256:[0-9]+:[a-f0-9]{64}'),
    # Generic hex tokens (32+ chars)
    re.compile(r'\b[a-f0-9]{32,}\b'),
    # Base64-encoded strings that look like tokens (40+ chars)
    re.compile(r'\b[A-Za-z0-9+/]{40,}={0,2}\b'),
    # AWS-style keys
    re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    # GitHub tokens
    re.compile(r'\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}\b'),
)

REDACTED = '[REDACTED]'


class SecretRedactor:
    """Thread-safe secret redactor for log and error messages.

    Register known secret values at startup. The redactor will replace
    any occurrence of these values (and pattern-matched secrets) with
    [REDACTED] in any string passed to redact().
    """

    def __init__(self, *, enable_pattern_matching: bool = True) -> None:
        self._secrets: set[str] = set()
        self._enable_patterns = enable_pattern_matching

    def register(self, secret: str) -> None:
        """Register a secret value for redaction.

        Secrets shorter than MIN_SECRET_LENGTH are ignored to avoid
        over-redaction of common short strings.
        """
        if not secret or len(secret) < MIN_SECRET_LENGTH:
            return
        self._secrets.add(secret)

    def register_many(self, secrets: list[str]) -> None:
        """Register multiple secret values."""
        for s in secrets:
            self.register(s)

    def redact(self, text: str) -> str:
        """Redact all known secrets and pattern-matched secrets from text."""
        if not text:
            return text

        result = text

        # First: redact explicitly registered secrets (longest first
        # to avoid partial matches).
        for secret in sorted(self._secrets, key=len, reverse=True):
            if secret in result:
                result = result.replace(secret, REDACTED)

        # Second: redact pattern-matched secrets.
        if self._enable_patterns:
            for pattern in SECRET_PATTERNS:
                result = pattern.sub(REDACTED, result)

        return result

    def is_clean(self, text: str) -> bool:
        """Check if text contains any known or pattern-matched secrets."""
        return self.redact(text) == text

    @property
    def registered_count(self) -> int:
        """Number of explicitly registered secrets."""
        return len(self._secrets)


@dataclass(frozen=True)
class SafeErrorResponse:
    """A browser-safe error response with all secrets redacted."""
    status_code: int
    detail: str
    error_id: str = ''


def create_safe_error(
    status_code: int,
    detail: str,
    redactor: SecretRedactor,
    *,
    error_id: str = '',
) -> SafeErrorResponse:
    """Create a browser-safe error response with redacted detail.

    Args:
        status_code: HTTP status code.
        detail: Error detail message (may contain secrets).
        redactor: Secret redactor instance.
        error_id: Optional error ID for correlation.

    Returns:
        SafeErrorResponse with redacted detail.
    """
    return SafeErrorResponse(
        status_code=status_code,
        detail=redactor.redact(detail),
        error_id=error_id,
    )


class RedactingFilter(logging.Filter):
    """Logging filter that redacts secrets from log records.

    Attach to a logger or handler to ensure secrets never appear
    in log output.

    Usage:
        redactor = SecretRedactor()
        redactor.register('my-secret')
        handler.addFilter(RedactingFilter(redactor))
    """

    def __init__(self, redactor: SecretRedactor, name: str = ''):
        super().__init__(name)
        self.redactor = redactor

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redactor.redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self.redactor.redact(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self.redactor.redact(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )
        return True
