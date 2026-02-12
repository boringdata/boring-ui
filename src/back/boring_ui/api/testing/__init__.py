"""Test harness for deterministic sandbox testing.

Provides stubbed provider clients, fixture replay utilities, and
factory helpers for comprehensive unit and e2e test suites.
"""
from .stubs import (
    StubProxyClient,
    StubExecClient,
    StubServicesClient,
    StubResponse,
)
from .fixtures import (
    FixtureRecorder,
    FixtureReplayer,
    RecordedExchange,
)
from .factories import (
    sandbox_test_app,
    sandbox_config_factory,
    auth_headers,
)

__all__ = [
    'StubProxyClient',
    'StubExecClient',
    'StubServicesClient',
    'StubResponse',
    'FixtureRecorder',
    'FixtureReplayer',
    'RecordedExchange',
    'sandbox_test_app',
    'sandbox_config_factory',
    'auth_headers',
]
