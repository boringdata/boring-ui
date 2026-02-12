"""Unit tests for rate limiting and abuse controls."""
import pytest

from boring_ui.api.rate_limiter import (
    ConcurrencyLimitExceeded,
    ConcurrencyTracker,
    RateLimitConfig,
    RateLimitExceeded,
    SessionLimitConfig,
    SessionLifecycle,
    SlidingWindowCounter,
    DEFAULT_ROUTE_LIMITS,
)


NOW = 1700000000.0


class TestSlidingWindowCounter:

    def test_allows_within_limit(self):
        cfg = RateLimitConfig(max_requests=3, window_seconds=60)
        counter = SlidingWindowCounter(cfg)
        counter.check('key', now=NOW)
        counter.check('key', now=NOW + 1)
        counter.check('key', now=NOW + 2)

    def test_rejects_over_limit(self):
        cfg = RateLimitConfig(max_requests=2, window_seconds=60)
        counter = SlidingWindowCounter(cfg)
        counter.check('key', now=NOW)
        counter.check('key', now=NOW + 1)
        with pytest.raises(RateLimitExceeded) as exc:
            counter.check('key', now=NOW + 2)
        assert exc.value.key == 'key'
        assert exc.value.retry_after > 0

    def test_window_expiry(self):
        cfg = RateLimitConfig(max_requests=2, window_seconds=10)
        counter = SlidingWindowCounter(cfg)
        counter.check('key', now=NOW)
        counter.check('key', now=NOW + 1)
        # After window expires, should be allowed again
        counter.check('key', now=NOW + 11)

    def test_independent_keys(self):
        cfg = RateLimitConfig(max_requests=1, window_seconds=60)
        counter = SlidingWindowCounter(cfg)
        counter.check('a', now=NOW)
        counter.check('b', now=NOW)  # Different key, should work
        with pytest.raises(RateLimitExceeded):
            counter.check('a', now=NOW + 1)

    def test_current_count(self):
        cfg = RateLimitConfig(max_requests=10, window_seconds=60)
        counter = SlidingWindowCounter(cfg)
        assert counter.current_count('key', now=NOW) == 0
        counter.check('key', now=NOW)
        counter.check('key', now=NOW + 1)
        assert counter.current_count('key', now=NOW + 2) == 2

    def test_current_count_window_expiry(self):
        cfg = RateLimitConfig(max_requests=10, window_seconds=10)
        counter = SlidingWindowCounter(cfg)
        counter.check('key', now=NOW)
        assert counter.current_count('key', now=NOW + 11) == 0

    def test_reset_key(self):
        cfg = RateLimitConfig(max_requests=1, window_seconds=60)
        counter = SlidingWindowCounter(cfg)
        counter.check('key', now=NOW)
        counter.reset('key')
        counter.check('key', now=NOW + 1)  # Should work after reset

    def test_reset_all(self):
        cfg = RateLimitConfig(max_requests=1, window_seconds=60)
        counter = SlidingWindowCounter(cfg)
        counter.check('a', now=NOW)
        counter.check('b', now=NOW)
        counter.reset_all()
        counter.check('a', now=NOW + 1)
        counter.check('b', now=NOW + 1)

    def test_retry_after_value(self):
        cfg = RateLimitConfig(max_requests=1, window_seconds=60)
        counter = SlidingWindowCounter(cfg)
        counter.check('key', now=NOW)
        with pytest.raises(RateLimitExceeded) as exc:
            counter.check('key', now=NOW + 10)
        # First request at NOW, window is 60s, so retry after ~50s
        assert 49 < exc.value.retry_after < 51


