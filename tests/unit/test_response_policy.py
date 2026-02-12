"""Unit tests for response streaming, size caps, and retry policy."""
import pytest

from boring_ui.api.response_policy import (
    DEFAULT_MAX_RESPONSE_SIZE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BASE_DELAY,
    DEFAULT_STREAMING_CHUNK_SIZE,
    IDEMPOTENT_METHODS,
    RETRYABLE_STATUS_CODES,
    IdempotentRetryPolicy,
    ResponsePolicy,
    ResponsePolicyConfig,
    ResponseSizeCap,
    RetryAttempt,
    RetryDecision,
    SizeCapResult,
    SizeExceededAction,
    StreamingBuffer,
    StreamingChunk,
    is_idempotent,
    is_retryable_status,
)


# ── Idempotency helpers ──


class TestIdempotency:

    def test_get_is_idempotent(self):
        assert is_idempotent('GET')

    def test_head_is_idempotent(self):
        assert is_idempotent('HEAD')

    def test_put_is_idempotent(self):
        assert is_idempotent('PUT')

    def test_delete_is_idempotent(self):
        assert is_idempotent('DELETE')

    def test_post_is_not_idempotent(self):
        assert not is_idempotent('POST')

    def test_patch_is_not_idempotent(self):
        assert not is_idempotent('PATCH')

    def test_case_insensitive(self):
        assert is_idempotent('get')

    def test_retryable_502(self):
        assert is_retryable_status(502)

    def test_retryable_429(self):
        assert is_retryable_status(429)

    def test_not_retryable_200(self):
        assert not is_retryable_status(200)

    def test_not_retryable_404(self):
        assert not is_retryable_status(404)


# ── ResponseSizeCap ──


class TestResponseSizeCap:

    def test_within_limit(self):
        cap = ResponseSizeCap(max_size=100)
        result = cap.apply(b'hello')
        assert result.is_ok
        assert result.data == b'hello'
        assert result.original_size == 5
        assert not result.was_truncated
        assert not result.was_rejected

    def test_truncate(self):
        cap = ResponseSizeCap(max_size=3, action=SizeExceededAction.TRUNCATE)
        result = cap.apply(b'hello')
        assert result.data == b'hel'
        assert result.was_truncated
        assert not result.was_rejected
        assert result.original_size == 5

    def test_reject(self):
        cap = ResponseSizeCap(max_size=3, action=SizeExceededAction.REJECT)
        result = cap.apply(b'hello')
        assert result.data == b''
        assert result.was_rejected
        assert not result.was_truncated
        assert result.original_size == 5

    def test_exact_limit(self):
        cap = ResponseSizeCap(max_size=5)
        result = cap.apply(b'hello')
        assert result.is_ok
        assert result.data == b'hello'

    def test_empty_data(self):
        cap = ResponseSizeCap(max_size=100)
        result = cap.apply(b'')
        assert result.is_ok
        assert result.data == b''

    def test_max_size_property(self):
        cap = ResponseSizeCap(max_size=42)
        assert cap.max_size == 42


# ── StreamingBuffer ──


class TestStreamingBuffer:

    def test_basic_feed(self):
        buf = StreamingBuffer(chunk_size=5, max_total=100)
        chunks = buf.feed(b'hello world')
        assert len(chunks) == 2  # 'hello' and ' worl'
        assert chunks[0].data == b'hello'
        assert chunks[0].index == 0
        assert chunks[1].data == b' worl'

    def test_flush_remainder(self):
        buf = StreamingBuffer(chunk_size=10, max_total=100)
        buf.feed(b'hello')
        final = buf.flush()
        assert final is not None
        assert final.data == b'hello'
        assert final.is_last

    def test_flush_empty(self):
        buf = StreamingBuffer(chunk_size=5, max_total=100)
        buf.feed(b'hello')  # Exactly one chunk
        assert buf.flush() is None  # Nothing left

    def test_total_received(self):
        buf = StreamingBuffer(chunk_size=100, max_total=1000)
        buf.feed(b'hello')
        buf.feed(b'world')
        assert buf.total_received == 10

    def test_max_total_enforced(self):
        buf = StreamingBuffer(chunk_size=5, max_total=8)
        chunks = buf.feed(b'hello world!')
        total_data = b''.join(c.data for c in chunks)
        final = buf.flush()
        if final:
            total_data += final.data
        assert len(total_data) <= 8

    def test_is_exceeded(self):
        buf = StreamingBuffer(chunk_size=100, max_total=5)
        buf.feed(b'hello world')
        assert buf.total_received <= 5

    def test_feed_after_finished(self):
        buf = StreamingBuffer(chunk_size=100, max_total=5)
        buf.feed(b'hello world')
        buf.flush()
        assert buf.feed(b'more') == []

    def test_chunk_index_increments(self):
        buf = StreamingBuffer(chunk_size=3, max_total=100)
        chunks = buf.feed(b'abcdef')
        assert chunks[0].index == 0
        assert chunks[1].index == 1

    def test_chunk_size_property(self):
        buf = StreamingBuffer(chunk_size=42)
        assert buf.chunk_size == 42


