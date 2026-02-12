"""Unit tests for HTTP route delegation in sandbox mode."""
import json

import pytest

from boring_ui.api.http_delegation import (
    DELEGATION_ROUTES,
    DelegationError,
    DelegationMethod,
    DelegationRequest,
    DelegationResponse,
    delegate_delete_file,
    delegate_git_diff,
    delegate_git_show,
    delegate_git_status,
    delegate_list_tree,
    delegate_move_file,
    delegate_read_file,
    delegate_rename_file,
    delegate_search_files,
    delegate_write_file,
    is_delegatable,
    list_delegatable_routes,
    map_upstream_status,
)


# ── DelegationRequest ──


class TestDelegationRequest:

    def test_simple_get(self):
        req = DelegationRequest(method=DelegationMethod.GET, path='/api/tree')
        assert req.method == DelegationMethod.GET
        assert req.path == '/api/tree'
        assert req.full_path == '/api/tree'

    def test_with_query_params(self):
        req = DelegationRequest(
            method=DelegationMethod.GET,
            path='/api/file',
            query_params={'path': 'src/main.py'},
        )
        assert 'path=src' in req.full_path
        assert req.full_path.startswith('/api/file?')

    def test_with_json_body(self):
        req = DelegationRequest(
            method=DelegationMethod.PUT,
            path='/api/file',
            json_body={'content': 'hello'},
        )
        assert req.json_body == {'content': 'hello'}

    def test_with_content(self):
        req = DelegationRequest(
            method=DelegationMethod.POST,
            path='/api/upload',
            content=b'binary data',
        )
        assert req.content == b'binary data'

    def test_empty_query_params(self):
        req = DelegationRequest(
            method=DelegationMethod.GET,
            path='/api/tree',
            query_params={},
        )
        assert req.full_path == '/api/tree'

    def test_special_chars_in_query(self):
        req = DelegationRequest(
            method=DelegationMethod.GET,
            path='/api/file',
            query_params={'path': 'dir/file with spaces.txt'},
        )
        assert 'spaces' in req.full_path
        assert '?' in req.full_path


# ── DelegationResponse ──


class TestDelegationResponse:

    def test_success(self):
        resp = DelegationResponse(status_code=200, body=b'{"ok": true}')
        assert resp.is_success
        assert not resp.is_error

    def test_error(self):
        resp = DelegationResponse(status_code=404)
        assert not resp.is_success
        assert resp.is_error

    def test_redirect(self):
        resp = DelegationResponse(status_code=301)
        assert not resp.is_success
        assert not resp.is_error

    def test_json_body(self):
        resp = DelegationResponse(status_code=200, json_body={'data': 'value'})
        assert resp.json_body == {'data': 'value'}


# ── DelegationError ──


class TestDelegationError:

    def test_basic(self):
        err = DelegationError('connection refused')
        assert err.message == 'connection refused'
        assert err.status_code == 502

    def test_custom_status(self):
        err = DelegationError('timeout', status_code=504)
        assert err.status_code == 504


# ── File delegators ──


class TestFileDelegators:

    def test_list_tree_default(self):
        req = delegate_list_tree()
        assert req.method == DelegationMethod.GET
        assert req.path == '/api/tree'
        assert req.query_params == {'path': '.'}

    def test_list_tree_custom_path(self):
        req = delegate_list_tree('src/components')
        assert req.query_params['path'] == 'src/components'

    def test_read_file(self):
        req = delegate_read_file('main.py')
        assert req.method == DelegationMethod.GET
        assert req.path == '/api/file'
        assert req.query_params['path'] == 'main.py'

    def test_write_file(self):
        req = delegate_write_file('test.py', 'print("hello")')
        assert req.method == DelegationMethod.PUT
        assert req.path == '/api/file'
        assert req.query_params['path'] == 'test.py'
        assert req.json_body == {'content': 'print("hello")'}

    def test_delete_file(self):
        req = delegate_delete_file('old.py')
        assert req.method == DelegationMethod.DELETE
        assert req.path == '/api/file'
        assert req.query_params['path'] == 'old.py'

    def test_rename_file(self):
        req = delegate_rename_file('old.py', 'new.py')
        assert req.method == DelegationMethod.POST
        assert req.path == '/api/file/rename'
        assert req.json_body == {'old_path': 'old.py', 'new_path': 'new.py'}

    def test_move_file(self):
        req = delegate_move_file('file.py', 'dest/')
        assert req.method == DelegationMethod.POST
        assert req.path == '/api/file/move'
        assert req.json_body == {'src_path': 'file.py', 'dest_dir': 'dest/'}

    def test_search_files_default(self):
        req = delegate_search_files('*.py')
        assert req.method == DelegationMethod.GET
        assert req.path == '/api/search'
        assert req.query_params == {'q': '*.py', 'path': '.'}

    def test_search_files_custom_path(self):
        req = delegate_search_files('*.tsx', 'src/front')
        assert req.query_params['path'] == 'src/front'


