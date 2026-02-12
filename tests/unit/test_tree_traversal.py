"""Unit tests for bounded tree traversal and degradation."""
import time

import pytest

from boring_ui.api.tree_traversal import (
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_NODES,
    DEFAULT_TIME_BUDGET,
    TraversalBudget,
    TraversalConfig,
    TraversalResult,
    TraversalStatus,
    TreeEntry,
    validate_tree_path,
)


# ── TreeEntry ──


class TestTreeEntry:

    def test_dir_entry(self):
        e = TreeEntry(name='src', path='src', is_dir=True, depth=0)
        d = e.to_dict()
        assert d == {'name': 'src', 'path': 'src', 'is_dir': True}
        assert 'size' not in d

    def test_file_entry(self):
        e = TreeEntry(name='main.py', path='src/main.py', is_dir=False, depth=1, size=1024)
        d = e.to_dict()
        assert d['name'] == 'main.py'
        assert d['size'] == 1024
        assert d['is_dir'] is False

    def test_frozen(self):
        e = TreeEntry(name='a', path='a', is_dir=True, depth=0)
        with pytest.raises(AttributeError):
            e.name = 'b'


# ── TraversalResult ──


class TestTraversalResult:

    def test_complete(self):
        result = TraversalResult(
            entries=[TreeEntry(name='a', path='a', is_dir=True, depth=0)],
            status=TraversalStatus.COMPLETE,
            root_path='.',
        )
        assert result.is_complete
        assert not result.is_truncated

    def test_truncated_node(self):
        result = TraversalResult(status=TraversalStatus.NODE_LIMITED)
        assert result.is_truncated
        assert not result.is_complete

    def test_truncated_depth(self):
        result = TraversalResult(status=TraversalStatus.DEPTH_LIMITED)
        assert result.is_truncated

    def test_truncated_time(self):
        result = TraversalResult(status=TraversalStatus.TIME_LIMITED)
        assert result.is_truncated

    def test_error(self):
        result = TraversalResult(
            status=TraversalStatus.ERROR,
            error_message='permission denied',
        )
        assert not result.is_complete
        assert not result.is_truncated

    def test_to_response_complete(self):
        entries = [TreeEntry(name='a', path='a', is_dir=True, depth=0)]
        result = TraversalResult(entries=entries, root_path='src')
        resp = result.to_response()
        assert resp['path'] == 'src'
        assert len(resp['entries']) == 1
        assert 'truncated' not in resp

    def test_to_response_truncated(self):
        result = TraversalResult(
            status=TraversalStatus.NODE_LIMITED,
            root_path='.',
            total_visited=10000,
        )
        resp = result.to_response()
        assert resp['truncated'] is True
        assert resp['truncation_reason'] == 'node_limited'
        assert resp['total_visited'] == 10000


# ── TraversalConfig ──


class TestTraversalConfig:

    def test_defaults(self):
        cfg = TraversalConfig()
        assert cfg.max_nodes == DEFAULT_MAX_NODES
        assert cfg.max_depth == DEFAULT_MAX_DEPTH
        assert cfg.time_budget == DEFAULT_TIME_BUDGET

    def test_custom(self):
        cfg = TraversalConfig(max_nodes=100, max_depth=5, time_budget=1.0)
        assert cfg.max_nodes == 100
        assert cfg.max_depth == 5
        assert cfg.time_budget == 1.0


# ── TraversalBudget ──


class TestTraversalBudget:

    def test_initial_state(self):
        budget = TraversalBudget()
        assert budget.node_count == 0
        assert budget.max_depth_seen == 0
        assert not budget.is_exhausted

    def test_check_node(self):
        budget = TraversalBudget(TraversalConfig(max_nodes=3))
        assert budget.check_node()
        assert budget.check_node()
        assert budget.check_node()
        assert not budget.check_node()  # 4th exceeds limit
        assert budget.is_exhausted
        assert budget.exhaustion_reason == TraversalStatus.NODE_LIMITED

    def test_check_depth(self):
        budget = TraversalBudget(TraversalConfig(max_depth=2))
        assert budget.check_depth(0)
        assert budget.check_depth(1)
        assert budget.check_depth(2)
        assert not budget.check_depth(3)
        assert budget.exhaustion_reason == TraversalStatus.DEPTH_LIMITED

    def test_check_depth_tracks_max(self):
        budget = TraversalBudget()
        budget.check_depth(0)
        budget.check_depth(3)
        budget.check_depth(1)
        assert budget.max_depth_seen == 3

    def test_check_time(self):
        budget = TraversalBudget(TraversalConfig(time_budget=0.0))
        time.sleep(0.01)
        assert not budget.check_time()
        assert budget.exhaustion_reason == TraversalStatus.TIME_LIMITED

    def test_check_time_within_budget(self):
        budget = TraversalBudget(TraversalConfig(time_budget=10.0))
        assert budget.check_time()

    def test_check_all_passes(self):
        budget = TraversalBudget(TraversalConfig(
            max_nodes=100, max_depth=10, time_budget=10.0,
        ))
        assert budget.check_all(depth=1)
        assert budget.node_count == 1

    def test_check_all_depth_fail(self):
        budget = TraversalBudget(TraversalConfig(max_depth=1))
        assert not budget.check_all(depth=5)

    def test_check_all_node_fail(self):
        budget = TraversalBudget(TraversalConfig(max_nodes=1))
        budget.check_all(depth=0)
        assert not budget.check_all(depth=0)

    def test_sanitize_name(self):
        budget = TraversalBudget(TraversalConfig(max_entry_name_length=5))
        assert budget.sanitize_name('hello') == 'hello'
        assert budget.sanitize_name('hello world') == 'hello'

    def test_sanitize_name_within_limit(self):
        budget = TraversalBudget()
        assert budget.sanitize_name('short') == 'short'

    def test_build_result_complete(self):
        budget = TraversalBudget()
        entries = [TreeEntry(name='a', path='a', is_dir=True, depth=0)]
        budget.check_node()
        result = budget.build_result(entries, '.')
        assert result.status == TraversalStatus.COMPLETE
        assert result.total_visited == 1

    def test_build_result_exhausted(self):
        budget = TraversalBudget(TraversalConfig(max_nodes=1))
        budget.check_node()
        budget.check_node()  # Exceeds
        result = budget.build_result([], '.')
        assert result.status == TraversalStatus.NODE_LIMITED

    def test_elapsed(self):
        budget = TraversalBudget()
        time.sleep(0.01)
        assert budget.elapsed >= 0.01

    def test_config_property(self):
        cfg = TraversalConfig(max_nodes=42)
        budget = TraversalBudget(cfg)
        assert budget.config.max_nodes == 42


# ── validate_tree_path ──


class TestValidateTreePath:

    def test_valid_simple(self):
        assert validate_tree_path('.') is None

    def test_valid_nested(self):
        assert validate_tree_path('src/components') is None

    def test_traversal_dotdot(self):
        err = validate_tree_path('../etc/passwd')
        assert err is not None
        assert 'traversal' in err.lower()

    def test_traversal_mid_path(self):
        err = validate_tree_path('src/../../etc')
        assert err is not None

    def test_absolute_path(self):
        err = validate_tree_path('/etc/passwd')
        assert err is not None
        assert 'absolute' in err.lower()

    def test_null_byte(self):
        err = validate_tree_path('src/\x00evil')
        assert err is not None
        assert 'null' in err.lower()

    def test_dotdot_in_name_ok(self):
        # "foo..bar" is fine, only ".." as a path component is bad
        assert validate_tree_path('foo..bar') is None
