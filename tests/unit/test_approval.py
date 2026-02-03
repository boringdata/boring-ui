"""Unit tests for boring_ui.api.approval module."""
import pytest
from httpx import AsyncClient, ASGITransport
from boring_ui.api.approval import InMemoryApprovalStore, create_approval_router
from fastapi import FastAPI


@pytest.fixture
def store():
    """Create an in-memory approval store."""
    return InMemoryApprovalStore()


@pytest.fixture
def app(store):
    """Create test FastAPI app with approval router."""
    app = FastAPI()
    app.include_router(create_approval_router(store), prefix='/api')
    return app


class TestInMemoryApprovalStore:
    """Tests for InMemoryApprovalStore class."""

    @pytest.mark.asyncio
    async def test_create_and_get(self):
        """Test creating and retrieving an approval request."""
        store = InMemoryApprovalStore()
        await store.create('test-123', {'tool_name': 'Write', 'description': 'Test'})

        result = await store.get('test-123')
        assert result is not None
        assert result['id'] == 'test-123'
        assert result['status'] == 'pending'
        assert result['tool_name'] == 'Write'
        assert 'created_at' in result

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        """Test retrieving non-existent request returns None."""
        store = InMemoryApprovalStore()
        result = await store.get('nonexistent')
        assert result is None

    @pytest.mark.asyncio
    async def test_update(self):
        """Test updating approval with decision."""
        store = InMemoryApprovalStore()
        await store.create('test-123', {'tool_name': 'Write', 'description': 'Test'})
        await store.update('test-123', 'approve', 'Looks good')

        result = await store.get('test-123')
        assert result['status'] == 'approve'
        assert result['reason'] == 'Looks good'
        assert 'decided_at' in result

    @pytest.mark.asyncio
    async def test_list_pending(self):
        """Test listing pending requests."""
        store = InMemoryApprovalStore()
        await store.create('test-1', {'tool_name': 'Write', 'description': 'Test 1'})
        await store.create('test-2', {'tool_name': 'Read', 'description': 'Test 2'})
        await store.update('test-1', 'approve')  # No longer pending

        pending = await store.list_pending()
        assert len(pending) == 1
        assert pending[0]['id'] == 'test-2'

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test deleting an approval request."""
        store = InMemoryApprovalStore()
        await store.create('test-123', {'tool_name': 'Write', 'description': 'Test'})

        deleted = await store.delete('test-123')
        assert deleted is True

        result = await store.get('test-123')
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        """Test deleting non-existent request returns False."""
        store = InMemoryApprovalStore()
        deleted = await store.delete('nonexistent')
        assert deleted is False


class TestCreateRequestEndpoint:
    """Tests for POST /approval/request endpoint."""

    @pytest.mark.asyncio
    async def test_create_approval_request(self, app):
        """Test creating an approval request."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post('/api/approval/request', json={
                'tool_name': 'Write',
                'description': 'Write to file /tmp/test.txt'
            })
            assert r.status_code == 200
            data = r.json()
            assert 'request_id' in data
            assert data['status'] == 'pending'

    @pytest.mark.asyncio
    async def test_create_with_command(self, app):
        """Test creating an approval request with command."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post('/api/approval/request', json={
                'tool_name': 'Bash',
                'description': 'Run npm install',
                'command': 'npm install'
            })
            assert r.status_code == 200
            assert 'request_id' in r.json()

    @pytest.mark.asyncio
    async def test_create_with_metadata(self, app):
        """Test creating an approval request with metadata."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post('/api/approval/request', json={
                'tool_name': 'Write',
                'description': 'Create config file',
                'metadata': {'path': '/etc/config.json', 'size': 1024}
            })
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_create_missing_required_field(self, app):
        """Test creating request without required fields fails."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            # Missing description
            r = await client.post('/api/approval/request', json={
                'tool_name': 'Write'
            })
            assert r.status_code == 422  # Validation error


class TestListPendingEndpoint:
    """Tests for GET /approval/pending endpoint."""

    @pytest.mark.asyncio
    async def test_list_pending_empty(self, app):
        """Test listing pending when none exist."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/approval/pending')
            assert r.status_code == 200
            data = r.json()
            assert data['pending'] == []
            assert data['count'] == 0

    @pytest.mark.asyncio
    async def test_list_pending_with_requests(self, app):
        """Test listing pending requests."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            # Create two requests
            await client.post('/api/approval/request', json={
                'tool_name': 'Write', 'description': 'Write 1'
            })
            await client.post('/api/approval/request', json={
                'tool_name': 'Bash', 'description': 'Run command'
            })

            r = await client.get('/api/approval/pending')
            assert r.status_code == 200
            data = r.json()
            assert data['count'] == 2
            assert len(data['pending']) == 2


class TestDecisionEndpoint:
    """Tests for POST /approval/decision endpoint."""

    @pytest.mark.asyncio
    async def test_approve_request(self, app):
        """Test approving a request."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            # Create request
            r1 = await client.post('/api/approval/request', json={
                'tool_name': 'Write', 'description': 'Test'
            })
            request_id = r1.json()['request_id']

            # Approve it
            r2 = await client.post('/api/approval/decision', json={
                'request_id': request_id,
                'decision': 'approve'
            })
            assert r2.status_code == 200
            data = r2.json()
            assert data['success'] is True
            assert data['decision'] == 'approve'

    @pytest.mark.asyncio
    async def test_deny_request(self, app):
        """Test denying a request."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            # Create request
            r1 = await client.post('/api/approval/request', json={
                'tool_name': 'Bash', 'description': 'Dangerous command'
            })
            request_id = r1.json()['request_id']

            # Deny it with reason
            r2 = await client.post('/api/approval/decision', json={
                'request_id': request_id,
                'decision': 'deny',
                'reason': 'Command too dangerous'
            })
            assert r2.status_code == 200
            assert r2.json()['decision'] == 'deny'

    @pytest.mark.asyncio
    async def test_decision_invalid_value(self, app):
        """Test invalid decision value returns 400."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            # Create request
            r1 = await client.post('/api/approval/request', json={
                'tool_name': 'Write', 'description': 'Test'
            })
            request_id = r1.json()['request_id']

            # Invalid decision
            r2 = await client.post('/api/approval/decision', json={
                'request_id': request_id,
                'decision': 'maybe'
            })
            assert r2.status_code == 400
            assert 'approve' in r2.json()['detail'].lower()

    @pytest.mark.asyncio
    async def test_decision_not_found(self, app):
        """Test decision on non-existent request returns 404."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post('/api/approval/decision', json={
                'request_id': 'nonexistent-id',
                'decision': 'approve'
            })
            assert r.status_code == 404
            assert 'not found' in r.json()['detail'].lower()

    @pytest.mark.asyncio
    async def test_decision_already_decided(self, app):
        """Test decision on already-decided request returns 409."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            # Create and approve
            r1 = await client.post('/api/approval/request', json={
                'tool_name': 'Write', 'description': 'Test'
            })
            request_id = r1.json()['request_id']
            await client.post('/api/approval/decision', json={
                'request_id': request_id,
                'decision': 'approve'
            })

            # Try to decide again
            r2 = await client.post('/api/approval/decision', json={
                'request_id': request_id,
                'decision': 'deny'
            })
            assert r2.status_code == 409
            assert 'already decided' in r2.json()['detail'].lower()