class TestConcurrencyTracker:

    def test_acquire_and_count(self):
        cfg = SessionLimitConfig(max_concurrent_sessions=3)
        tracker = ConcurrencyTracker(cfg)
        tracker.acquire('ws', 'sess-1')
        tracker.acquire('ws', 'sess-2')
        assert tracker.active_count('ws') == 2

    def test_acquire_idempotent(self):
        cfg = SessionLimitConfig(max_concurrent_sessions=3)
        tracker = ConcurrencyTracker(cfg)
        tracker.acquire('ws', 'sess-1')
        tracker.acquire('ws', 'sess-1')  # Same session
        assert tracker.active_count('ws') == 1

    def test_exceeds_limit(self):
        cfg = SessionLimitConfig(max_concurrent_sessions=2)
        tracker = ConcurrencyTracker(cfg)
        tracker.acquire('ws', 'sess-1')
        tracker.acquire('ws', 'sess-2')
        with pytest.raises(ConcurrencyLimitExceeded) as exc:
            tracker.acquire('ws', 'sess-3')
        assert exc.value.current == 2
        assert exc.value.limit == 2

    def test_release(self):
        cfg = SessionLimitConfig(max_concurrent_sessions=2)
        tracker = ConcurrencyTracker(cfg)
        tracker.acquire('ws', 'sess-1')
        tracker.acquire('ws', 'sess-2')
        tracker.release('ws', 'sess-1')
        tracker.acquire('ws', 'sess-3')  # Should work now

    def test_release_nonexistent(self):
        cfg = SessionLimitConfig(max_concurrent_sessions=2)
        tracker = ConcurrencyTracker(cfg)
        tracker.release('ws', 'nonexistent')  # Should not raise

    def test_active_sessions(self):
        cfg = SessionLimitConfig(max_concurrent_sessions=5)
        tracker = ConcurrencyTracker(cfg)
        tracker.acquire('ws', 'b')
        tracker.acquire('ws', 'a')
        assert tracker.active_sessions('ws') == ['a', 'b']

    def test_independent_keys(self):
        cfg = SessionLimitConfig(max_concurrent_sessions=1)
        tracker = ConcurrencyTracker(cfg)
        tracker.acquire('ws-a', 'sess-1')
        tracker.acquire('ws-b', 'sess-2')  # Different key


