"""Unit tests for WebSocket backpressure, fairness, and lifecycle GC."""
import time

import pytest

from boring_ui.api.ws_lifecycle import (
    DEFAULT_DETACH_WINDOW,
    DEFAULT_FAIRNESS_QUANTUM,
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_QUEUE_HIGH_WATER,
    DEFAULT_QUEUE_MAX_SIZE,
    BoundedOutboundQueue,
    DetachState,
    DetachWindow,
    DropReason,
    FairScheduler,
    QueueState,
    ReapResult,
    SessionEntry,
    SessionReaper,
    WSLifecycleConfig,
    WSLifecyclePolicy,
)


# ── BoundedOutboundQueue ──


class TestBoundedOutboundQueue:

    def test_enqueue_dequeue(self):
        q = BoundedOutboundQueue(max_size=10)
        q.enqueue({'msg': 'a'})
        q.enqueue({'msg': 'b'})
        result = q.dequeue(2)
        assert len(result) == 2
        assert result[0] == {'msg': 'a'}

    def test_empty_dequeue(self):
        q = BoundedOutboundQueue()
        assert q.dequeue(5) == []

    def test_size(self):
        q = BoundedOutboundQueue(max_size=10)
        assert q.size == 0
        q.enqueue({'msg': 'a'})
        assert q.size == 1

    def test_is_empty(self):
        q = BoundedOutboundQueue()
        assert q.is_empty
        q.enqueue({'msg': 'a'})
        assert not q.is_empty

    def test_peek(self):
        q = BoundedOutboundQueue()
        assert q.peek() is None
        q.enqueue({'msg': 'a'})
        assert q.peek() == {'msg': 'a'}
        assert q.size == 1  # peek doesn't dequeue

    def test_clear(self):
        q = BoundedOutboundQueue(max_size=10)
        q.enqueue({'msg': 'a'})
        q.enqueue({'msg': 'b'})
        cleared = q.clear()
        assert cleared == 2
        assert q.is_empty

    def test_state_normal(self):
        q = BoundedOutboundQueue(max_size=100, high_water=75, low_water=25)
        assert q.state == QueueState.NORMAL

    def test_state_high_water(self):
        q = BoundedOutboundQueue(max_size=10, high_water=5, low_water=2)
        for i in range(6):
            q.enqueue({'i': i})
        assert q.state == QueueState.HIGH_WATER

    def test_state_full(self):
        q = BoundedOutboundQueue(max_size=5, high_water=3, low_water=1)
        for i in range(5):
            q.enqueue({'i': i})
        assert q.state == QueueState.FULL

    def test_drops_oldest_when_full(self):
        q = BoundedOutboundQueue(max_size=3, high_water=2, low_water=1)
        q.enqueue({'i': 0})
        q.enqueue({'i': 1})
        q.enqueue({'i': 2})
        q.enqueue({'i': 3})  # Should drop 0
        assert q.size == 3
        result = q.dequeue(3)
        assert result[0] == {'i': 1}
        assert q.stats.dropped == 1

    def test_stats_enqueued(self):
        q = BoundedOutboundQueue(max_size=10)
        q.enqueue({'a': 1})
        q.enqueue({'b': 2})
        assert q.stats.enqueued == 2

    def test_stats_dequeued(self):
        q = BoundedOutboundQueue(max_size=10)
        q.enqueue({'a': 1})
        q.dequeue(1)
        assert q.stats.dequeued == 1

    def test_is_backpressured(self):
        q = BoundedOutboundQueue(max_size=10, high_water=5, low_water=2)
        assert not q.is_backpressured
        for i in range(6):
            q.enqueue({'i': i})
        assert q.is_backpressured

    def test_high_water_correction(self):
        q = BoundedOutboundQueue(max_size=10, high_water=20, low_water=1)
        assert q.high_water < q.max_size

    def test_low_water_correction(self):
        q = BoundedOutboundQueue(max_size=10, high_water=8, low_water=9)
        assert q.low_water < q.high_water

    def test_dequeue_partial(self):
        q = BoundedOutboundQueue(max_size=10)
        q.enqueue({'a': 1})
        q.enqueue({'b': 2})
        result = q.dequeue(5)  # Asking for 5 but only 2 available
        assert len(result) == 2


# ── FairScheduler ──