# ── Git delegators ──


class TestGitDelegators:

    def test_git_status(self):
        req = delegate_git_status()
        assert req.method == DelegationMethod.GET
        assert req.path == '/api/git/status'
        assert req.query_params == {}

    def test_git_diff(self):
        req = delegate_git_diff('main.py')
        assert req.method == DelegationMethod.GET
        assert req.path == '/api/git/diff'
        assert req.query_params['path'] == 'main.py'

    def test_git_show(self):
        req = delegate_git_show('main.py')
        assert req.method == DelegationMethod.GET
        assert req.path == '/api/git/show'
        assert req.query_params['path'] == 'main.py'


# ── Error mapping ──


class TestMapUpstreamStatus:

    def test_success_passthrough(self):
        resp = map_upstream_status(200)
        assert resp.status_code == 200

    def test_400_bad_request(self):
        resp = map_upstream_status(400)
        assert resp.status_code == 400
        assert resp.json_body is not None
        assert resp.json_body['category'] == 'validation'

    def test_403_unauthorized(self):
        resp = map_upstream_status(403)
        assert resp.status_code == 403

    def test_404_not_found(self):
        resp = map_upstream_status(404)
        assert resp.status_code == 404
        assert resp.json_body['category'] == 'not_found'

    def test_409_conflict(self):
        resp = map_upstream_status(409)
        assert resp.status_code == 409

    def test_422_validation(self):
        resp = map_upstream_status(422)
        assert resp.status_code == 422

    def test_429_rate_limited(self):
        resp = map_upstream_status(429)
        assert resp.status_code == 429
        assert 'retry_after' in resp.json_body

    def test_500_maps_to_provider(self):
        resp = map_upstream_status(500)
        assert resp.status_code == 502  # provider_error

    def test_502_maps_to_provider(self):
        resp = map_upstream_status(502)
        assert resp.status_code == 502

    def test_unknown_4xx(self):
        resp = map_upstream_status(418)
        assert resp.status_code == 500  # internal_error

    def test_response_body_is_json(self):
        resp = map_upstream_status(404)
        body = json.loads(resp.body)
        assert body['error'] == resp.json_body['error']

    def test_no_internal_leaks(self):
        resp = map_upstream_status(500)
        body_str = resp.body.decode('utf-8')
        assert 'Internal' not in body_str or 'unavailable' in body_str.lower()


# ── Delegation registry ──


class TestDelegationRegistry:

    def test_is_delegatable_get_tree(self):
        assert is_delegatable('GET', '/api/tree')

    def test_is_delegatable_put_file(self):
        assert is_delegatable('PUT', '/api/file')

    def test_is_delegatable_case_insensitive_method(self):
        assert is_delegatable('get', '/api/tree')

    def test_not_delegatable_unknown(self):
        assert not is_delegatable('GET', '/api/unknown')

    def test_not_delegatable_wrong_method(self):
        assert not is_delegatable('POST', '/api/tree')

    def test_list_delegatable_routes(self):
        routes = list_delegatable_routes()
        assert len(routes) == len(DELEGATION_ROUTES)
        methods = {r[0] for r in routes}
        assert 'GET' in methods
        assert 'PUT' in methods
        assert 'DELETE' in methods
        assert 'POST' in methods

    def test_all_file_routes_present(self):
        routes = {(m, p) for m, p, _ in list_delegatable_routes()}
        assert ('GET', '/api/tree') in routes
        assert ('GET', '/api/file') in routes
        assert ('PUT', '/api/file') in routes
        assert ('DELETE', '/api/file') in routes
        assert ('POST', '/api/file/rename') in routes
        assert ('POST', '/api/file/move') in routes
        assert ('GET', '/api/search') in routes

    def test_all_git_routes_present(self):
        routes = {(m, p) for m, p, _ in list_delegatable_routes()}
        assert ('GET', '/api/git/status') in routes
        assert ('GET', '/api/git/diff') in routes
        assert ('GET', '/api/git/show') in routes
