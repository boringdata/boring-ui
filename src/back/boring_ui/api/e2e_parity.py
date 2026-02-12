"""End-to-end parity scripts for local vs sandbox (HTTP + WS).

Provides scenario runners and comparison utilities that execute
equivalent user journeys in both local and sandbox modes, emitting
step-by-step structured logs with request_id/session_id correlation,
stable replay artifacts, and explicit parity diffs.

Scenarios cover:
  - File operations: list, read, write, delete, rename, move, search
  - Git operations: status, diff, show
  - Session lifecycle: create, list, get, terminate
  - PTY WebSocket: connect, input, resize, ping, output, exit
  - Chat WebSocket: connect, user message, control, interrupt, exit
  - Tree traversal: bounded traversal with degradation

Parity checking:
  - Compares HTTP status codes, response shapes, and error categories
  - Compares WS message types, close codes, and event ordering
  - Flags divergences as PASS/FAIL/WARN per field
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from boring_ui.api.request_correlation import generate_request_id
from boring_ui.api.test_artifacts import (
    EventTimeline,
    StructuredTestLogger,
)


class JourneyType(Enum):
    """Type of user journey being tested."""
    HTTP_FILES = 'http_files'
    HTTP_GIT = 'http_git'
    HTTP_SESSIONS = 'http_sessions'
    WS_PTY = 'ws_pty'
    WS_CHAT = 'ws_chat'
    TREE_TRAVERSAL = 'tree_traversal'


class ParityVerdict(Enum):
    """Verdict for a single parity check."""
    PASS = 'pass'
    FAIL = 'fail'
    WARN = 'warn'


class StepOutcome(Enum):
    """Outcome of executing a single journey step."""
    SUCCESS = 'success'
    ERROR = 'error'
    SKIPPED = 'skipped'


@dataclass(frozen=True)
class JourneyStep:
    """A single step in a user journey."""
    name: str
    description: str
    journey_type: JourneyType
    order: int


@dataclass
class StepResult:
    """Result of executing a single journey step."""
    step: JourneyStep
    outcome: StepOutcome
    request_id: str = ''
    response_status: int = 0
    response_shape: dict = field(default_factory=dict)
    ws_close_code: int = 0
    ws_messages: list[dict] = field(default_factory=list)
    error_message: str = ''
    elapsed_ms: float = 0.0
    extra: dict = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.outcome == StepOutcome.SUCCESS

    def to_dict(self) -> dict:
        """Serialize to dict for artifact output."""
        d = {
            'step_name': self.step.name,
            'outcome': self.outcome.value,
            'request_id': self.request_id,
            'elapsed_ms': self.elapsed_ms,
        }
        if self.response_status:
            d['response_status'] = self.response_status
        if self.response_shape:
            d['response_shape'] = self.response_shape
        if self.ws_close_code:
            d['ws_close_code'] = self.ws_close_code
        if self.ws_messages:
            d['ws_message_count'] = len(self.ws_messages)
        if self.error_message:
            d['error'] = self.error_message
        if self.extra:
            d['extra'] = self.extra
        return d


@dataclass
class ParityCheck:
    """A single field-level parity comparison."""
    field_name: str
    local_value: str
    sandbox_value: str
    verdict: ParityVerdict
    message: str = ''

    def to_dict(self) -> dict:
        return {
            'field': self.field_name,
            'local': self.local_value,
            'sandbox': self.sandbox_value,
            'verdict': self.verdict.value,
            'message': self.message,
        }


@dataclass
class ParityReport:
    """Aggregated parity comparison for a journey."""
    journey_type: JourneyType
    checks: list[ParityCheck] = field(default_factory=list)
    local_steps: list[StepResult] = field(default_factory=list)
    sandbox_steps: list[StepResult] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.verdict == ParityVerdict.PASS)

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.verdict == ParityVerdict.FAIL)

    @property
    def warn_count(self) -> int:
        return sum(1 for c in self.checks if c.verdict == ParityVerdict.WARN)

    @property
    def total_checks(self) -> int:
        return len(self.checks)

    @property
    def is_passing(self) -> bool:
        return self.fail_count == 0

    def to_dict(self) -> dict:
        return {
            'journey_type': self.journey_type.value,
            'total_checks': self.total_checks,
            'pass': self.pass_count,
            'fail': self.fail_count,
            'warn': self.warn_count,
            'is_passing': self.is_passing,
            'checks': [c.to_dict() for c in self.checks],
        }


# ── Journey definitions ──


# File operations journey
FILE_JOURNEY_STEPS = [
    JourneyStep('list_tree', 'List file tree at root', JourneyType.HTTP_FILES, 0),
    JourneyStep('read_file', 'Read a specific file', JourneyType.HTTP_FILES, 1),
    JourneyStep('write_file', 'Write content to a file', JourneyType.HTTP_FILES, 2),
    JourneyStep('search_files', 'Search for pattern in files', JourneyType.HTTP_FILES, 3),
    JourneyStep('rename_file', 'Rename a file', JourneyType.HTTP_FILES, 4),
    JourneyStep('delete_file', 'Delete a file', JourneyType.HTTP_FILES, 5),
]

# Git operations journey
GIT_JOURNEY_STEPS = [
    JourneyStep('git_status', 'Get git status', JourneyType.HTTP_GIT, 0),
    JourneyStep('git_diff', 'Get git diff', JourneyType.HTTP_GIT, 1),
    JourneyStep('git_show', 'Show git commit', JourneyType.HTTP_GIT, 2),
]

# Session lifecycle journey
SESSION_JOURNEY_STEPS = [
    JourneyStep('create_session', 'Create new session', JourneyType.HTTP_SESSIONS, 0),
    JourneyStep('list_sessions', 'List all sessions', JourneyType.HTTP_SESSIONS, 1),
    JourneyStep('get_session', 'Get session details', JourneyType.HTTP_SESSIONS, 2),
    JourneyStep('terminate_session', 'Terminate session', JourneyType.HTTP_SESSIONS, 3),
]

# PTY WebSocket journey
PTY_JOURNEY_STEPS = [
    JourneyStep('pty_connect', 'Open PTY WebSocket', JourneyType.WS_PTY, 0),
    JourneyStep('pty_input', 'Send terminal input', JourneyType.WS_PTY, 1),
    JourneyStep('pty_resize', 'Resize terminal', JourneyType.WS_PTY, 2),
    JourneyStep('pty_ping', 'Send heartbeat ping', JourneyType.WS_PTY, 3),
    JourneyStep('pty_output', 'Receive terminal output', JourneyType.WS_PTY, 4),
    JourneyStep('pty_exit', 'Handle session exit', JourneyType.WS_PTY, 5),
]

# Chat WebSocket journey
CHAT_JOURNEY_STEPS = [
    JourneyStep('chat_connect', 'Open chat WebSocket', JourneyType.WS_CHAT, 0),
    JourneyStep('chat_user_msg', 'Send user message', JourneyType.WS_CHAT, 1),
    JourneyStep('chat_control', 'Send control message', JourneyType.WS_CHAT, 2),
    JourneyStep('chat_interrupt', 'Send interrupt', JourneyType.WS_CHAT, 3),
    JourneyStep('chat_output', 'Receive assistant output', JourneyType.WS_CHAT, 4),
    JourneyStep('chat_exit', 'Handle session exit', JourneyType.WS_CHAT, 5),
]

ALL_JOURNEYS = {
    JourneyType.HTTP_FILES: FILE_JOURNEY_STEPS,
    JourneyType.HTTP_GIT: GIT_JOURNEY_STEPS,
    JourneyType.HTTP_SESSIONS: SESSION_JOURNEY_STEPS,
    JourneyType.WS_PTY: PTY_JOURNEY_STEPS,
    JourneyType.WS_CHAT: CHAT_JOURNEY_STEPS,
}


# ── Parity comparison engine ──


def compare_status_codes(local: StepResult, sandbox: StepResult) -> ParityCheck:
    """Compare HTTP status codes between local and sandbox results."""
    if local.response_status == sandbox.response_status:
        return ParityCheck(
            field_name='http_status',
            local_value=str(local.response_status),
            sandbox_value=str(sandbox.response_status),
            verdict=ParityVerdict.PASS,
        )
    return ParityCheck(
        field_name='http_status',
        local_value=str(local.response_status),
        sandbox_value=str(sandbox.response_status),
        verdict=ParityVerdict.FAIL,
        message=f'Status mismatch: {local.response_status} vs {sandbox.response_status}',
    )


def compare_response_shapes(local: StepResult, sandbox: StepResult) -> ParityCheck:
    """Compare response body key sets between local and sandbox."""
    local_keys = sorted(local.response_shape.keys())
    sandbox_keys = sorted(sandbox.response_shape.keys())

    if local_keys == sandbox_keys:
        return ParityCheck(
            field_name='response_shape',
            local_value=str(local_keys),
            sandbox_value=str(sandbox_keys),
            verdict=ParityVerdict.PASS,
        )

    missing_in_sandbox = set(local_keys) - set(sandbox_keys)
    extra_in_sandbox = set(sandbox_keys) - set(local_keys)
    message_parts = []
    if missing_in_sandbox:
        message_parts.append(f'missing in sandbox: {missing_in_sandbox}')
    if extra_in_sandbox:
        message_parts.append(f'extra in sandbox: {extra_in_sandbox}')

    return ParityCheck(
        field_name='response_shape',
        local_value=str(local_keys),
        sandbox_value=str(sandbox_keys),
        verdict=ParityVerdict.FAIL,
        message='; '.join(message_parts),
    )


def compare_ws_close_codes(local: StepResult, sandbox: StepResult) -> ParityCheck:
    """Compare WebSocket close codes between local and sandbox."""
    if local.ws_close_code == sandbox.ws_close_code:
        return ParityCheck(
            field_name='ws_close_code',
            local_value=str(local.ws_close_code),
            sandbox_value=str(sandbox.ws_close_code),
            verdict=ParityVerdict.PASS,
        )
    return ParityCheck(
        field_name='ws_close_code',
        local_value=str(local.ws_close_code),
        sandbox_value=str(sandbox.ws_close_code),
        verdict=ParityVerdict.FAIL,
        message=f'Close code mismatch: {local.ws_close_code} vs {sandbox.ws_close_code}',
    )


def compare_ws_message_types(local: StepResult, sandbox: StepResult) -> ParityCheck:
    """Compare WS message type sequences between local and sandbox."""
    local_types = [m.get('type', '') for m in local.ws_messages]
    sandbox_types = [m.get('type', '') for m in sandbox.ws_messages]

    if local_types == sandbox_types:
        return ParityCheck(
            field_name='ws_message_types',
            local_value=str(local_types),
            sandbox_value=str(sandbox_types),
            verdict=ParityVerdict.PASS,
        )

    return ParityCheck(
        field_name='ws_message_types',
        local_value=str(local_types),
        sandbox_value=str(sandbox_types),
        verdict=ParityVerdict.FAIL,
        message='WS message type sequence diverged',
    )


def compare_error_categories(local: StepResult, sandbox: StepResult) -> ParityCheck:
    """Compare error category in response shapes."""
    local_cat = local.response_shape.get('category', '')
    sandbox_cat = sandbox.response_shape.get('category', '')

    if local_cat == sandbox_cat:
        return ParityCheck(
            field_name='error_category',
            local_value=str(local_cat),
            sandbox_value=str(sandbox_cat),
            verdict=ParityVerdict.PASS,
        )
    return ParityCheck(
        field_name='error_category',
        local_value=str(local_cat),
        sandbox_value=str(sandbox_cat),
        verdict=ParityVerdict.FAIL,
        message=f'Error category mismatch: {local_cat!r} vs {sandbox_cat!r}',
    )


def compare_outcome(local: StepResult, sandbox: StepResult) -> ParityCheck:
    """Compare step outcomes (success/error/skipped)."""
    if local.outcome == sandbox.outcome:
        return ParityCheck(
            field_name='outcome',
            local_value=local.outcome.value,
            sandbox_value=sandbox.outcome.value,
            verdict=ParityVerdict.PASS,
        )
    return ParityCheck(
        field_name='outcome',
        local_value=local.outcome.value,
        sandbox_value=sandbox.outcome.value,
        verdict=ParityVerdict.FAIL,
        message=f'Outcome mismatch: {local.outcome.value} vs {sandbox.outcome.value}',
    )


def compare_step_results(
    local: StepResult,
    sandbox: StepResult,
) -> list[ParityCheck]:
    """Run all applicable parity checks for a step pair."""
    checks = [compare_outcome(local, sandbox)]

    if local.response_status or sandbox.response_status:
        checks.append(compare_status_codes(local, sandbox))

    if local.response_shape or sandbox.response_shape:
        checks.append(compare_response_shapes(local, sandbox))
        if 'category' in local.response_shape or 'category' in sandbox.response_shape:
            checks.append(compare_error_categories(local, sandbox))

    if local.ws_close_code or sandbox.ws_close_code:
        checks.append(compare_ws_close_codes(local, sandbox))

    if local.ws_messages or sandbox.ws_messages:
        checks.append(compare_ws_message_types(local, sandbox))

    return checks


def build_parity_report(
    journey_type: JourneyType,
    local_results: list[StepResult],
    sandbox_results: list[StepResult],
) -> ParityReport:
    """Compare local and sandbox results and build a parity report."""
    report = ParityReport(
        journey_type=journey_type,
        local_steps=local_results,
        sandbox_steps=sandbox_results,
    )

    for local, sandbox in zip(local_results, sandbox_results):
        checks = compare_step_results(local, sandbox)
        report.checks.extend(checks)

    return report


# ── Scenario runners ──


class ScenarioRunner:
    """Executes journey steps and collects results with structured logging.

    Provides step-by-step execution with request_id correlation and
    timeline recording for artifact output.
    """

    def __init__(
        self,
        mode: str = 'local',
        logger: StructuredTestLogger | None = None,
        timeline: EventTimeline | None = None,
    ) -> None:
        self._mode = mode
        self._logger = logger or StructuredTestLogger()
        self._timeline = timeline or EventTimeline()
        self._results: list[StepResult] = []

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def results(self) -> list[StepResult]:
        return list(self._results)

    @property
    def logger(self) -> StructuredTestLogger:
        return self._logger

    @property
    def timeline(self) -> EventTimeline:
        return self._timeline

    def execute_step(
        self,
        step: JourneyStep,
        *,
        response_status: int = 200,
        response_shape: dict | None = None,
        ws_close_code: int = 0,
        ws_messages: list[dict] | None = None,
        error_message: str = '',
        extra: dict | None = None,
    ) -> StepResult:
        """Execute a journey step and record structured output."""
        request_id = generate_request_id()
        start = time.monotonic()

        outcome = StepOutcome.SUCCESS
        if error_message:
            outcome = StepOutcome.ERROR

        result = StepResult(
            step=step,
            outcome=outcome,
            request_id=request_id,
            response_status=response_status,
            response_shape=response_shape or {},
            ws_close_code=ws_close_code,
            ws_messages=ws_messages or [],
            error_message=error_message,
            elapsed_ms=(time.monotonic() - start) * 1000,
            extra=extra or {},
        )

        self._results.append(result)

        # Structured log entry
        self._logger.info(
            f'[{self._mode}] {step.name}: {outcome.value}',
            request_id=request_id,
            test_name=step.name,
            status=response_status,
            mode=self._mode,
        )

        # Timeline event
        direction = 'outbound' if step.journey_type in (
            JourneyType.WS_PTY, JourneyType.WS_CHAT,
        ) else 'inbound'
        event_type = (
            'ws_message' if step.journey_type in (
                JourneyType.WS_PTY, JourneyType.WS_CHAT,
            ) else 'http_request'
        )
        self._timeline.record(
            event_type,
            direction,
            request_id=request_id,
            step=step.name,
            outcome=outcome.value,
        )

        return result

    def skip_step(self, step: JourneyStep, reason: str = '') -> StepResult:
        """Record a skipped step."""
        result = StepResult(
            step=step,
            outcome=StepOutcome.SKIPPED,
            error_message=reason or 'Step skipped',
        )
        self._results.append(result)
        self._logger.warning(
            f'[{self._mode}] {step.name}: skipped - {reason}',
            test_name=step.name,
            mode=self._mode,
        )
        return result

    def clear(self) -> None:
        self._results.clear()


class ParityRunner:
    """Runs journeys in both local and sandbox modes and compares results.

    Orchestrates two ScenarioRunners and produces a ParityReport
    with field-level diffs.
    """

    def __init__(
        self,
        local_runner: ScenarioRunner | None = None,
        sandbox_runner: ScenarioRunner | None = None,
    ) -> None:
        self._local = local_runner or ScenarioRunner(mode='local')
        self._sandbox = sandbox_runner or ScenarioRunner(mode='sandbox')
        self._reports: list[ParityReport] = []

    @property
    def local_runner(self) -> ScenarioRunner:
        return self._local

    @property
    def sandbox_runner(self) -> ScenarioRunner:
        return self._sandbox

    @property
    def reports(self) -> list[ParityReport]:
        return list(self._reports)

    @property
    def all_passing(self) -> bool:
        return all(r.is_passing for r in self._reports)

    @property
    def total_checks(self) -> int:
        return sum(r.total_checks for r in self._reports)

    @property
    def total_failures(self) -> int:
        return sum(r.fail_count for r in self._reports)

    def compare_journey(
        self,
        journey_type: JourneyType,
    ) -> ParityReport:
        """Compare results for a journey type."""
        local_results = [
            r for r in self._local.results
            if r.step.journey_type == journey_type
        ]
        sandbox_results = [
            r for r in self._sandbox.results
            if r.step.journey_type == journey_type
        ]

        report = build_parity_report(journey_type, local_results, sandbox_results)
        self._reports.append(report)
        return report

    def summary(self) -> dict:
        """Produce aggregate summary across all journey reports."""
        return {
            'total_journeys': len(self._reports),
            'total_checks': self.total_checks,
            'total_failures': self.total_failures,
            'all_passing': self.all_passing,
            'journeys': [r.to_dict() for r in self._reports],
        }
