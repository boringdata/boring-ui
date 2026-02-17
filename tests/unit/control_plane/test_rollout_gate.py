"""Production rollout gate checklist tests.

Bead: bd-223o.15.6 (J6)

Validates:
  - Gate checklist covers all required categories
  - Minimum items per category are present
  - All items have requirements and evidence sources
  - No duplicate keys within categories
  - Gate blocking logic (required + pending/failed = blocked)
  - Gate passes when all required items pass
  - Validation catches structural defects
  - Frozen dataclass invariants hold
  - Idempotent construction
  - Cross-epic gate items reference correct evidence sources
"""

from __future__ import annotations

import pytest

from control_plane.app.operations.rollout_gate import (
    DEFAULT_ROLLOUT_GATE,
    MINIMUM_ITEMS_PER_CATEGORY,
    REQUIRED_CATEGORIES,
    GateCategory,
    GateItem,
    GateStatus,
    RolloutGateChecklist,
    build_rollout_gate_checklist,
    validate_rollout_gate,
)


@pytest.fixture
def checklist():
    return DEFAULT_ROLLOUT_GATE


# =====================================================================
# 1. Category coverage
# =====================================================================


class TestCategoryCoverage:
    """Gate must cover all required categories."""

    def test_all_required_categories_covered(self, checklist):
        covered = set(checklist.items_by_category.keys())
        assert REQUIRED_CATEGORIES.issubset(covered)

    def test_operational_category_present(self, checklist):
        assert GateCategory.OPERATIONAL in checklist.items_by_category

    def test_security_category_present(self, checklist):
        assert GateCategory.SECURITY in checklist.items_by_category

    def test_provisioning_category_present(self, checklist):
        assert GateCategory.PROVISIONING in checklist.items_by_category

    def test_observability_category_present(self, checklist):
        assert GateCategory.OBSERVABILITY in checklist.items_by_category

    def test_release_category_present(self, checklist):
        assert GateCategory.RELEASE in checklist.items_by_category


# =====================================================================
# 2. Minimum items per category
# =====================================================================


class TestMinimumItems:
    """Each category meets its minimum item count."""

    def test_operational_minimum(self, checklist):
        items = checklist.items_by_category[GateCategory.OPERATIONAL]
        assert len(items) >= MINIMUM_ITEMS_PER_CATEGORY[GateCategory.OPERATIONAL]

    def test_security_minimum(self, checklist):
        items = checklist.items_by_category[GateCategory.SECURITY]
        assert len(items) >= MINIMUM_ITEMS_PER_CATEGORY[GateCategory.SECURITY]

    def test_provisioning_minimum(self, checklist):
        items = checklist.items_by_category[GateCategory.PROVISIONING]
        assert len(items) >= MINIMUM_ITEMS_PER_CATEGORY[GateCategory.PROVISIONING]

    def test_observability_minimum(self, checklist):
        items = checklist.items_by_category[GateCategory.OBSERVABILITY]
        assert len(items) >= MINIMUM_ITEMS_PER_CATEGORY[GateCategory.OBSERVABILITY]

    def test_release_minimum(self, checklist):
        items = checklist.items_by_category[GateCategory.RELEASE]
        assert len(items) >= MINIMUM_ITEMS_PER_CATEGORY[GateCategory.RELEASE]


# =====================================================================
# 3. Item completeness
# =====================================================================


class TestItemCompleteness:
    """All items have requirements and evidence sources."""

    def test_all_have_requirements(self, checklist):
        for item in checklist.items:
            assert item.requirement.strip(), (
                f'Item {item.key!r} has no requirement'
            )

    def test_all_have_evidence_source(self, checklist):
        for item in checklist.items:
            assert item.evidence_source.strip(), (
                f'Item {item.key!r} has no evidence source'
            )

    def test_all_have_unique_keys_per_category(self, checklist):
        for cat, items in checklist.items_by_category.items():
            keys = [item.key for item in items]
            assert len(keys) == len(set(keys)), (
                f'Duplicate keys in {cat.value}'
            )

    def test_all_have_non_empty_keys(self, checklist):
        for item in checklist.items:
            assert item.key.strip()


