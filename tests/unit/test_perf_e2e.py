"""Unit tests for performance/load/soak e2e scripts."""
import json
import math

import pytest

from boring_ui.api.perf_e2e import (
    DisconnectMetrics,
    EndpointType,
    LatencyHistogram,
    LoadProfile,
    LoadTestConfig,
    LoadTestResult,
    PerfTestRunner,
    QueuePressureMetrics,
    simulate_chat_load,
    simulate_pty_load,
    simulate_ramp_load,
    simulate_search_load,
    simulate_tree_load,
)
from boring_ui.api.test_artifacts import EventTimeline, StructuredTestLogger


# ── LatencyHistogram ──


class TestLatencyHistogram:

    def test_empty(self):
        h = LatencyHistogram()
        assert h.count == 0
        assert h.p50 == 0.0
        assert h.p90 == 0.0
        assert h.p95 == 0.0
        assert h.p99 == 0.0
        assert h.mean == 0.0
        assert h.min_val == 0.0
        assert h.max_val == 0.0
        assert h.stddev == 0.0

    def test_single_sample(self):
        h = LatencyHistogram()
        h.record(10.0)
        assert h.count == 1
        assert h.p50 == 10.0
        assert h.mean == 10.0
        assert h.stddev == 0.0

    def test_multiple_samples(self):
        h = LatencyHistogram()
        for i in range(100):
            h.record(float(i))
        assert h.count == 100
        assert h.p50 == pytest.approx(49.5, abs=1.0)
        assert h.min_val == 0.0
        assert h.max_val == 99.0
        assert h.mean == pytest.approx(49.5, abs=0.5)

    def test_percentile_ordering(self):
        h = LatencyHistogram()
        for i in range(1000):
            h.record(float(i))
        assert h.p50 <= h.p90
        assert h.p90 <= h.p95
        assert h.p95 <= h.p99

    def test_stddev(self):
        h = LatencyHistogram()
        h.record(10.0)
        h.record(10.0)
        h.record(10.0)
        assert h.stddev == 0.0

    def test_to_dict(self):
        h = LatencyHistogram()
        h.record(5.0)
        h.record(10.0)
        d = h.to_dict()
        assert 'count' in d
        assert 'p50' in d
        assert 'p90' in d
        assert 'p95' in d
        assert 'p99' in d
        assert 'mean' in d
        assert 'min' in d
        assert 'max' in d
        assert 'stddev' in d
        assert d['count'] == 2

    def test_to_dict_serializable(self):
        h = LatencyHistogram()
        for i in range(50):
            h.record(float(i))
        json.dumps(h.to_dict())


# ── QueuePressureMetrics ──


class TestQueuePressureMetrics:

    def test_defaults(self):
        m = QueuePressureMetrics()
        assert m.high_water_events == 0
        assert m.total_drops == 0
        assert m.drop_rate == 0.0

    def test_drop_rate(self):
        m = QueuePressureMetrics(total_drops=10, total_enqueued=100)
        assert m.drop_rate == 0.1

    def test_to_dict(self):
        m = QueuePressureMetrics(high_water_events=2, total_drops=5, total_enqueued=100)
        d = m.to_dict()
        assert d['high_water_events'] == 2
        assert d['total_drops'] == 5
        assert d['drop_rate'] == 0.05


# ── DisconnectMetrics ──


class TestDisconnectMetrics:

    def test_defaults(self):
        m = DisconnectMetrics()
        assert m.disconnects == 0
        assert m.reconnect_success_rate == 1.0

    def test_success_rate(self):
        m = DisconnectMetrics(reconnects=8, failed_reconnects=2)
        assert m.reconnect_success_rate == 0.8

    def test_to_dict(self):
        m = DisconnectMetrics(disconnects=5, reconnects=4, failed_reconnects=1)
        d = m.to_dict()
        assert d['disconnects'] == 5
        assert d['reconnect_success_rate'] == 0.8


# ── LoadTestResult ──