class TestFairScheduler:

    def test_register(self):
        sched = FairScheduler()
        sched.register('s1')
        assert sched.session_count == 1

    def test_register_idempotent(self):
        sched = FairScheduler()
        sched.register('s1')
        sched.register('s1')
        assert sched.session_count == 1

    def test_unregister(self):
        sched = FairScheduler()
        sched.register('s1')
        sched.unregister('s1')
        assert sched.session_count == 0

    def test_unregister_missing(self):
        sched = FairScheduler()
        sched.unregister('nope')  # No error

    def test_next_batch_round_robin(self):
        sched = FairScheduler(quantum=4)
        sched.register('s1')
        sched.register('s2')
        batch = sched.next_batch()
        assert len(batch) == 2
        ids = [b[0] for b in batch]
        assert 's1' in ids
        assert 's2' in ids
        assert all(q == 4 for _, q in batch)

    def test_next_batch_excludes_unregistered(self):
        sched = FairScheduler()
        sched.register('s1')
        sched.register('s2')
        sched.unregister('s1')
        batch = sched.next_batch()
        assert len(batch) == 1
        assert batch[0][0] == 's2'

    def test_registered_sessions(self):
        sched = FairScheduler()
        sched.register('s1')
        sched.register('s2')
        assert sched.registered_sessions == frozenset({'s1', 's2'})

    def test_empty_batch(self):
        sched = FairScheduler()
        assert sched.next_batch() == []


# ── DetachWindow ──


class TestDetachWindow:

    def test_initial_state_attached(self):
        dw = DetachWindow()
        assert dw.state == DetachState.ATTACHED
        assert dw.is_attached

    def test_detach(self):
        dw = DetachWindow()
        dw.detach()
        assert dw.state == DetachState.DETACHED
        assert not dw.is_attached

    def test_reattach_within_window(self):
        dw = DetachWindow(window_seconds=10.0)
        dw.detach()
        assert dw.reattach() is True
        assert dw.is_attached

    def test_reattach_expired(self):
        dw = DetachWindow(window_seconds=0.0)
        dw.detach()
        dw._detach_time = time.time() - 1.0  # Force expired
        assert dw.state == DetachState.EXPIRED
        assert dw.reattach() is False
        assert dw.is_expired

    def test_time_remaining_attached(self):
        dw = DetachWindow()
        assert dw.time_remaining == 0.0

    def test_time_remaining_detached(self):
        dw = DetachWindow(window_seconds=30.0)
        dw.detach()
        assert dw.time_remaining > 0
        assert dw.time_remaining <= 30.0

    def test_time_remaining_expired(self):
        dw = DetachWindow(window_seconds=0.0)
        dw.detach()
        dw._detach_time = time.time() - 1.0
        assert dw.time_remaining == 0.0


# ── SessionEntry ──


class TestSessionEntry:

    def test_fields(self):
        e = SessionEntry(session_id='s1')
        assert e.session_id == 's1'
        assert e.client_count == 0
        assert e.closed is False

    def test_touch(self):
        e = SessionEntry(session_id='s1')
        before = e.last_activity
        time.sleep(0.01)
        e.touch()
        assert e.last_activity >= before

    def test_is_idle(self):
        e = SessionEntry(session_id='s1')
        assert e.is_idle is True
        e.client_count = 1
        assert e.is_idle is False

    def test_idle_duration(self):
        e = SessionEntry(session_id='s1')
        e.last_activity = time.time() - 10.0
        assert e.idle_duration >= 9.0


# ── SessionReaper ──


class TestSessionReaper:

    def test_reap_closed(self):
        reaper = SessionReaper()
        sessions = {
            's1': SessionEntry(session_id='s1'),
            's2': SessionEntry(session_id='s2'),
        }
        sessions['s1'].closed = True
        result = reaper.identify_reapable(sessions)
        assert 's1' in result.reaped_ids
        assert 's2' not in result.reaped_ids

    def test_reap_idle_timeout(self):
        reaper = SessionReaper(idle_timeout=5.0)
        sessions = {
            's1': SessionEntry(session_id='s1'),
        }
        sessions['s1'].last_activity = time.time() - 10.0
        result = reaper.identify_reapable(sessions)
        assert 's1' in result.reaped_ids

    def test_no_reap_active(self):
        reaper = SessionReaper(idle_timeout=5.0)
        sessions = {
            's1': SessionEntry(session_id='s1'),
        }
        sessions['s1'].client_count = 1
        sessions['s1'].last_activity = time.time() - 100.0
        result = reaper.identify_reapable(sessions)
        assert result.total_reaped == 0

    def test_reap_expired_detach(self):
        reaper = SessionReaper()
        sessions = {
            's1': SessionEntry(session_id='s1'),
        }
        sessions['s1'].detach.detach()
        sessions['s1'].detach._detach_time = time.time() - DEFAULT_DETACH_WINDOW - 1
        result = reaper.identify_reapable(sessions)
        assert 's1' in result.expired_detach_ids

    def test_no_reap_within_detach_window(self):
        reaper = SessionReaper(idle_timeout=999.0)
        sessions = {
            's1': SessionEntry(session_id='s1'),
        }
        sessions['s1'].detach.detach()
        sessions['s1'].client_count = 0
        result = reaper.identify_reapable(sessions)
        # Within detach window, not idle enough
        assert 's1' not in result.expired_detach_ids

    def test_total_reaped(self):
        result = ReapResult(reaped_ids=['s1', 's2'], expired_detach_ids=['s3'])
        assert result.total_reaped == 3