# =====================================================================
# 4. Gate blocking logic
# =====================================================================


class TestGateBlocking:
    """Gate blocks release when required items are not satisfied."""

    def test_all_pending_means_blocked(self, checklist):
        # Default checklist has all items PENDING.
        assert checklist.release_blocked is True

    def test_all_passed_means_unblocked(self):
        items = tuple(
            GateItem(
                category=GateCategory.OPERATIONAL,
                key=f'item_{i}',
                requirement='Test',
                evidence_source='test.py',
                status=GateStatus.PASSED,
            )
            for i in range(5)
        )
        gate = RolloutGateChecklist(
            items=items,
            release_id='v1.0',
            owner='owner',
        )
        assert gate.release_blocked is False

    def test_waived_items_do_not_block(self):
        items = (
            GateItem(
                category=GateCategory.OPERATIONAL,
                key='item_1',
                requirement='Test',
                evidence_source='test.py',
                required=True,
                status=GateStatus.WAIVED,
            ),
        )
        gate = RolloutGateChecklist(
            items=items,
            release_id='v1.0',
            owner='owner',
        )
        assert gate.release_blocked is False

    def test_one_failed_required_blocks(self):
        items = (
            GateItem(
                category=GateCategory.OPERATIONAL,
                key='passed_item',
                requirement='Test',
                evidence_source='test.py',
                status=GateStatus.PASSED,
            ),
            GateItem(
                category=GateCategory.SECURITY,
                key='failed_item',
                requirement='Test',
                evidence_source='test.py',
                required=True,
                status=GateStatus.FAILED,
                detail='Auth check failed',
            ),
        )
        gate = RolloutGateChecklist(
            items=items,
            release_id='v1.0',
            owner='owner',
        )
        assert gate.release_blocked is True
        assert len(gate.blocking_failures) == 1
        assert gate.blocking_failures[0].key == 'failed_item'

    def test_non_required_failure_does_not_block(self):
        items = (
            GateItem(
                category=GateCategory.OPERATIONAL,
                key='passed_item',
                requirement='Test',
                evidence_source='test.py',
                status=GateStatus.PASSED,
            ),
            GateItem(
                category=GateCategory.SECURITY,
                key='optional_failed',
                requirement='Test',
                evidence_source='test.py',
                required=False,
                status=GateStatus.FAILED,
            ),
        )
        gate = RolloutGateChecklist(
            items=items,
            release_id='v1.0',
            owner='owner',
        )
        assert gate.release_blocked is False

    def test_blocking_pending_tracked(self, checklist):
        assert len(checklist.blocking_pending) == checklist.required_count


# =====================================================================
# 5. Checklist properties
# =====================================================================


class TestChecklistProperties:
    """Aggregate properties are correct."""

    def test_item_count(self, checklist):
        assert checklist.item_count == len(checklist.items)
        assert checklist.item_count >= 20

    def test_required_count(self, checklist):
        assert checklist.required_count > 0
        assert checklist.required_count <= checklist.item_count

    def test_all_default_items_are_pending(self, checklist):
        assert checklist.pending_count == checklist.item_count

    def test_passed_count_starts_zero(self, checklist):
        assert checklist.passed_count == 0

    def test_failed_count_starts_zero(self, checklist):
        assert checklist.failed_count == 0

    def test_default_owner(self, checklist):
        assert checklist.owner == 'release_manager'

    def test_default_release_id(self, checklist):
        assert checklist.release_id == 'pending'

    def test_custom_release_id(self):
        gate = build_rollout_gate_checklist(release_id='v1.0.0')
        assert gate.release_id == 'v1.0.0'

    def test_custom_owner(self):
        gate = build_rollout_gate_checklist(owner='deploy_lead')
        assert gate.owner == 'deploy_lead'


