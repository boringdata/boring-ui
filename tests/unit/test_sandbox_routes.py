"""Tests for sandbox lifecycle and target-resolution endpoints."""

from fastapi.testclient import TestClient

from boring_ui.api import create_app


class TestSandboxRoutes:
    """Verify sandbox lifecycle API contract."""

    def test_create_and_list_sandbox(self):
        client = TestClient(create_app())

        create_response = client.post(
            '/api/sandbox',
            json={
                'name': 'dev-a',
                'workspace_id': 'ws-1',
                'owner': 'alice',
                'target_base_url': 'http://sandbox-a.internal',
                'labels': {'env': 'dev'},
            },
        )
        assert create_response.status_code == 200
        created = create_response.json()['sandbox']
        assert created['name'] == 'dev-a'
        assert created['status'] == 'pending'

        list_response = client.get('/api/sandbox')
        assert list_response.status_code == 200
        sandboxes = list_response.json()
        assert len(sandboxes) == 1
        assert sandboxes[0]['id'] == created['id']

    def test_lifecycle_start_stop_and_get(self):
        client = TestClient(create_app())

        created = client.post(
            '/api/sandbox',
            json={
                'name': 'dev-a',
                'target_base_url': 'http://sandbox-a.internal',
            },
        ).json()['sandbox']
        sandbox_id = created['id']

        started = client.post(f'/api/sandbox/{sandbox_id}/start')
        assert started.status_code == 200
        assert started.json()['sandbox']['status'] == 'running'

        fetched = client.get(f'/api/sandbox/{sandbox_id}')
        assert fetched.status_code == 200
        assert fetched.json()['id'] == sandbox_id

        stopped = client.post(f'/api/sandbox/{sandbox_id}/stop')
        assert stopped.status_code == 200
        assert stopped.json()['sandbox']['status'] == 'stopped'

    def test_target_resolution_prefers_explicit_then_active_then_workspace(self):
        client = TestClient(create_app())

        first = client.post(
            '/api/sandbox',
            json={
                'name': 'first',
                'workspace_id': 'ws-alpha',
                'target_base_url': 'http://first.internal',
            },
        ).json()['sandbox']
        second = client.post(
            '/api/sandbox',
            json={
                'name': 'second',
                'workspace_id': 'ws-beta',
                'target_base_url': 'http://second.internal',
            },
        ).json()['sandbox']

        active = client.get('/api/sandbox/active')
        assert active.status_code == 200
        assert active.json()['active_sandbox_id'] == first['id']

        explicit = client.get(f"/api/sandbox/target?sandbox_id={second['id']}")
        assert explicit.status_code == 200
        assert explicit.json()['reason'] == 'explicit_sandbox_id'
        assert explicit.json()['sandbox_id'] == second['id']

        by_active = client.get('/api/sandbox/target')
        assert by_active.status_code == 200
        assert by_active.json()['reason'] == 'active_sandbox'
        assert by_active.json()['sandbox_id'] == first['id']

        client.post(f"/api/sandbox/{first['id']}/stop")
        by_workspace = client.get('/api/sandbox/target?workspace_id=ws-beta')
        assert by_workspace.status_code == 200
        assert by_workspace.json()['reason'] == 'workspace_match'
        assert by_workspace.json()['sandbox_id'] == second['id']

    def test_target_resolution_falls_back_to_local(self):
        client = TestClient(create_app())

        response = client.get('/api/sandbox/target')
        assert response.status_code == 200
        data = response.json()
        assert data['mode'] == 'local'
        assert data['reason'] == 'no_sandbox_selected'

    def test_unknown_sandbox_returns_typed_error(self):
        client = TestClient(create_app())

        response = client.get('/api/sandbox/missing-id')
        assert response.status_code == 404
        assert response.json()['detail'] == 'sandbox_not_found'
