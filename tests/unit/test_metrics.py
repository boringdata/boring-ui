"""Tests for the sandbox metrics module."""
import pytest

from boring_ui.api.modules.sandbox.metrics import (
    gauge_dec,
    gauge_inc,
    get_snapshot,
    record,
    reset,
    timed,
)


@pytest.fixture(autouse=True)
def _clean_metrics():
    """Reset metrics before each test."""
    reset()
    yield
    reset()


class TestRecord:
    def test_counter_increment(self):
        record("test_counter")
        record("test_counter")
        snap = get_snapshot()
        assert snap["counters"]["test_counter"] == 2.0

    def test_counter_custom_value(self):
        record("test_counter", value=5.0)
        snap = get_snapshot()
        assert snap["counters"]["test_counter"] == 5.0

    def test_counter_with_tags(self):
        record("errors_total", tags={"sandbox_id": "sb-1"})
        record("errors_total", tags={"sandbox_id": "sb-2"})
        snap = get_snapshot()
        assert snap["counters"]["errors_total{sandbox_id=sb-1}"] == 1.0
        assert snap["counters"]["errors_total{sandbox_id=sb-2}"] == 1.0

    def test_gauge_set(self):
        record("active", value=3.0, kind="gauge")
        snap = get_snapshot()
        assert snap["gauges"]["active"] == 3.0

    def test_gauge_overwrite(self):
        record("active", value=3.0, kind="gauge")
        record("active", value=7.0, kind="gauge")
        snap = get_snapshot()
        assert snap["gauges"]["active"] == 7.0

    def test_histogram_observe(self):
        record("duration", value=0.5, kind="histogram")
        record("duration", value=1.5, kind="histogram")
        snap = get_snapshot()
        h = snap["histograms"]["duration"]
        assert h["count"] == 2
        assert h["min"] == 0.5
        assert h["max"] == 1.5
        assert h["avg"] == 1.0


class TestGaugeHelpers:
    def test_gauge_inc_dec(self):
        gauge_inc("sprites_active_total")
        gauge_inc("sprites_active_total")
        gauge_dec("sprites_active_total")
        snap = get_snapshot()
        assert snap["gauges"]["sprites_active_total"] == 1.0

    def test_gauge_dec_below_zero(self):
        gauge_dec("sprites_active_total")
        snap = get_snapshot()
        assert snap["gauges"]["sprites_active_total"] == -1.0


class TestTimed:
    def test_records_duration(self):
        with timed("test_op") as t:
            pass  # instant
        assert "duration_ms" in t
        assert t["duration_ms"] >= 0
        snap = get_snapshot()
        assert snap["histograms"]["test_op"]["count"] == 1

    def test_records_duration_on_error(self):
        with pytest.raises(ValueError):
            with timed("test_op") as t:
                raise ValueError("boom")
        assert "duration_ms" in t
        snap = get_snapshot()
        assert snap["histograms"]["test_op"]["count"] == 1

    def test_timed_with_tags(self):
        with timed("op", tags={"sandbox_id": "sb-1"}):
            pass
        snap = get_snapshot()
        assert "op{sandbox_id=sb-1}" in snap["histograms"]


class TestSnapshot:
    def test_empty_snapshot(self):
        snap = get_snapshot()
        assert snap == {}

    def test_snapshot_excludes_empty_sections(self):
        record("c")
        snap = get_snapshot()
        assert "counters" in snap
        assert "gauges" not in snap
        assert "histograms" not in snap


class TestReset:
    def test_clears_all(self):
        record("c")
        gauge_inc("g")
        record("h", value=1.0, kind="histogram")
        reset()
        assert get_snapshot() == {}


class TestLogRedaction:
    """Verify that the metrics module itself doesn't log secrets.

    The metrics module only stores numeric values and string keys/tags.
    Credential values should never appear as metric names or tag values.
    """

    def test_no_credential_in_tags(self):
        # Simulate what SpritesProvider does - only sandbox_id in tags
        record(
            "sprite_health_check_failures_total",
            tags={"sandbox_id": "sb-user123"},
        )
        snap = get_snapshot()
        key = list(snap["counters"].keys())[0]
        assert "api_key" not in key.lower()
        assert "token" not in key.lower()
        assert "secret" not in key.lower()