class TestSessionLifecycle:

    def test_touch(self):
        s = SessionLifecycle(session_id='s1', created_at=NOW, last_activity_at=NOW)
        s.touch(now=NOW + 100)
        assert s.last_activity_at == NOW + 100

    def test_idle_not_expired(self):
        cfg = SessionLimitConfig(idle_timeout_seconds=1800)
        s = SessionLifecycle(session_id='s1', created_at=NOW, last_activity_at=NOW)
        assert s.is_idle_expired(cfg, now=NOW + 1799) is False

    def test_idle_expired(self):
        cfg = SessionLimitConfig(idle_timeout_seconds=1800)
        s = SessionLifecycle(session_id='s1', created_at=NOW, last_activity_at=NOW)
        assert s.is_idle_expired(cfg, now=NOW + 1801) is True

    def test_absolute_not_expired(self):
        cfg = SessionLimitConfig(absolute_timeout_seconds=86400)
        s = SessionLifecycle(session_id='s1', created_at=NOW, last_activity_at=NOW)
        assert s.is_absolute_expired(cfg, now=NOW + 86399) is False

    def test_absolute_expired(self):
        cfg = SessionLimitConfig(absolute_timeout_seconds=86400)
        s = SessionLifecycle(session_id='s1', created_at=NOW, last_activity_at=NOW)
        assert s.is_absolute_expired(cfg, now=NOW + 86401) is True

    def test_reattach_not_disconnected(self):
        cfg = SessionLimitConfig(reattach_window_seconds=300)
        s = SessionLifecycle(session_id='s1', created_at=NOW, last_activity_at=NOW)
        assert s.is_reattach_expired(cfg, now=NOW + 1000) is False

    def test_reattach_within_window(self):
        cfg = SessionLimitConfig(reattach_window_seconds=300)
        s = SessionLifecycle(
            session_id='s1', created_at=NOW,
            last_activity_at=NOW, ws_disconnected_at=NOW,
        )
        assert s.is_reattach_expired(cfg, now=NOW + 299) is False

    def test_reattach_expired(self):
        cfg = SessionLimitConfig(reattach_window_seconds=300)
        s = SessionLifecycle(
            session_id='s1', created_at=NOW,
            last_activity_at=NOW, ws_disconnected_at=NOW,
        )
        assert s.is_reattach_expired(cfg, now=NOW + 301) is True

    def test_mark_disconnected_and_reconnected(self):
        cfg = SessionLimitConfig(reattach_window_seconds=300)
        s = SessionLifecycle(session_id='s1', created_at=NOW, last_activity_at=NOW)
        s.mark_disconnected(now=NOW + 100)
        assert s.ws_disconnected_at == NOW + 100
        s.mark_reconnected()
        assert s.ws_disconnected_at is None
        assert s.is_reattach_expired(cfg, now=NOW + 1000) is False

    def test_should_terminate_absolute(self):
        cfg = SessionLimitConfig(
            idle_timeout_seconds=99999,
            absolute_timeout_seconds=100,
        )
        s = SessionLifecycle(session_id='s1', created_at=NOW, last_activity_at=NOW + 99)
        terminate, reason = s.should_terminate(cfg, now=NOW + 101)
        assert terminate is True
        assert 'absolute' in reason

    def test_should_terminate_idle(self):
        cfg = SessionLimitConfig(
            idle_timeout_seconds=100,
            absolute_timeout_seconds=99999,
        )
        s = SessionLifecycle(session_id='s1', created_at=NOW, last_activity_at=NOW)
        terminate, reason = s.should_terminate(cfg, now=NOW + 101)
        assert terminate is True
        assert 'idle' in reason

    def test_should_terminate_reattach(self):
        cfg = SessionLimitConfig(
            idle_timeout_seconds=99999,
            absolute_timeout_seconds=99999,
            reattach_window_seconds=60,
        )
        s = SessionLifecycle(
            session_id='s1', created_at=NOW,
            last_activity_at=NOW + 50, ws_disconnected_at=NOW + 50,
        )
        terminate, reason = s.should_terminate(cfg, now=NOW + 111)
        assert terminate is True
        assert 'reattach' in reason

    def test_should_not_terminate(self):
        cfg = SessionLimitConfig()
        s = SessionLifecycle(session_id='s1', created_at=NOW, last_activity_at=NOW)
        terminate, reason = s.should_terminate(cfg, now=NOW + 10)
        assert terminate is False
        assert reason == ''


class TestRateLimitConfig:

    def test_fields(self):
        cfg = RateLimitConfig(max_requests=10, window_seconds=60, description='test')
        assert cfg.max_requests == 10
        assert cfg.window_seconds == 60
        assert cfg.description == 'test'


class TestSessionLimitConfig:

    def test_defaults(self):
        cfg = SessionLimitConfig()
        assert cfg.max_concurrent_sessions == 5
        assert cfg.idle_timeout_seconds == 1800
        assert cfg.absolute_timeout_seconds == 86400
        assert cfg.reattach_window_seconds == 300


class TestDefaultRouteLimits:

    def test_has_tree(self):
        assert '/api/tree' in DEFAULT_ROUTE_LIMITS

    def test_has_search(self):
        assert '/api/search' in DEFAULT_ROUTE_LIMITS

    def test_has_file(self):
        assert '/api/file' in DEFAULT_ROUTE_LIMITS

    def test_has_ws_connect(self):
        assert 'ws_connect' in DEFAULT_ROUTE_LIMITS

    def test_all_have_positive_limits(self):
        for route, cfg in DEFAULT_ROUTE_LIMITS.items():
            assert cfg.max_requests > 0, f'{route} has non-positive max_requests'
            assert cfg.window_seconds > 0, f'{route} has non-positive window'