class TestLoadTestResult:

    def _config(self, endpoint=EndpointType.TREE):
        return LoadTestConfig(endpoint=endpoint, profile=LoadProfile.BURST)

    def test_throughput(self):
        r = LoadTestResult(
            config=self._config(),
            total_requests=1000,
            elapsed_seconds=10.0,
        )
        assert r.throughput == 100.0

    def test_throughput_zero_elapsed(self):
        r = LoadTestResult(config=self._config())
        assert r.throughput == 0.0

    def test_error_rate(self):
        r = LoadTestResult(
            config=self._config(),
            total_requests=100,
            total_errors=5,
        )
        assert r.error_rate == 0.05
        assert r.success_rate == 0.95

    def test_error_rate_zero(self):
        r = LoadTestResult(config=self._config())
        assert r.error_rate == 0.0
        assert r.success_rate == 1.0

    def test_to_dict(self):
        r = LoadTestResult(
            config=self._config(),
            total_requests=100,
            elapsed_seconds=1.0,
        )
        d = r.to_dict()
        assert d['endpoint'] == 'tree'
        assert d['profile'] == 'burst'
        assert d['total_requests'] == 100
        assert 'latency' in d
        assert 'queue_pressure' in d
        assert 'disconnects' in d

    def test_to_dict_serializable(self):
        r = LoadTestResult(
            config=self._config(),
            total_requests=50,
            elapsed_seconds=1.0,
        )
        json.dumps(r.to_dict())


# ── simulate_tree_load ──


class TestSimulateTreeLoad:

    def test_default(self):
        result = simulate_tree_load()
        assert result.config.endpoint == EndpointType.TREE
        assert result.total_requests > 0
        assert result.latency.count > 0
        assert result.elapsed_seconds > 0

    def test_custom_config(self):
        cfg = LoadTestConfig(
            endpoint=EndpointType.TREE,
            profile=LoadProfile.BURST,
            concurrency=5,
            requests_per_client=20,
        )
        result = simulate_tree_load(cfg)
        assert result.total_requests == 100
        assert result.total_errors == 0

    def test_latency_positive(self):
        result = simulate_tree_load()
        assert result.latency.p50 > 0
        assert result.latency.p99 > 0


# ── simulate_search_load ──


class TestSimulateSearchLoad:

    def test_default(self):
        result = simulate_search_load()
        assert result.config.endpoint == EndpointType.SEARCH
        assert result.total_requests > 0

    def test_has_errors(self):
        # Default config has 2% timeout rate
        result = simulate_search_load()
        assert result.total_errors > 0
        assert result.error_rate > 0

    def test_custom_config(self):
        cfg = LoadTestConfig(
            endpoint=EndpointType.SEARCH,
            profile=LoadProfile.BURST,
            concurrency=2,
            requests_per_client=10,
        )
        result = simulate_search_load(cfg)
        assert result.total_requests == 20


# ── simulate_pty_load ──


class TestSimulatePtyLoad:

    def test_default(self):
        result = simulate_pty_load()
        assert result.config.endpoint == EndpointType.PTY
        assert result.total_requests > 0
        assert result.latency.count > 0

    def test_queue_metrics_populated(self):
        result = simulate_pty_load()
        assert result.queue_pressure.total_enqueued > 0

    def test_custom_config(self):
        cfg = LoadTestConfig(
            endpoint=EndpointType.PTY,
            profile=LoadProfile.SUSTAINED,
            concurrency=2,
            requests_per_client=50,
        )
        result = simulate_pty_load(cfg)
        assert result.total_requests == 100


# ── simulate_chat_load ──


class TestSimulateChatLoad:

    def test_default(self):
        result = simulate_chat_load()
        assert result.config.endpoint == EndpointType.CHAT
        assert result.total_requests > 0

    def test_latency_higher_than_pty(self):
        # Chat has thinking time, so p50 should be higher
        chat = simulate_chat_load()
        pty = simulate_pty_load()
        assert chat.latency.p50 > pty.latency.p50

    def test_custom_config(self):
        cfg = LoadTestConfig(
            endpoint=EndpointType.CHAT,
            profile=LoadProfile.SUSTAINED,
            concurrency=2,
            requests_per_client=10,
        )
        result = simulate_chat_load(cfg)
        assert result.total_requests == 20


