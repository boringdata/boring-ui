"""Unit tests for SSRF and proxy hardening guardrails."""
import pytest

from boring_ui.api.proxy_guardrails import (
    AllowedTarget,
    ProxyGuardrailConfig,
    ProxyRequestDenied,
    ResponseTooLarge,
    DEFAULT_MAX_RESPONSE_BYTES,
    HOP_BY_HOP_HEADERS,
    STRIPPED_REQUEST_HEADERS,
    sanitize_request_headers,
    sanitize_response_headers,
    validate_proxy_method,
    validate_proxy_path,
    validate_proxy_target,
    validate_response_size,
    validate_response_status,
)


@pytest.fixture
def config():
    return ProxyGuardrailConfig(
        allowed_targets=(
            AllowedTarget(host='workspace-service', port=8443),
        ),
        allowed_path_prefixes=('/api/', '/healthz', '/__meta/'),
    )


class TestAllowedTarget:

    def test_matches(self):
        t = AllowedTarget(host='svc', port=8080)
        assert t.matches('svc', 8080) is True

    def test_no_match_host(self):
        t = AllowedTarget(host='svc', port=8080)
        assert t.matches('evil', 8080) is False

    def test_no_match_port(self):
        t = AllowedTarget(host='svc', port=8080)
        assert t.matches('svc', 9090) is False

    def test_str(self):
        assert str(AllowedTarget('host', 80)) == 'host:80'


class TestValidateProxyTarget:

    def test_allowed_target(self, config):
        validate_proxy_target('workspace-service', 8443, config)

    def test_denied_target(self, config):
        with pytest.raises(ProxyRequestDenied) as exc:
            validate_proxy_target('evil-host', 8443, config)
        assert 'not allowed' in str(exc.value).lower()

    def test_denied_wrong_port(self, config):
        with pytest.raises(ProxyRequestDenied):
            validate_proxy_target('workspace-service', 9999, config)

    def test_empty_allowlist(self):
        cfg = ProxyGuardrailConfig(allowed_targets=())
        with pytest.raises(ProxyRequestDenied) as exc:
            validate_proxy_target('any', 80, cfg)
        assert 'empty' in str(exc.value)

    def test_multiple_targets(self):
        cfg = ProxyGuardrailConfig(
            allowed_targets=(
                AllowedTarget('svc-a', 80),
                AllowedTarget('svc-b', 443),
            ),
        )
        validate_proxy_target('svc-a', 80, cfg)
        validate_proxy_target('svc-b', 443, cfg)
        with pytest.raises(ProxyRequestDenied):
            validate_proxy_target('svc-c', 80, cfg)


class TestValidateProxyPath:

    def test_allowed_api_path(self, config):
        validate_proxy_path('/api/tree', config)

    def test_allowed_api_subpath(self, config):
        validate_proxy_path('/api/file/rename', config)

    def test_allowed_healthz(self, config):
        validate_proxy_path('/healthz', config)

    def test_allowed_meta(self, config):
        validate_proxy_path('/__meta/version', config)

    def test_denied_root(self, config):
        with pytest.raises(ProxyRequestDenied):
            validate_proxy_path('/', config)

    def test_denied_arbitrary(self, config):
        with pytest.raises(ProxyRequestDenied):
            validate_proxy_path('/admin/secrets', config)

    def test_path_traversal_rejected(self, config):
        with pytest.raises(ProxyRequestDenied) as exc:
            validate_proxy_path('/api/../etc/passwd', config)
        assert 'traversal' in str(exc.value).lower()

    def test_double_dot_in_query_not_path(self, config):
        # .. in the path component itself should be caught
        with pytest.raises(ProxyRequestDenied):
            validate_proxy_path('/api/../../secret', config)

    def test_empty_prefixes(self):
        cfg = ProxyGuardrailConfig(allowed_path_prefixes=())
        with pytest.raises(ProxyRequestDenied) as exc:
            validate_proxy_path('/api/test', cfg)
        assert 'empty' in str(exc.value)


class TestValidateProxyMethod:

    def test_allowed_get(self, config):
        validate_proxy_method('GET', config)

    def test_allowed_post(self, config):
        validate_proxy_method('POST', config)

    def test_allowed_put(self, config):
        validate_proxy_method('PUT', config)

    def test_allowed_delete(self, config):
        validate_proxy_method('DELETE', config)

    def test_case_insensitive(self, config):
        validate_proxy_method('get', config)

    def test_denied_options(self, config):
        with pytest.raises(ProxyRequestDenied):
            validate_proxy_method('OPTIONS', config)

    def test_denied_trace(self, config):
        with pytest.raises(ProxyRequestDenied):
            validate_proxy_method('TRACE', config)

    def test_denied_connect(self, config):
        with pytest.raises(ProxyRequestDenied):
            validate_proxy_method('CONNECT', config)

    def test_custom_methods(self):
        cfg = ProxyGuardrailConfig(
            allowed_methods=frozenset({'GET'}),
        )
        validate_proxy_method('GET', cfg)
        with pytest.raises(ProxyRequestDenied):
            validate_proxy_method('POST', cfg)