class TestStatusEndpoint:
    """Tests for GET /approval/status/{request_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_status_pending(self, app):
        """Test getting status of pending request."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            # Create request
            r1 = await client.post('/api/approval/request', json={
                'tool_name': 'Write', 'description': 'Test'
            })
            request_id = r1.json()['request_id']

            # Get status
            r2 = await client.get(f'/api/approval/status/{request_id}')
            assert r2.status_code == 200
            data = r2.json()
            assert data['status'] == 'pending'
            assert data['tool_name'] == 'Write'

    @pytest.mark.asyncio
    async def test_get_status_approved(self, app):
        """Test getting status of approved request."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            # Create and approve
            r1 = await client.post('/api/approval/request', json={
                'tool_name': 'Write', 'description': 'Test'
            })
            request_id = r1.json()['request_id']
            await client.post('/api/approval/decision', json={
                'request_id': request_id,
                'decision': 'approve',
                'reason': 'Approved by user'
            })

            # Get status
            r2 = await client.get(f'/api/approval/status/{request_id}')
            assert r2.status_code == 200
            data = r2.json()
            assert data['status'] == 'approve'
            assert data['reason'] == 'Approved by user'
            assert 'decided_at' in data

    @pytest.mark.asyncio
    async def test_get_status_not_found(self, app):
        """Test getting status of non-existent request returns 404."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/approval/status/nonexistent-id')
            assert r.status_code == 404


class TestDeleteEndpoint:
    """Tests for DELETE /approval/{request_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_request(self, app):
        """Test deleting an approval request."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            # Create request
            r1 = await client.post('/api/approval/request', json={
                'tool_name': 'Write', 'description': 'Test'
            })
            request_id = r1.json()['request_id']

            # Delete it
            r2 = await client.delete(f'/api/approval/{request_id}')
            assert r2.status_code == 200
            assert r2.json()['success'] is True

            # Verify it's gone
            r3 = await client.get(f'/api/approval/status/{request_id}')
            assert r3.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_not_found(self, app):
        """Test deleting non-existent request returns 404."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.delete('/api/approval/nonexistent-id')
            assert r.status_code == 404


class TestApprovalWorkflow:
    """Integration tests for full approval workflow."""

    @pytest.mark.asyncio
    async def test_full_approval_workflow(self, app):
        """Test complete approval workflow from create to approve."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            # 1. Create request
            r1 = await client.post('/api/approval/request', json={
                'tool_name': 'Bash',
                'description': 'Run npm install',
                'command': 'npm install',
                'metadata': {'cwd': '/project'}
            })
            assert r1.status_code == 200
            request_id = r1.json()['request_id']

            # 2. Verify in pending list
            r2 = await client.get('/api/approval/pending')
            assert r2.status_code == 200
            pending_ids = [p['id'] for p in r2.json()['pending']]
            assert request_id in pending_ids

            # 3. Check initial status
            r3 = await client.get(f'/api/approval/status/{request_id}')
            assert r3.status_code == 200
            assert r3.json()['status'] == 'pending'

            # 4. Approve
            r4 = await client.post('/api/approval/decision', json={
                'request_id': request_id,
                'decision': 'approve',
                'reason': 'Dependencies needed'
            })
            assert r4.status_code == 200

            # 5. Verify no longer in pending
            r5 = await client.get('/api/approval/pending')
            pending_ids = [p['id'] for p in r5.json()['pending']]
            assert request_id not in pending_ids

            # 6. Verify final status
            r6 = await client.get(f'/api/approval/status/{request_id}')
            assert r6.status_code == 200
            data = r6.json()
            assert data['status'] == 'approve'
            assert data['reason'] == 'Dependencies needed'
            assert 'created_at' in data
            assert 'decided_at' in data