# ── simulate_ramp_load ──


class TestSimulateRampLoad:

    def test_default(self):
        results = simulate_ramp_load()
        assert len(results) == 5

    def test_increasing_concurrency(self):
        results = simulate_ramp_load(ramp_steps=3, base_concurrency=2)
        concurrencies = [r.config.concurrency for r in results]
        assert concurrencies == [2, 4, 6]

    def test_each_step_has_results(self):
        results = simulate_ramp_load(ramp_steps=3)
        for r in results:
            assert r.total_requests > 0
            assert r.latency.count > 0

    def test_search_ramp(self):
        results = simulate_ramp_load(
            endpoint=EndpointType.SEARCH,
            ramp_steps=2,
        )
        assert len(results) == 2
        assert all(r.config.endpoint == EndpointType.SEARCH for r in results)

    def test_pty_ramp(self):
        results = simulate_ramp_load(
            endpoint=EndpointType.PTY,
            ramp_steps=2,
            base_concurrency=1,
            requests_per_step=20,
        )
        assert len(results) == 2

    def test_chat_ramp(self):
        results = simulate_ramp_load(
            endpoint=EndpointType.CHAT,
            ramp_steps=2,
            base_concurrency=1,
            requests_per_step=10,
        )
        assert len(results) == 2


# ── PerfTestRunner ──


class TestPerfTestRunner:

    def test_record_result(self):
        runner = PerfTestRunner()
        result = simulate_tree_load()
        runner.record_result(result)
        assert len(runner.results) == 1

    def test_total_requests(self):
        runner = PerfTestRunner()
        runner.record_result(simulate_tree_load())
        runner.record_result(simulate_search_load())
        assert runner.total_requests > 0

    def test_total_errors(self):
        runner = PerfTestRunner()
        runner.record_result(simulate_search_load())
        assert runner.total_errors > 0

    def test_logger_records(self):
        test_logger = StructuredTestLogger()
        runner = PerfTestRunner(logger=test_logger)
        runner.record_result(simulate_tree_load())
        assert test_logger.count == 1

    def test_timeline_records(self):
        timeline = EventTimeline()
        runner = PerfTestRunner(timeline=timeline)
        runner.record_result(simulate_tree_load())
        assert timeline.count == 1

    def test_summary(self):
        runner = PerfTestRunner()
        runner.record_result(simulate_tree_load())
        summary = runner.summary()
        assert summary['total_runs'] == 1
        assert summary['total_requests'] > 0

    def test_summary_serializable(self):
        runner = PerfTestRunner()
        runner.record_result(simulate_tree_load())
        runner.record_result(simulate_search_load())
        runner.record_result(simulate_pty_load())
        runner.record_result(simulate_chat_load())
        json.dumps(runner.summary())

    def test_ramp_results(self):
        runner = PerfTestRunner()
        for r in simulate_ramp_load(ramp_steps=3):
            runner.record_result(r)
        assert len(runner.results) == 3

    def test_properties(self):
        runner = PerfTestRunner()
        assert runner.logger is not None
        assert runner.timeline is not None


# ── Enum coverage ──


class TestEnums:

    def test_load_profiles(self):
        assert LoadProfile.BURST.value == 'burst'
        assert LoadProfile.SUSTAINED.value == 'sustained'
        assert LoadProfile.SOAK.value == 'soak'
        assert LoadProfile.RAMP.value == 'ramp'

    def test_endpoint_types(self):
        assert EndpointType.TREE.value == 'tree'
        assert EndpointType.SEARCH.value == 'search'
        assert EndpointType.PTY.value == 'pty'
        assert EndpointType.CHAT.value == 'chat'