# ── IdempotentRetryPolicy ──


class TestIdempotentRetryPolicy:

    def test_retry_on_502(self):
        policy = IdempotentRetryPolicy()
        decision, attempt = policy.evaluate('GET', 502, 0)
        assert decision == RetryDecision.RETRY
        assert attempt is not None
        assert attempt.attempt == 1
        assert attempt.delay > 0

    def test_skip_post(self):
        policy = IdempotentRetryPolicy()
        decision, attempt = policy.evaluate('POST', 502, 0)
        assert decision == RetryDecision.SKIP
        assert attempt is None

    def test_stop_on_200(self):
        policy = IdempotentRetryPolicy()
        decision, attempt = policy.evaluate('GET', 200, 0)
        assert decision == RetryDecision.STOP
        assert attempt is None

    def test_stop_on_404(self):
        policy = IdempotentRetryPolicy()
        decision, attempt = policy.evaluate('GET', 404, 0)
        assert decision == RetryDecision.STOP

    def test_stop_at_max_retries(self):
        policy = IdempotentRetryPolicy(max_retries=2)
        decision, _ = policy.evaluate('GET', 502, 2)
        assert decision == RetryDecision.STOP

    def test_exponential_backoff(self):
        policy = IdempotentRetryPolicy(
            base_delay=1.0, backoff_factor=2.0, max_delay=100.0,
        )
        _, a0 = policy.evaluate('GET', 502, 0)
        _, a1 = policy.evaluate('GET', 502, 1)
        _, a2 = policy.evaluate('GET', 502, 2)
        assert a0.delay == 1.0
        assert a1.delay == 2.0
        assert a2.delay == 4.0

    def test_delay_capped(self):
        policy = IdempotentRetryPolicy(
            base_delay=1.0, backoff_factor=10.0, max_delay=5.0,
        )
        _, attempt = policy.evaluate('GET', 502, 2)
        assert attempt.delay <= 5.0

    def test_compute_delays(self):
        policy = IdempotentRetryPolicy(
            max_retries=3, base_delay=1.0, backoff_factor=2.0, max_delay=100.0,
        )
        delays = policy.compute_delays(3)
        assert delays == [1.0, 2.0, 4.0]

    def test_compute_delays_capped(self):
        policy = IdempotentRetryPolicy(max_retries=2)
        delays = policy.compute_delays(5)
        assert len(delays) == 2  # Capped at max_retries

    def test_retry_429(self):
        policy = IdempotentRetryPolicy()
        decision, _ = policy.evaluate('GET', 429, 0)
        assert decision == RetryDecision.RETRY

    def test_retry_503(self):
        policy = IdempotentRetryPolicy()
        decision, _ = policy.evaluate('GET', 503, 0)
        assert decision == RetryDecision.RETRY

    def test_max_retries_property(self):
        policy = IdempotentRetryPolicy(max_retries=7)
        assert policy.max_retries == 7


# ── ResponsePolicy (unified) ──


class TestResponsePolicy:

    def test_default_config(self):
        policy = ResponsePolicy()
        assert policy.size_cap.max_size == DEFAULT_MAX_RESPONSE_SIZE
        assert policy.retry_policy.max_retries == DEFAULT_MAX_RETRIES

    def test_custom_config(self):
        config = ResponsePolicyConfig(
            max_response_size=1024,
            max_retries=5,
        )
        policy = ResponsePolicy(config)
        assert policy.size_cap.max_size == 1024
        assert policy.retry_policy.max_retries == 5

    def test_apply_size_cap(self):
        config = ResponsePolicyConfig(max_response_size=5)
        policy = ResponsePolicy(config)
        result = policy.apply_size_cap(b'hello world')
        assert result.was_truncated
        assert len(result.data) == 5

    def test_create_streaming_buffer(self):
        config = ResponsePolicyConfig(
            streaming_chunk_size=32,
            max_response_size=100,
        )
        policy = ResponsePolicy(config)
        buf = policy.create_streaming_buffer()
        assert buf.chunk_size == 32

    def test_should_retry_get_502(self):
        policy = ResponsePolicy()
        decision, attempt = policy.should_retry('GET', 502, 0)
        assert decision == RetryDecision.RETRY

    def test_should_not_retry_post(self):
        policy = ResponsePolicy()
        decision, _ = policy.should_retry('POST', 502, 0)
        assert decision == RetryDecision.SKIP

    def test_reject_action(self):
        config = ResponsePolicyConfig(
            max_response_size=5,
            size_exceeded_action=SizeExceededAction.REJECT,
        )
        policy = ResponsePolicy(config)
        result = policy.apply_size_cap(b'hello world')
        assert result.was_rejected
        assert result.data == b''
