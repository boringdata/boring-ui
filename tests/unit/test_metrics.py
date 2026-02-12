"""Unit tests for core sandbox metrics."""
import pytest

from boring_ui.api.metrics import (
    Counter,
    LabeledCounter,
    LatencyHistogram,
    MetricsRegistry,
)


class TestCounter:

    def test_initial_zero(self):
        c = Counter()
        assert c.value == 0

    def test_inc(self):
        c = Counter()
        c.inc()
        c.inc()
        assert c.value == 2

    def test_inc_amount(self):
        c = Counter()
        c.inc(5)
        assert c.value == 5

    def test_negative_inc(self):
        c = Counter()
        c.inc(10)
        c.inc(-3)
        assert c.value == 7

    def test_reset(self):
        c = Counter()
        c.inc(10)
        c.reset()
        assert c.value == 0


class TestLabeledCounter:

    def test_inc_and_get(self):
        c = LabeledCounter()
        c.inc('200')
        c.inc('200')
        c.inc('404')
        assert c.get('200') == 2
        assert c.get('404') == 1

    def test_get_unknown(self):
        c = LabeledCounter()
        assert c.get('nope') == 0

    def test_all(self):
        c = LabeledCounter()
        c.inc('a')
        c.inc('b', 3)
        assert c.all == {'a': 1, 'b': 3}

    def test_reset(self):
        c = LabeledCounter()
        c.inc('a', 5)
        c.reset()
        assert c.all == {}


class TestLatencyHistogram:

    def test_observe(self):
        h = LatencyHistogram()
        h.observe(0.05)
        assert h.count == 1
        assert h.total == 0.05

    def test_avg(self):
        h = LatencyHistogram()
        h.observe(0.1)
        h.observe(0.3)
        assert h.avg == pytest.approx(0.2)

    def test_avg_empty(self):
        h = LatencyHistogram()
        assert h.avg == 0.0

    def test_bucket_distribution(self):
        h = LatencyHistogram()
        h.observe(0.005)  # <= 0.01
        h.observe(0.05)   # <= 0.05
        h.observe(0.5)    # <= 0.5
        snap = h.snapshot()
        # Buckets are cumulative: each counts values <= that threshold
        assert snap['buckets']['0.01'] == 1   # only 0.005
        assert snap['buckets']['0.05'] == 2   # 0.005 + 0.05
        assert snap['buckets']['0.5'] == 3    # all three

    def test_snapshot(self):
        h = LatencyHistogram()
        h.observe(1.0)
        snap = h.snapshot()
        assert snap['count'] == 1
        assert snap['sum'] == 1.0
        assert 'buckets' in snap


class TestMetricsRegistry:

    def test_record_proxy_request(self):
        m = MetricsRegistry()
        m.record_proxy_request(200, 0.1)
        assert m.proxy_request_total.value == 1
        assert m.proxy_request_latency.count == 1
        assert m.proxy_request_status.get('200') == 1
        assert m.proxy_error_total.value == 0

    def test_record_proxy_error(self):
        m = MetricsRegistry()
        m.record_proxy_request(500, 0.5)
        assert m.proxy_error_total.value == 1

    def test_record_exec_create(self):
        m = MetricsRegistry()
        m.record_exec_create(success=True)
        m.record_exec_create(success=False)
        assert m.exec_create_total.value == 2
        assert m.exec_create_errors.value == 1

    def test_record_exec_attach(self):
        m = MetricsRegistry()
        m.record_exec_attach(success=True)
        m.record_exec_attach(success=False)
        assert m.exec_attach_total.value == 2
        assert m.exec_attach_errors.value == 1

    def test_record_ws_lifecycle(self):
        m = MetricsRegistry()
        m.record_ws_connect()
        m.record_ws_connect()
        m.record_ws_disconnect()
        assert m.ws_connect_total.value == 2
        assert m.ws_disconnect_total.value == 1
        assert m.ws_active.value == 1

    def test_record_health_check(self):
        m = MetricsRegistry()
        m.record_health_check(0.05, success=True)
        m.record_health_check(0.1, success=False)
        assert m.health_check_total.value == 2
        assert m.health_check_failures.value == 1

    def test_record_readiness_transition(self):
        m = MetricsRegistry()
        m.record_readiness_transition('ready')
        m.record_readiness_transition('not_ready')
        m.record_readiness_transition('ready')
        assert m.readiness_transitions.get('ready') == 2
        assert m.readiness_transitions.get('not_ready') == 1

    def test_snapshot(self):
        m = MetricsRegistry()
        m.record_proxy_request(200, 0.1)
        m.record_exec_create()
        m.record_ws_connect()
        m.record_health_check(0.05)
        m.record_readiness_transition('ready')

        snap = m.snapshot()
        assert snap['proxy']['request_total'] == 1
        assert snap['exec']['create_total'] == 1
        assert snap['websocket']['connect_total'] == 1
        assert snap['health']['check_total'] == 1
        assert snap['readiness']['transitions']['ready'] == 1

    def test_snapshot_empty(self):
        m = MetricsRegistry()
        snap = m.snapshot()
        assert snap['proxy']['request_total'] == 0
        assert snap['exec']['create_total'] == 0
        assert snap['websocket']['active'] == 0
