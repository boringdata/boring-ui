"""Execute parsed scenarios against a live or test control plane.

Bead: bd-223o.16.3 (K3)

The runner takes a :class:`ScenarioSpec` and executes API steps sequentially,
validating responses against expected signals. Results include request IDs,
timestamps, and structured pass/fail outcomes for downstream evidence
collection (K3a) and visual proof (K4).

Usage::

    runner = ScenarioRunner(RunConfig(base_url='http://localhost:8000'))
    result = await runner.run(scenario_spec)
    assert result.passed

For test environments, pass an httpx.AsyncClient directly::

    runner = ScenarioRunner(RunConfig(base_url='http://test'), client=client)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx

from .scenario_parser import ApiSignal, ScenarioSpec


class StepOutcome(str, Enum):
    """Outcome of a single scenario step."""

    PASS = 'pass'
    FAIL = 'fail'
    SKIP = 'skip'
    ERROR = 'error'


@dataclass(frozen=True, slots=True)
class StepResult:
    """Result of executing one API signal step."""

    step_number: int
    method: str
    path: str
    expected_status: int
    actual_status: int | None
    outcome: StepOutcome
    request_id: str
    timestamp: str  # ISO-8601
    duration_ms: float
    response_body: dict[str, Any] | None = None
    error_detail: str | None = None
    missing_fields: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.outcome == StepOutcome.PASS

    def to_dict(self, *, include_body: bool = False) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict with expected vs observed.

        Args:
            include_body: If True, include the full response body.

        Returns:
            Dict with step metadata, expected, observed, and verdict.
        """
        result: dict[str, Any] = {
            'step': self.step_number,
            'method': self.method,
            'path': self.path,
            'outcome': self.outcome.value,
            'timestamp': self.timestamp,
            'duration_ms': round(self.duration_ms, 2),
            'request_id': self.request_id,
            'expected': {
                'status': self.expected_status,
            },
            'observed': {
                'status': self.actual_status,
            },
        }

        if self.missing_fields:
            result['expected']['key_fields'] = list(self.missing_fields)
            result['observed']['missing_fields'] = list(self.missing_fields)

        if self.error_detail:
            result['error_detail'] = self.error_detail

        if include_body and self.response_body is not None:
            result['observed']['body'] = self.response_body

        return result


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """Aggregate result of executing a full scenario."""

    scenario_id: str
    title: str
    step_results: tuple[StepResult, ...]
    started_at: str  # ISO-8601
    finished_at: str  # ISO-8601
    total_duration_ms: float

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.step_results)

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.step_results if r.passed)

    @property
    def fail_count(self) -> int:
        return sum(
            1 for r in self.step_results
            if r.outcome == StepOutcome.FAIL
        )

    @property
    def error_count(self) -> int:
        return sum(
            1 for r in self.step_results
            if r.outcome == StepOutcome.ERROR
        )

    @property
    def total_steps(self) -> int:
        return len(self.step_results)

    def summary(self) -> dict[str, Any]:
        """Return a JSON-serializable summary of the result."""
        return {
            'scenario_id': self.scenario_id,
            'title': self.title,
            'passed': self.passed,
            'steps': self.total_steps,
            'pass': self.pass_count,
            'fail': self.fail_count,
            'error': self.error_count,
            'duration_ms': round(self.total_duration_ms, 1),
            'started_at': self.started_at,
            'finished_at': self.finished_at,
        }

    def to_run_log(self, *, include_bodies: bool = False) -> dict[str, Any]:
        """Return a machine-readable run log with per-step evidence.

        Ties each scenario step to its expected and observed behavior.
        Suitable for downstream evidence collection and reporting.

        Args:
            include_bodies: If True, include full response bodies.

        Returns:
            Dict with scenario metadata, per-step results, and verdict.
        """
        return {
            'scenario_id': self.scenario_id,
            'title': self.title,
            'started_at': self.started_at,
            'finished_at': self.finished_at,
            'duration_ms': round(self.total_duration_ms, 2),
            'verdict': 'pass' if self.passed else 'fail',
            'counts': {
                'total': self.total_steps,
                'pass': self.pass_count,
                'fail': self.fail_count,
                'error': self.error_count,
                'skip': sum(
                    1 for r in self.step_results
                    if r.outcome == StepOutcome.SKIP
                ),
            },
            'steps': [
                r.to_dict(include_body=include_bodies)
                for r in self.step_results
            ],
        }


@dataclass(frozen=True, slots=True)
class RunConfig:
    """Configuration for a scenario run."""

    base_url: str
    session_cookie: str | None = None
    auth_token: str | None = None
    timeout_seconds: float = 30.0
    fail_fast: bool = True
    variable_map: dict[str, str] = field(
        default_factory=dict,
    )


