"""Fixture recording and replay for deterministic sandbox tests.

Allows capturing real HTTP exchanges and replaying them in CI
without network access.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .stubs import StubProxyClient, StubResponse

logger = logging.getLogger(__name__)


@dataclass
class RecordedExchange:
    """A recorded HTTP request/response exchange."""
    method: str
    path: str
    request_headers: dict[str, str] = field(default_factory=dict)
    request_params: dict[str, str] = field(default_factory=dict)
    request_json: dict | None = None
    response_status: int = 200
    response_headers: dict[str, str] = field(default_factory=dict)
    response_json: dict | list | None = None
    response_text: str = ''

    def to_stub_response(self) -> StubResponse:
        """Convert to a StubResponse for replay."""
        return StubResponse(
            status_code=self.response_status,
            headers=self.response_headers,
            json_body=self.response_json,
            text_body=self.response_text,
        )


class FixtureRecorder:
    """Records HTTP exchanges to a fixture file.

    Usage:
        recorder = FixtureRecorder()
        recorder.record(exchange)
        recorder.save(Path('fixtures/my_test.json'))
    """

    def __init__(self) -> None:
        self._exchanges: list[RecordedExchange] = []

    def record(self, exchange: RecordedExchange) -> None:
        """Add an exchange to the recording."""
        self._exchanges.append(exchange)

    def save(self, path: Path) -> None:
        """Save recorded exchanges to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(e) for e in self._exchanges]
        path.write_text(json.dumps(data, indent=2))
        logger.info('Saved %d exchanges to %s', len(data), path)

    @property
    def exchanges(self) -> list[RecordedExchange]:
        return list(self._exchanges)

    @property
    def count(self) -> int:
        return len(self._exchanges)

    def clear(self) -> None:
        self._exchanges.clear()


class FixtureReplayer:
    """Loads recorded fixtures and configures a StubProxyClient.

    Usage:
        replayer = FixtureReplayer.from_file(Path('fixtures/my_test.json'))
        client = replayer.to_stub_client()
    """

    def __init__(self, exchanges: list[RecordedExchange]) -> None:
        self._exchanges = exchanges

    @classmethod
    def from_file(cls, path: Path) -> FixtureReplayer:
        """Load exchanges from a JSON fixture file."""
        data = json.loads(path.read_text())
        exchanges = [RecordedExchange(**e) for e in data]
        return cls(exchanges)

    @classmethod
    def from_exchanges(cls, exchanges: list[RecordedExchange]) -> FixtureReplayer:
        """Create from a list of RecordedExchange objects."""
        return cls(exchanges)

    def to_stub_client(self) -> StubProxyClient:
        """Create a StubProxyClient pre-loaded with fixture responses."""
        client = StubProxyClient()
        for exchange in self._exchanges:
            client.set_response(
                exchange.method,
                exchange.path,
                exchange.to_stub_response(),
            )
        return client

    @property
    def exchanges(self) -> list[RecordedExchange]:
        return list(self._exchanges)

    @property
    def count(self) -> int:
        return len(self._exchanges)