class TestValidateResponseStatus:

    def test_200_ok(self, config):
        validate_response_status(200, config)

    def test_404_ok(self, config):
        validate_response_status(404, config)

    def test_500_ok(self, config):
        validate_response_status(500, config)

    def test_301_redirect_denied(self, config):
        with pytest.raises(ProxyRequestDenied) as exc:
            validate_response_status(301, config)
        assert 'redirect' in str(exc.value).lower()

    def test_302_redirect_denied(self, config):
        with pytest.raises(ProxyRequestDenied):
            validate_response_status(302, config)

    def test_307_redirect_denied(self, config):
        with pytest.raises(ProxyRequestDenied):
            validate_response_status(307, config)

    def test_redirects_allowed_when_configured(self):
        cfg = ProxyGuardrailConfig(allow_redirects=True)
        validate_response_status(302, cfg)  # should not raise


class TestValidateResponseSize:

    def test_within_limit(self, config):
        validate_response_size(1024, config)

    def test_at_limit(self, config):
        validate_response_size(DEFAULT_MAX_RESPONSE_BYTES, config)

    def test_over_limit(self, config):
        with pytest.raises(ResponseTooLarge) as exc:
            validate_response_size(DEFAULT_MAX_RESPONSE_BYTES + 1, config)
        assert exc.value.size == DEFAULT_MAX_RESPONSE_BYTES + 1
        assert exc.value.limit == DEFAULT_MAX_RESPONSE_BYTES

    def test_none_content_length_ok(self, config):
        validate_response_size(None, config)

    def test_custom_limit(self):
        cfg = ProxyGuardrailConfig(max_response_bytes=1000)
        validate_response_size(999, cfg)
        with pytest.raises(ResponseTooLarge):
            validate_response_size(1001, cfg)


class TestSanitizeRequestHeaders:

    def test_strips_authorization(self):
        h = sanitize_request_headers({
            'Authorization': 'Bearer token',
            'Content-Type': 'application/json',
        })
        assert 'Authorization' not in h
        assert h['Content-Type'] == 'application/json'

    def test_strips_cookie(self):
        h = sanitize_request_headers({'Cookie': 'session=abc', 'Accept': '*/*'})
        assert 'Cookie' not in h
        assert h['Accept'] == '*/*'

    def test_strips_hop_by_hop(self):
        h = sanitize_request_headers({
            'Connection': 'keep-alive',
            'Transfer-Encoding': 'chunked',
            'X-Custom': 'safe',
        })
        assert 'Connection' not in h
        assert 'Transfer-Encoding' not in h
        assert h['X-Custom'] == 'safe'

    def test_strips_host(self):
        h = sanitize_request_headers({'Host': 'evil.com', 'Accept': '*/*'})
        assert 'Host' not in h

    def test_case_insensitive(self):
        h = sanitize_request_headers({'authorization': 'Bearer x'})
        assert len(h) == 0

    def test_strips_internal_auth(self):
        """Internal auth headers from browser must be stripped to prevent spoofing.

        The proxy injects its own auth headers after sanitization.
        """
        h = sanitize_request_headers({
            'X-Workspace-Internal-Auth': 'hmac-sha256:123:abc',
            'X-Workspace-API-Version': '0.1.0',
        })
        assert 'X-Workspace-Internal-Auth' not in h
        assert 'X-Workspace-API-Version' not in h

    def test_empty_headers(self):
        assert sanitize_request_headers({}) == {}


class TestSanitizeResponseHeaders:

    def test_strips_hop_by_hop(self):
        h = sanitize_response_headers({
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
        })
        assert 'Connection' not in h
        assert h['Content-Type'] == 'application/json'

    def test_preserves_content_headers(self):
        h = sanitize_response_headers({
            'Content-Type': 'application/json',
            'Content-Length': '42',
            'X-Custom': 'value',
        })
        assert len(h) == 3

    def test_strips_transfer_encoding(self):
        h = sanitize_response_headers({'Transfer-Encoding': 'chunked'})
        assert len(h) == 0

    def test_empty_headers(self):
        assert sanitize_response_headers({}) == {}


class TestProxyGuardrailConfig:

    def test_defaults(self):
        cfg = ProxyGuardrailConfig()
        assert cfg.allowed_targets == ()
        assert cfg.allow_redirects is False
        assert cfg.max_response_bytes == DEFAULT_MAX_RESPONSE_BYTES

    def test_custom_config(self):
        cfg = ProxyGuardrailConfig(
            allowed_targets=(AllowedTarget('svc', 80),),
            max_response_bytes=1000,
            allow_redirects=True,
        )
        assert len(cfg.allowed_targets) == 1
        assert cfg.max_response_bytes == 1000
        assert cfg.allow_redirects is True
