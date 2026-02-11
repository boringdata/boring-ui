"""Tests for audit event persistence and querying (bd-1pwb.9.2)."""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta

from src.back.boring_ui.api.audit import (
    AuditEvent,
    AuditEventType,
    AuditLogger,
)
from src.back.boring_ui.api.audit_persistence import (
    InMemoryAuditStore,
    FileAuditStore,
    create_audit_store,
)


class TestInMemoryAuditStore:
    """Tests for in-memory audit store."""

    def test_store_and_retrieve(self):
        """Test basic store and retrieve."""
        store = InMemoryAuditStore()
        event = AuditEvent(
            event_type=AuditEventType.AUTH_SUCCESS,
            timestamp=datetime.now(timezone.utc),
            trace_id="test-123",
            user_id="user1",
        )

        store.store(event)
        results = store.query()

        assert len(results) == 1
        assert results[0].event_type == AuditEventType.AUTH_SUCCESS
        assert results[0].user_id == "user1"

    def test_query_with_filters(self):
        """Test query filtering."""
        store = InMemoryAuditStore()

        event1 = AuditEvent(
            event_type=AuditEventType.AUTH_SUCCESS,
            timestamp=datetime.now(timezone.utc),
            trace_id="trace-1",
            user_id="user1",
            workspace_id="ws-1",
        )
        event2 = AuditEvent(
            event_type=AuditEventType.AUTH_FAILURE,
            timestamp=datetime.now(timezone.utc),
            trace_id="trace-2",
            user_id="user2",
            workspace_id="ws-2",
            status="failure",
        )

        store.store(event1)
        store.store(event2)

        # Query by user_id
        results = store.query(user_id="user1")
        assert len(results) == 1
        assert results[0].user_id == "user1"

        # Query by event_type
        results = store.query(event_type=AuditEventType.AUTH_FAILURE)
        assert len(results) == 1
        assert results[0].event_type == AuditEventType.AUTH_FAILURE

        # Query by status
        results = store.query(status="failure")
        assert len(results) == 1

    def test_query_by_trace_id(self):
        """Test querying by trace/request ID for end-to-end correlation."""
        store = InMemoryAuditStore()
        trace_id = "req-abc123"

        event = AuditEvent(
            event_type=AuditEventType.FILE_WRITE,
            timestamp=datetime.now(timezone.utc),
            trace_id=trace_id,
            user_id="user1",
            resource="/path/to/file.txt",
        )

        store.store(event)
        results = store.query(trace_id=trace_id)

        assert len(results) == 1
        assert results[0].trace_id == trace_id

    def test_count(self):
        """Test event counting."""
        store = InMemoryAuditStore()

        for i in range(5):
            store.store(
                AuditEvent(
                    event_type=AuditEventType.AUTH_SUCCESS,
                    timestamp=datetime.now(timezone.utc),
                    trace_id=f"trace-{i}",
                    user_id=f"user-{i}",
                )
            )

        assert store.count() == 5
        assert store.count(event_type=AuditEventType.AUTH_SUCCESS) == 5
        assert store.count(event_type=AuditEventType.AUTH_FAILURE) == 0

    def test_max_events_eviction(self):
        """Test FIFO eviction when exceeding max_events."""
        store = InMemoryAuditStore(max_events=3)

        for i in range(5):
            store.store(
                AuditEvent(
                    event_type=AuditEventType.AUTH_SUCCESS,
                    timestamp=datetime.now(timezone.utc),
                    trace_id=f"trace-{i}",
                )
            )

        assert len(store.events) == 3
        # Oldest should be evicted
        assert store.events[0].trace_id == "trace-2"