# ── WSLifecyclePolicy ──


class TestWSLifecyclePolicy:

    def test_register_session(self):
        policy = WSLifecyclePolicy()
        entry = policy.register_session('s1')
        assert entry.session_id == 's1'
        assert policy.session_count == 1

    def test_unregister_session(self):
        policy = WSLifecyclePolicy()
        policy.register_session('s1')
        policy.unregister_session('s1')
        assert policy.session_count == 0
        assert policy.get_session('s1') is None

    def test_unregister_missing(self):
        policy = WSLifecyclePolicy()
        policy.unregister_session('nope')  # No error

    def test_get_session(self):
        policy = WSLifecyclePolicy()
        policy.register_session('s1')
        assert policy.get_session('s1') is not None
        assert policy.get_session('nope') is None

    def test_enqueue_message(self):
        policy = WSLifecyclePolicy()
        policy.register_session('s1')
        assert policy.enqueue_message('s1', {'msg': 'hi'}) is True
        assert policy.total_queued_messages == 1

    def test_enqueue_unknown_session(self):
        policy = WSLifecyclePolicy()
        assert policy.enqueue_message('nope', {'msg': 'hi'}) is False

    def test_enqueue_closed_session(self):
        policy = WSLifecyclePolicy()
        entry = policy.register_session('s1')
        entry.closed = True
        assert policy.enqueue_message('s1', {'msg': 'hi'}) is False

    def test_dispatch_round(self):
        policy = WSLifecyclePolicy(WSLifecycleConfig(fairness_quantum=2))
        policy.register_session('s1')
        policy.register_session('s2')
        policy.enqueue_message('s1', {'a': 1})
        policy.enqueue_message('s1', {'a': 2})
        policy.enqueue_message('s1', {'a': 3})
        policy.enqueue_message('s2', {'b': 1})
        result = policy.dispatch_round()
        assert len(result['s1']) == 2  # quantum=2
        assert len(result['s2']) == 1

    def test_dispatch_round_skips_closed(self):
        policy = WSLifecyclePolicy()
        entry = policy.register_session('s1')
        policy.enqueue_message('s1', {'a': 1})
        entry.closed = True
        result = policy.dispatch_round()
        assert 's1' not in result

    def test_client_attach(self):
        policy = WSLifecyclePolicy()
        policy.register_session('s1')
        assert policy.client_attach('s1') is True
        entry = policy.get_session('s1')
        assert entry.client_count == 1

    def test_client_attach_unknown(self):
        policy = WSLifecyclePolicy()
        assert policy.client_attach('nope') is False

    def test_client_detach(self):
        policy = WSLifecyclePolicy()
        policy.register_session('s1')
        policy.client_attach('s1')
        policy.client_detach('s1')
        entry = policy.get_session('s1')
        assert entry.client_count == 0

    def test_detach_starts_window(self):
        policy = WSLifecyclePolicy()
        policy.register_session('s1')
        policy.client_attach('s1')
        policy.client_detach('s1')
        entry = policy.get_session('s1')
        assert entry.detach.state == DetachState.DETACHED

    def test_reattach_within_window(self):
        policy = WSLifecyclePolicy()
        policy.register_session('s1')
        policy.client_attach('s1')
        policy.client_detach('s1')
        assert policy.client_attach('s1') is True

    def test_reattach_expired_window(self):
        policy = WSLifecyclePolicy(WSLifecycleConfig(detach_window=0.0))
        policy.register_session('s1')
        policy.client_attach('s1')
        policy.client_detach('s1')
        entry = policy.get_session('s1')
        entry.detach._detach_time = time.time() - 1.0
        assert policy.client_attach('s1') is False

    def test_run_reap_cycle(self):
        policy = WSLifecyclePolicy(WSLifecycleConfig(idle_timeout=0.0))
        policy.register_session('s1')
        entry = policy.get_session('s1')
        entry.last_activity = time.time() - 1.0
        result = policy.run_reap_cycle()
        assert 's1' in result.reaped_ids
        assert policy.session_count == 0

    def test_should_reject_new(self):
        policy = WSLifecyclePolicy(WSLifecycleConfig(max_sessions=2))
        policy.register_session('s1')
        assert not policy.should_reject_new()
        policy.register_session('s2')
        assert policy.should_reject_new()

    def test_active_session_ids(self):
        policy = WSLifecyclePolicy()
        policy.register_session('s1')
        entry = policy.register_session('s2')
        entry.closed = True
        assert policy.active_session_ids == ['s1']

    def test_total_queued_messages(self):
        policy = WSLifecyclePolicy()
        policy.register_session('s1')
        policy.register_session('s2')
        policy.enqueue_message('s1', {'a': 1})
        policy.enqueue_message('s2', {'b': 1})
        policy.enqueue_message('s2', {'b': 2})
        assert policy.total_queued_messages == 3
