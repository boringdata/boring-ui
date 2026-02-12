"""Unit tests for workspace service API contract definitions."""
import pytest

from boring_ui.api.workspace_contract import (
    CURRENT_VERSION,
    MIN_COMPATIBLE_VERSION,
    WORKSPACE_API_VERSION_HEADER,
    INTERNAL_AUTH_HEADER,
    PROXIED_ENDPOINTS,
    ALL_ENDPOINTS,
    HEALTH_CHECK_FIXTURES,
    SMOKE_CHECK_FIXTURES,
    ALL_FIXTURES,
    ERROR_MAPPINGS,
    parse_version,
    is_compatible,
    map_upstream_error,
)


class TestVersionParsing:
    """Tests for semver parsing."""

    def test_parse_valid(self):
        assert parse_version('0.1.0') == (0, 1, 0)
        assert parse_version('1.2.3') == (1, 2, 3)
        assert parse_version('10.20.30') == (10, 20, 30)

    def test_parse_invalid_format(self):
        with pytest.raises(ValueError, match='Invalid version'):
            parse_version('1.2')

    def test_parse_non_numeric(self):
        with pytest.raises(ValueError, match='Non-numeric'):
            parse_version('1.2.beta')

    def test_parse_empty(self):
        with pytest.raises(ValueError):
            parse_version('')


class TestVersionCompatibility:
    """Tests for version compatibility checking."""

    def test_exact_match(self):
        assert is_compatible(CURRENT_VERSION) is True

    def test_same_major_higher_minor(self):
        assert is_compatible('0.2.0') is True

    def test_same_major_higher_patch(self):
        assert is_compatible('0.1.5') is True

    def test_different_major(self):
        assert is_compatible('1.0.0') is False

    def test_lower_minor(self):
        # MIN_COMPATIBLE_VERSION is 0.1.0, so 0.0.x is incompatible
        assert is_compatible('0.0.9') is False

    def test_garbage_version(self):
        assert is_compatible('not-a-version') is False

    def test_empty_version(self):
        assert is_compatible('') is False


class TestErrorMapping:
    """Tests for upstream error mapping."""

    def test_400_passthrough(self):
        status, detail = map_upstream_error(400)
        assert status == 400

    def test_404_passthrough(self):
        status, detail = map_upstream_error(404)
        assert status == 404

    def test_409_passthrough(self):
        status, detail = map_upstream_error(409)
        assert status == 409

    def test_500_maps_to_502(self):
        status, detail = map_upstream_error(500)
        assert status == 502

    def test_503_maps_to_503(self):
        status, detail = map_upstream_error(503)
        assert status == 503

    def test_unknown_5xx_maps_to_502(self):
        status, detail = map_upstream_error(599)
        assert status == 502

    def test_unknown_4xx_passthrough(self):
        status, detail = map_upstream_error(418)
        assert status == 418

    def test_detail_never_empty(self):
        for code in (400, 404, 500, 502, 503, 599):
            _, detail = map_upstream_error(code)
            assert detail, f'Empty detail for status {code}'


class TestEndpointContracts:
    """Tests for endpoint contract definitions."""

    def test_all_proxied_require_auth(self):
        """All proxied endpoints must require internal auth."""
        for ep in PROXIED_ENDPOINTS:
            assert INTERNAL_AUTH_HEADER in ep.required_headers, (
                f'{ep.path} missing {INTERNAL_AUTH_HEADER}'
            )

    def test_all_proxied_require_version(self):
        """All proxied endpoints must include version header."""
        for ep in PROXIED_ENDPOINTS:
            assert WORKSPACE_API_VERSION_HEADER in ep.required_headers, (
                f'{ep.path} missing {WORKSPACE_API_VERSION_HEADER}'
            )

    def test_proxied_count(self):
        """Should have contracts for all browser-facing routes."""
        assert len(PROXIED_ENDPOINTS) == 12

    def test_all_endpoints_includes_health(self):
        paths = [ep.path for ep in ALL_ENDPOINTS]
        assert '/healthz' in paths
        assert '/__meta/version' in paths

    def test_no_duplicate_paths(self):
        """Each (method, path) pair should be unique."""
        seen = set()
        for ep in ALL_ENDPOINTS:
            key = (ep.method, ep.path)
            assert key not in seen, f'Duplicate: {key}'
            seen.add(key)


class TestValidationFixtures:
    """Tests for validation fixture definitions."""

    def test_health_fixtures_exist(self):
        assert len(HEALTH_CHECK_FIXTURES) >= 2

    def test_smoke_fixtures_exist(self):
        assert len(SMOKE_CHECK_FIXTURES) >= 3

    def test_all_fixtures_have_names(self):
        names = set()
        for f in ALL_FIXTURES:
            assert f.name, 'Fixture missing name'
            assert f.name not in names, f'Duplicate fixture name: {f.name}'
            names.add(f.name)

    def test_all_fixtures_reference_valid_endpoints(self):
        all_paths = {ep.path for ep in ALL_ENDPOINTS}
        for f in ALL_FIXTURES:
            assert f.endpoint.path in all_paths, (
                f'Fixture {f.name} references unknown path {f.endpoint.path}'
            )

    def test_fixtures_have_expected_keys(self):
        for f in ALL_FIXTURES:
            assert f.expected_keys, f'Fixture {f.name} has no expected_keys'


class TestErrorMappingCompleteness:
    """Ensure error mapping covers critical cases."""

    def test_covers_standard_4xx(self):
        mapped_statuses = {m.upstream_status for m in ERROR_MAPPINGS if isinstance(m.upstream_status, int)}
        assert 400 in mapped_statuses
        assert 404 in mapped_statuses
        assert 409 in mapped_statuses

    def test_covers_standard_5xx(self):
        mapped_statuses = {m.upstream_status for m in ERROR_MAPPINGS if isinstance(m.upstream_status, int)}
        assert 500 in mapped_statuses
        assert 502 in mapped_statuses
        assert 503 in mapped_statuses

    def test_covers_transport_failures(self):
        transport_conditions = {m.upstream_status for m in ERROR_MAPPINGS if isinstance(m.upstream_status, str)}
        assert 'connection_refused' in transport_conditions
        assert 'connection_timeout' in transport_conditions
        assert 'read_timeout' in transport_conditions
        assert 'version_mismatch' in transport_conditions