class TestFileAuditStore:
    """Tests for file-based JSONL audit store."""

    def test_store_and_retrieve(self):
        """Test basic file storage and retrieval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FileAuditStore(Path(tmpdir) / "audit.jsonl")
            event = AuditEvent(
                event_type=AuditEventType.AUTH_SUCCESS,
                timestamp=datetime.now(timezone.utc),
                trace_id="test-123",
                user_id="user1",
            )

            store.store(event)
            results = store.query()

            assert len(results) == 1
            assert results[0].event_type == AuditEventType.AUTH_SUCCESS

    def test_persistence_across_instances(self):
        """Test that events persist across store instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.jsonl"

            # Store event with first instance
            store1 = FileAuditStore(path)
            event = AuditEvent(
                event_type=AuditEventType.FILE_WRITE,
                timestamp=datetime.now(timezone.utc),
                trace_id="test-123",
                user_id="user1",
                resource="/path",
            )
            store1.store(event)

            # Retrieve with second instance
            store2 = FileAuditStore(path)
            results = store2.query()

            assert len(results) == 1
            assert results[0].resource == "/path"

    def test_jsonl_format(self):
        """Test that events are stored in JSONL format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.jsonl"
            store = FileAuditStore(path)

            event = AuditEvent(
                event_type=AuditEventType.AUTH_SUCCESS,
                timestamp=datetime.now(timezone.utc),
                trace_id="test-123",
                user_id="user1",
            )
            store.store(event)

            # Read file directly and verify JSON format
            with open(path, "r") as f:
                line = f.readline()
                import json
                data = json.loads(line)
                assert data["event_type"] == "auth_success"
                assert data["user_id"] == "user1"


class TestAuditLoggerPersistence:
    """Tests for AuditLogger with persistence backend."""

    def test_logger_with_persistence(self):
        """Test that AuditLogger stores events when persistence is enabled."""
        store = InMemoryAuditStore()
        logger = AuditLogger(store=store)

        logger.log_auth_success("user1", workspace_id="ws-1", request_id="req-123")

        results = store.query(user_id="user1")
        assert len(results) == 1
        assert results[0].event_type == AuditEventType.AUTH_SUCCESS

    def test_authz_denied_logged(self):
        """Test that authorization denials are properly logged and persisted."""
        store = InMemoryAuditStore()
        logger = AuditLogger(store=store)

        logger.log_authz_denied(
            user_id="attacker",
            resource="/api/admin",
            action="admin:*",
            workspace_id="ws-1",
            reason="missing_permission",
            request_id="req-denied",
        )

        # Query for denials
        results = store.query(event_type=AuditEventType.AUTHZ_DENIED)
        assert len(results) == 1
        assert results[0].status == "denied"
        assert results[0].details.get("reason") == "missing_permission"

    def test_audit_trail_completeness(self):
        """Test that complete audit trail is captured."""
        store = InMemoryAuditStore()
        logger = AuditLogger(store=store)

        # Log various operations
        logger.log_auth_success("user1", request_id="req-1")
        logger.log_file_operation("user1", "read", "/path/file.txt", request_id="req-2")
        logger.log_file_operation("user1", "write", "/path/file.txt", request_id="req-3")
        logger.log_exec_operation("user1", "ls -la", request_id="req-4")
        logger.log_authz_denied("user2", "/api", "write", request_id="req-5", reason="insufficient_perms")

        # Verify all events are persisted
        all_events = store.query(limit=1000)
        assert len(all_events) == 5, f"Expected 5 events but got {len(all_events)}"

        # Verify we can filter by user
        user1_events = store.query(user_id="user1")
        assert len(user1_events) == 4

        user2_events = store.query(user_id="user2")
        assert len(user2_events) == 1


class TestAuditStoreFactory:
    """Tests for audit store factory."""

    def test_memory_store_creation(self):
        """Test creating memory store."""
        store = create_audit_store("memory")
        assert isinstance(store, InMemoryAuditStore)

    def test_file_store_creation(self):
        """Test creating file store with custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "custom.jsonl"
            store = create_audit_store("file", path=path)
            assert isinstance(store, FileAuditStore)
            assert store.path == path

    def test_file_store_default_path(self):
        """Test file store with default path."""
        store = create_audit_store("file")
        assert isinstance(store, FileAuditStore)
        assert ".audit" in str(store.path)
