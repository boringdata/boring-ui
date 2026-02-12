"""Server-owned command template allowlist for exec sessions.

When launching PTY or chat sessions in sandbox mode, the control plane
must only execute vetted command templates. Clients request a session
by template ID (e.g., "shell", "claude"), never by raw command strings.

This module:
  1. Defines ExecTemplate with validated command/env/limits.
  2. Provides a registry of allowed templates (loaded from config).
  3. Validates template parameters before execution.
  4. Rejects any attempt to execute arbitrary commands.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Template IDs must be alphanumeric with hyphens/underscores.
TEMPLATE_ID_PATTERN = re.compile(r'^[a-z][a-z0-9_-]{0,63}$')

# Maximum allowed timeout for any exec session.
MAX_TIMEOUT_SECONDS = 86400  # 24 hours

# Maximum output buffer.
MAX_OUTPUT_BYTES = 10 * 1024 * 1024  # 10 MB


class ExecPolicyError(Exception):
    """Raised when an exec request violates policy."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f'Exec policy violation: {reason}')


@dataclass(frozen=True)
class ExecTemplate:
    """A vetted, server-owned command template for exec sessions.

    Templates are immutable once registered. Clients reference them
    by ID and cannot modify the command, env, or limits.
    """
    id: str
    description: str
    command: tuple[str, ...]
    working_directory: str = '/home/sprite/workspace'
    env: dict[str, str] = field(default_factory=lambda: {
        'TERM': 'xterm-256color',
    })
    timeout_seconds: int = 3600
    max_output_bytes: int = 204800


def validate_template_id(template_id: str) -> None:
    """Validate that a template ID is well-formed.

    Raises:
        ExecPolicyError: If ID is invalid.
    """
    if not template_id:
        raise ExecPolicyError('Template ID is required')
    if not TEMPLATE_ID_PATTERN.match(template_id):
        raise ExecPolicyError(
            f'Invalid template ID {template_id!r}: must match '
            f'{TEMPLATE_ID_PATTERN.pattern}'
        )


def validate_template(template: ExecTemplate) -> list[str]:
    """Validate a template's fields. Returns list of issues (empty if valid)."""
    issues: list[str] = []

    if not TEMPLATE_ID_PATTERN.match(template.id):
        issues.append(
            f'Template ID {template.id!r} does not match '
            f'{TEMPLATE_ID_PATTERN.pattern}'
        )

    if not template.command:
        issues.append(f'Template {template.id!r} has empty command')

    if template.timeout_seconds <= 0:
        issues.append(
            f'Template {template.id!r} timeout must be positive, '
            f'got {template.timeout_seconds}'
        )
    elif template.timeout_seconds > MAX_TIMEOUT_SECONDS:
        issues.append(
            f'Template {template.id!r} timeout {template.timeout_seconds}s '
            f'exceeds max {MAX_TIMEOUT_SECONDS}s'
        )

    if template.max_output_bytes <= 0:
        issues.append(
            f'Template {template.id!r} max_output_bytes must be positive'
        )
    elif template.max_output_bytes > MAX_OUTPUT_BYTES:
        issues.append(
            f'Template {template.id!r} max_output_bytes '
            f'{template.max_output_bytes} exceeds max {MAX_OUTPUT_BYTES}'
        )

    # Command must not contain shell metacharacters (prevent injection).
    shell_meta = set(';&|`$(){}')
    for i, arg in enumerate(template.command):
        if any(c in arg for c in shell_meta):
            issues.append(
                f'Template {template.id!r} command[{i}] contains '
                f'shell metacharacter: {arg!r}'
            )

    return issues


class ExecTemplateRegistry:
    """Registry of allowed exec templates.

    Templates are registered at startup and cannot be modified at runtime.
    Client requests reference templates by ID.
    """

    def __init__(self) -> None:
        self._templates: dict[str, ExecTemplate] = {}
        self._frozen = False

    def register(self, template: ExecTemplate) -> None:
        """Register a template. Must be called before freeze().

        Raises:
            ExecPolicyError: If registry is frozen or template is invalid.
        """
        if self._frozen:
            raise ExecPolicyError(
                'Cannot register templates after registry is frozen'
            )

        issues = validate_template(template)
        if issues:
            raise ExecPolicyError(
                f'Invalid template {template.id!r}: {"; ".join(issues)}'
            )

        if template.id in self._templates:
            raise ExecPolicyError(
                f'Template {template.id!r} is already registered'
            )

        self._templates[template.id] = template
        logger.info('Registered exec template: %s', template.id)

    def freeze(self) -> None:
        """Freeze the registry. No more templates can be registered."""
        self._frozen = True
        logger.info(
            'Exec template registry frozen with %d templates: %s',
            len(self._templates),
            sorted(self._templates.keys()),
        )

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    def get(self, template_id: str) -> ExecTemplate:
        """Look up a template by ID.

        Raises:
            ExecPolicyError: If template ID is invalid or not found.
        """
        validate_template_id(template_id)

        template = self._templates.get(template_id)
        if template is None:
            raise ExecPolicyError(
                f'Unknown template {template_id!r}. '
                f'Available: {sorted(self._templates.keys())}'
            )
        return template

    def list_ids(self) -> list[str]:
        """Return sorted list of registered template IDs."""
        return sorted(self._templates.keys())

    def __len__(self) -> int:
        return len(self._templates)


def create_default_registry() -> ExecTemplateRegistry:
    """Create the default exec template registry with standard templates.

    Standard templates:
      - shell: Interactive bash shell
      - claude: Claude Code assistant
    """
    registry = ExecTemplateRegistry()

    registry.register(ExecTemplate(
        id='shell',
        description='Interactive bash shell',
        command=('/bin/bash',),
        timeout_seconds=3600,
        max_output_bytes=204800,
    ))

    registry.register(ExecTemplate(
        id='claude',
        description='Claude Code assistant',
        command=('claude', '--dangerously-skip-permissions'),
        timeout_seconds=7200,
        max_output_bytes=1048576,
    ))

    registry.freeze()
    return registry