# =====================================================================
# 6. Validation
# =====================================================================


class TestValidation:
    """validate_rollout_gate catches incomplete checklists."""

    def test_default_passes_validation(self, checklist):
        validate_rollout_gate(checklist)

    def test_built_passes_validation(self):
        validate_rollout_gate(build_rollout_gate_checklist())

    def test_missing_category_raises(self):
        # Only include operational items.
        items = tuple(
            GateItem(
                category=GateCategory.OPERATIONAL,
                key=f'op_{i}',
                requirement='Test',
                evidence_source='test.py',
            )
            for i in range(5)
        )
        gate = RolloutGateChecklist(
            items=items,
            release_id='v1.0',
            owner='owner',
        )
        with pytest.raises(ValueError, match='Missing gate categories'):
            validate_rollout_gate(gate)

    def test_too_few_items_in_category_raises(self):
        # Build minimal checklist with all categories but only 1 operational item.
        items = (
            GateItem(category=GateCategory.OPERATIONAL, key='op_1',
                     requirement='t', evidence_source='t'),
            *(GateItem(category=GateCategory.SECURITY, key=f's_{i}',
                       requirement='t', evidence_source='t') for i in range(6)),
            *(GateItem(category=GateCategory.PROVISIONING, key=f'p_{i}',
                       requirement='t', evidence_source='t') for i in range(3)),
            *(GateItem(category=GateCategory.OBSERVABILITY, key=f'o_{i}',
                       requirement='t', evidence_source='t') for i in range(3)),
            *(GateItem(category=GateCategory.RELEASE, key=f'r_{i}',
                       requirement='t', evidence_source='t') for i in range(4)),
        )
        gate = RolloutGateChecklist(items=items, release_id='v1.0', owner='o')
        with pytest.raises(ValueError, match='operational.*has 1 items'):
            validate_rollout_gate(gate)

    def test_empty_requirement_raises(self):
        items = list(DEFAULT_ROLLOUT_GATE.items)
        items[0] = GateItem(
            category=items[0].category,
            key=items[0].key,
            requirement='',
            evidence_source=items[0].evidence_source,
        )
        gate = RolloutGateChecklist(
            items=tuple(items),
            release_id='v1.0',
            owner='owner',
        )
        with pytest.raises(ValueError, match='no requirement'):
            validate_rollout_gate(gate)

    def test_empty_evidence_source_raises(self):
        items = list(DEFAULT_ROLLOUT_GATE.items)
        items[0] = GateItem(
            category=items[0].category,
            key=items[0].key,
            requirement=items[0].requirement,
            evidence_source='',
        )
        gate = RolloutGateChecklist(
            items=tuple(items),
            release_id='v1.0',
            owner='owner',
        )
        with pytest.raises(ValueError, match='no evidence source'):
            validate_rollout_gate(gate)

    def test_duplicate_keys_raises(self):
        items = list(DEFAULT_ROLLOUT_GATE.items)
        # Duplicate first item.
        items.append(items[0])
        gate = RolloutGateChecklist(
            items=tuple(items),
            release_id='v1.0',
            owner='owner',
        )
        with pytest.raises(ValueError, match='Duplicate keys'):
            validate_rollout_gate(gate)

    def test_empty_owner_raises(self):
        gate = RolloutGateChecklist(
            items=DEFAULT_ROLLOUT_GATE.items,
            release_id='v1.0',
            owner='',
        )
        with pytest.raises(ValueError, match='no owner'):
            validate_rollout_gate(gate)

    def test_empty_release_id_raises(self):
        gate = RolloutGateChecklist(
            items=DEFAULT_ROLLOUT_GATE.items,
            release_id='',
            owner='owner',
        )
        with pytest.raises(ValueError, match='no release_id'):
            validate_rollout_gate(gate)

    def test_no_required_items_raises(self):
        items = tuple(
            GateItem(
                category=cat,
                key=f'{cat.value}_{i}',
                requirement='t',
                evidence_source='t',
                required=False,
            )
            for cat in GateCategory
            for i in range(MINIMUM_ITEMS_PER_CATEGORY[cat])
        )
        gate = RolloutGateChecklist(items=items, release_id='v1', owner='o')
        with pytest.raises(ValueError, match='no required items'):
            validate_rollout_gate(gate)