class ScenarioRunner:
    """Execute scenario API steps and record structured outcomes.

    Args:
        config: Run configuration (base URL, auth, etc.).
        client: Optional httpx.AsyncClient (for test injection).
    """

    def __init__(
        self,
        config: RunConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._owns_client = client is None

    async def run(self, spec: ScenarioSpec) -> ScenarioResult:
        """Execute all API signal steps in a scenario.

        Steps without API signals are skipped (they may be UI-only).

        Args:
            spec: Parsed scenario specification.

        Returns:
            ScenarioResult with per-step outcomes.
        """
        started_at = _now_iso()
        start_time = time.monotonic()

        client = self._client or self._build_client()
        try:
            step_results = await self._execute_signals(
                client, spec,
            )
        finally:
            if self._owns_client and client is not self._client:
                await client.aclose()

        finished_at = _now_iso()
        total_ms = (time.monotonic() - start_time) * 1000

        return ScenarioResult(
            scenario_id=spec.scenario_id,
            title=spec.title,
            step_results=tuple(step_results),
            started_at=started_at,
            finished_at=finished_at,
            total_duration_ms=total_ms,
        )

    async def _execute_signals(
        self,
        client: httpx.AsyncClient,
        spec: ScenarioSpec,
    ) -> list[StepResult]:
        """Execute API signal steps sequentially."""
        results: list[StepResult] = []

        for signal in spec.api_signals:
            result = await self._execute_one(client, signal)
            results.append(result)

            if (
                not result.passed
                and self._config.fail_fast
            ):
                # Remaining steps are skipped.
                for remaining in spec.api_signals[len(results):]:
                    results.append(StepResult(
                        step_number=remaining.step,
                        method=remaining.method,
                        path=remaining.path,
                        expected_status=remaining.status,
                        actual_status=None,
                        outcome=StepOutcome.SKIP,
                        request_id='',
                        timestamp=_now_iso(),
                        duration_ms=0.0,
                        error_detail='Skipped due to prior failure',
                    ))
                break

        return results

    async def _execute_one(
        self,
        client: httpx.AsyncClient,
        signal: ApiSignal,
    ) -> StepResult:
        """Execute a single API signal step."""
        url = self._resolve_url(signal.path)
        timestamp = _now_iso()
        start = time.monotonic()

        try:
            response = await client.request(
                method=signal.method,
                url=url,
                timeout=self._config.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            duration_ms = (time.monotonic() - start) * 1000
            return StepResult(
                step_number=signal.step,
                method=signal.method,
                path=signal.path,
                expected_status=signal.status,
                actual_status=None,
                outcome=StepOutcome.ERROR,
                request_id='',
                timestamp=timestamp,
                duration_ms=duration_ms,
                error_detail=f'{type(exc).__name__}: {exc}',
            )

        duration_ms = (time.monotonic() - start) * 1000
        request_id = response.headers.get('x-request-id', '')

        # Parse response body if JSON.
        body: dict[str, Any] | None = None
        try:
            body = response.json()
        except Exception:
            pass

        # Check status code.
        status_ok = response.status_code == signal.status

        # Check key fields present in response body.
        missing = _check_key_fields(body, signal.key_fields)

        if status_ok and not missing:
            outcome = StepOutcome.PASS
        else:
            outcome = StepOutcome.FAIL

        error_detail = None
        if not status_ok:
            error_detail = (
                f'Expected status {signal.status}, '
                f'got {response.status_code}'
            )
        elif missing:
            error_detail = f'Missing key fields: {", ".join(missing)}'

        return StepResult(
            step_number=signal.step,
            method=signal.method,
            path=signal.path,
            expected_status=signal.status,
            actual_status=response.status_code,
            outcome=outcome,
            request_id=request_id,
            timestamp=timestamp,
            duration_ms=duration_ms,
            response_body=body,
            error_detail=error_detail,
            missing_fields=tuple(missing),
        )

    def _resolve_url(self, path: str) -> str:
        """Resolve a path template against the base URL and variable map."""
        resolved = path
        for key, value in self._config.variable_map.items():
            resolved = resolved.replace(f'{{{key}}}', value)
        base = self._config.base_url.rstrip('/')
        return f'{base}{resolved}'

    def _build_client(self) -> httpx.AsyncClient:
        """Build a default httpx.AsyncClient with auth."""
        headers: dict[str, str] = {}
        cookies: dict[str, str] = {}

        if self._config.auth_token:
            headers['Authorization'] = f'Bearer {self._config.auth_token}'
        if self._config.session_cookie:
            cookies['boring_session'] = self._config.session_cookie

        return httpx.AsyncClient(
            headers=headers,
            cookies=cookies,
            follow_redirects=False,
        )


# ── Helpers ────────────────────────────────────────────────────────


def _now_iso() -> str:
    """Return current UTC timestamp in ISO-8601."""
    return datetime.now(timezone.utc).isoformat()


def _check_key_fields(
    body: dict[str, Any] | None,
    key_fields: tuple[str, ...],
) -> list[str]:
    """Check that key fields are present in the response body.

    Fields containing ``:`` are treated as key:value assertions.
    Fields are plain names checked for presence.

    Returns list of missing/invalid field names.
    """
    if not key_fields:
        return []
    if body is None:
        return list(key_fields)

    missing: list[str] = []
    for field_spec in key_fields:
        if ':' in field_spec and not field_spec.startswith('`'):
            # key: value assertion.
            key, expected = field_spec.split(':', 1)
            key = key.strip()
            expected = expected.strip()
            actual = body.get(key)
            if actual is None:
                missing.append(field_spec)
            elif str(actual) != expected:
                missing.append(field_spec)
        else:
            # Plain field presence check.
            field_name = field_spec.strip('`').strip()
            # Handle nested references like `workspaces[]`.
            base = field_name.rstrip('[]')
            if base not in body:
                missing.append(field_spec)

    return missing