# =====================================================================
# 7. Cross-epic evidence references
# =====================================================================


class TestCrossEpicReferences:
    """Gate items reference correct test files and evidence sources."""

    def test_slo_alerts_references_test(self, checklist):
        items = {item.key: item for item in checklist.items}
        assert 'test_slo_operational_catalog' in items['slo_alerts_defined'].evidence_source

    def test_stale_job_references_test(self, checklist):
        items = {item.key: item for item in checklist.items}
        assert 'test_stale_job_detector' in items['stale_job_detector'].evidence_source

    def test_rotation_references_test(self, checklist):
        items = {item.key: item for item in checklist.items}
        assert 'test_sprite_rotation' in items['sprite_rotation_runbook'].evidence_source

    def test_checksum_references_test(self, checklist):
        items = {item.key: item for item in checklist.items}
        assert 'test_checksum_failure' in items['checksum_failure_runbook'].evidence_source

    def test_drill_references_test(self, checklist):
        items = {item.key: item for item in checklist.items}
        assert 'test_outage_drill' in items['outage_drill_catalog'].evidence_source

    def test_auth_guard_references_test(self, checklist):
        items = {item.key: item for item in checklist.items}
        assert 'test_auth_guard' in items['auth_guard_tested'].evidence_source

    def test_cookie_flags_references_test(self, checklist):
        items = {item.key: item for item in checklist.items}
        assert 'test_cookie_flag' in items['cookie_flags_hardened'].evidence_source


# =====================================================================
# 8. Frozen dataclass invariants
# =====================================================================


class TestFrozenInvariants:

    def test_checklist_frozen(self, checklist):
        with pytest.raises(AttributeError):
            checklist.owner = 'changed'

    def test_gate_item_frozen(self, checklist):
        with pytest.raises(AttributeError):
            checklist.items[0].status = GateStatus.PASSED

    def test_gate_item_detail_frozen(self, checklist):
        with pytest.raises(AttributeError):
            checklist.items[0].detail = 'changed'


# =====================================================================
# 9. Idempotency
# =====================================================================


class TestIdempotency:

    def test_two_builds_same_item_count(self):
        g1 = build_rollout_gate_checklist()
        g2 = build_rollout_gate_checklist()
        assert g1.item_count == g2.item_count

    def test_two_builds_same_categories(self):
        g1 = build_rollout_gate_checklist()
        g2 = build_rollout_gate_checklist()
        cats1 = set(g1.items_by_category.keys())
        cats2 = set(g2.items_by_category.keys())
        assert cats1 == cats2

    def test_default_matches_build(self):
        fresh = build_rollout_gate_checklist()
        assert DEFAULT_ROLLOUT_GATE.item_count == fresh.item_count
        assert DEFAULT_ROLLOUT_GATE.owner == fresh.owner


# =====================================================================
# 10. Enum values
# =====================================================================


class TestEnumValues:

    def test_gate_categories(self):
        assert GateCategory.OPERATIONAL.value == 'operational'
        assert GateCategory.SECURITY.value == 'security'
        assert GateCategory.PROVISIONING.value == 'provisioning'
        assert GateCategory.OBSERVABILITY.value == 'observability'
        assert GateCategory.RELEASE.value == 'release'

    def test_gate_statuses(self):
        assert GateStatus.PENDING.value == 'pending'
        assert GateStatus.PASSED.value == 'passed'
        assert GateStatus.FAILED.value == 'failed'
        assert GateStatus.WAIVED.value == 'waived'
