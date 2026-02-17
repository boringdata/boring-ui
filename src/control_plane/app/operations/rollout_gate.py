"""Production rollout gate checklist.

Bead: bd-223o.15.6 (J6)

Consolidates dependency, acceptance, test, and operations evidence into a
single gate that blocks production release until all required conditions are
met.

Gate categories:
  - OPERATIONAL: SLO alerts active, runbooks authored, drills completed
  - SECURITY: Auth hardened, token rotation tested, proxy redaction verified
  - PROVISIONING: State machine tested, stale job detection, checksum verified
  - OBSERVABILITY: Dashboards, alert routing, escalation paths validated
  - RELEASE: Artifact integrity, changelog, rollback procedure documented

Each gate item tracks:
  - Gate category and unique key
  - Human-readable requirement description
  - Evidence source (test file, runbook reference, or manual attestation)
  - Pass/fail status with optional failure detail

The gate blocks release when any required item is not satisfied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


class GateCategory(Enum):
    """Categories of rollout gate checks."""

    OPERATIONAL = 'operational'
    SECURITY = 'security'
    PROVISIONING = 'provisioning'
    OBSERVABILITY = 'observability'
    RELEASE = 'release'


class GateStatus(Enum):
    """Status of a gate item."""

    PENDING = 'pending'
    PASSED = 'passed'
    FAILED = 'failed'
    WAIVED = 'waived'


@dataclass(frozen=True, slots=True)
class GateItem:
    """Single item in the rollout gate checklist.

    Attributes:
        category: Which gate category this belongs to.
        key: Unique identifier within the category.
        requirement: Human-readable description of what must be true.
        evidence_source: Where the evidence comes from.
        required: Whether this item blocks release.
        status: Current pass/fail status.
        detail: Optional detail about pass/fail outcome.
    """

    category: GateCategory
    key: str
    requirement: str
    evidence_source: str
    required: bool = True
    status: GateStatus = GateStatus.PENDING
    detail: str = ''


@dataclass(frozen=True, slots=True)
class RolloutGateChecklist:
    """Complete production rollout gate checklist.

    Attributes:
        items: All gate items in evaluation order.
        release_id: Release identifier being gated.
        owner: Release manager or on-call owner.
    """

    items: tuple[GateItem, ...]
    release_id: str
    owner: str

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def required_count(self) -> int:
        return sum(1 for item in self.items if item.required)

    @property
    def passed_count(self) -> int:
        return sum(
            1 for item in self.items
            if item.status in (GateStatus.PASSED, GateStatus.WAIVED)
        )

    @property
    def failed_count(self) -> int:
        return sum(
            1 for item in self.items
            if item.status == GateStatus.FAILED
        )

    @property
    def pending_count(self) -> int:
        return sum(
            1 for item in self.items
            if item.status == GateStatus.PENDING
        )

    @property
    def blocking_failures(self) -> tuple[GateItem, ...]:
        """Items that are required AND failed."""
        return tuple(
            item for item in self.items
            if item.required and item.status == GateStatus.FAILED
        )

    @property
    def blocking_pending(self) -> tuple[GateItem, ...]:
        """Items that are required AND still pending."""
        return tuple(
            item for item in self.items
            if item.required and item.status == GateStatus.PENDING
        )

    @property
    def release_blocked(self) -> bool:
        """True if any required item is not passed/waived."""
        return len(self.blocking_failures) > 0 or len(self.blocking_pending) > 0

    @property
    def items_by_category(self) -> dict[GateCategory, list[GateItem]]:
        result: dict[GateCategory, list[GateItem]] = {}
        for item in self.items:
            result.setdefault(item.category, []).append(item)
        return result


# ── Gate item factory ──────────────────────────────────────────────


def build_rollout_gate_checklist(
    release_id: str = 'pending',
    owner: str = 'release_manager',
) -> RolloutGateChecklist:
    """Build the canonical production rollout gate checklist.

    All items start as PENDING. Evaluation logic updates status
    based on evidence collection.
    """

    items = (
        # ── Operational gates (J1-J5) ──────────────────────────────
        GateItem(
            category=GateCategory.OPERATIONAL,
            key='slo_alerts_defined',
            requirement='SLO alert catalog defined and validated',
            evidence_source='tests/unit/control_plane/test_slo_operational_catalog.py',
        ),
        GateItem(
            category=GateCategory.OPERATIONAL,
            key='stale_job_detector',
            requirement='Stale provisioning-job detector implemented and tested',
            evidence_source='tests/unit/control_plane/test_stale_job_detector.py',
        ),
        GateItem(
            category=GateCategory.OPERATIONAL,
            key='sprite_rotation_runbook',
            requirement='Sprite bearer rotation runbook authored and validated',
            evidence_source='tests/unit/control_plane/test_sprite_rotation_runbook.py',
        ),
        GateItem(
            category=GateCategory.OPERATIONAL,
            key='checksum_failure_runbook',
            requirement='Checksum-failure operator runbook authored and validated',
            evidence_source='tests/unit/control_plane/test_checksum_failure_runbook.py',
        ),
        GateItem(
            category=GateCategory.OPERATIONAL,
            key='outage_drill_catalog',
            requirement='Cross-epic outage drill catalog defined with evidence requirements',
            evidence_source='tests/unit/control_plane/test_outage_drill.py',
        ),

        # ── Security gates (B-epic) ───────────────────────────────
        GateItem(
            category=GateCategory.SECURITY,
            key='auth_guard_tested',
            requirement='Auth guard middleware covers Bearer, session, and exempt paths',
            evidence_source='tests/unit/control_plane/test_auth_guard.py',
        ),
        GateItem(
            category=GateCategory.SECURITY,
            key='auth_transport_tested',
            requirement='Auth transport extraction and precedence validated',
            evidence_source='tests/unit/control_plane/test_auth_transport.py',
        ),
        GateItem(
            category=GateCategory.SECURITY,
            key='session_fixation_prevented',
            requirement='Auth callback always issues fresh session token',
            evidence_source='tests/unit/control_plane/test_auth_security_integration.py',
        ),
        GateItem(
            category=GateCategory.SECURITY,
            key='token_leakage_prevented',
            requirement='401 responses never echo submitted credentials',
            evidence_source='tests/unit/control_plane/test_auth_security_integration.py',
        ),
        GateItem(
            category=GateCategory.SECURITY,
            key='proxy_redaction_verified',
            requirement='Proxy responses do not leak bearer tokens or service headers',
            evidence_source='tests/unit/control_plane/test_proxy_security.py',
        ),
        GateItem(
            category=GateCategory.SECURITY,
            key='cookie_flags_hardened',
            requirement='Session cookies use Secure, HttpOnly, SameSite=Lax',
            evidence_source='tests/unit/control_plane/test_cookie_flag_matrix.py',
        ),

        # ── Provisioning gates (D-epic) ───────────────────────────
        GateItem(
            category=GateCategory.PROVISIONING,
            key='state_machine_tested',
            requirement='Provisioning state machine transitions and timeouts validated',
            evidence_source='tests/unit/control_plane/test_state_machine.py',
        ),
        GateItem(
            category=GateCategory.PROVISIONING,
            key='release_contract_validated',
            requirement='Release artifact contract with checksum verification',
            evidence_source='tests/unit/control_plane/test_release_contract.py',
        ),
        GateItem(
            category=GateCategory.PROVISIONING,
            key='idempotency_enforced',
            requirement='Provisioning requests are idempotent with single-active-job locking',
            evidence_source='tests/unit/control_plane/test_provisioning_idempotency.py',
        ),

        # ── Observability gates ────────────────────────────────────
        GateItem(
            category=GateCategory.OBSERVABILITY,
            key='alert_routing_validated',
            requirement='Alert routing and escalation paths are tested',
            evidence_source='tests/unit/control_plane/test_alert_routing_escalation.py',
        ),
        GateItem(
            category=GateCategory.OBSERVABILITY,
            key='dashboards_defined',
            requirement='Operational dashboards defined for API, provisioning, and proxy',
            evidence_source='tests/unit/control_plane/test_slo_operational_catalog.py',
        ),
        GateItem(
            category=GateCategory.OBSERVABILITY,
            key='request_correlation',
            requirement='All drill evidence entries carry request-id correlation',
            evidence_source='tests/unit/control_plane/test_outage_drill.py',
        ),

        # ── Release gates ─────────────────────────────────────────
        GateItem(
            category=GateCategory.RELEASE,
            key='artifact_integrity',
            requirement='Release artifacts pass checksum verification',
            evidence_source='release_contract.validate_artifact()',
        ),
        GateItem(
            category=GateCategory.RELEASE,
            key='rollback_documented',
            requirement='Rollback procedure documented for each deployment component',
            evidence_source='sprite_rotation.py + modal deploy rollback',
        ),
        GateItem(
            category=GateCategory.RELEASE,
            key='all_drills_passed',
            requirement='All required outage drills executed with passing evidence',
            evidence_source='outage_drill.validate_drill_result()',
            required=True,
        ),
        GateItem(
            category=GateCategory.RELEASE,
            key='runbook_owners_assigned',
            requirement='All runbooks have assigned escalation owners',
            evidence_source='slo_alerts.REQUIRED_ESCALATION_OWNERS',
        ),
    )

    return RolloutGateChecklist(
        items=items,
        release_id=release_id,
        owner=owner,
    )


DEFAULT_ROLLOUT_GATE = build_rollout_gate_checklist()


# ── Required contracts ─────────────────────────────────────────────

REQUIRED_CATEGORIES = frozenset(GateCategory)

MINIMUM_ITEMS_PER_CATEGORY = {
    GateCategory.OPERATIONAL: 5,
    GateCategory.SECURITY: 5,
    GateCategory.PROVISIONING: 3,
    GateCategory.OBSERVABILITY: 3,
    GateCategory.RELEASE: 4,
}


# ── Validation ─────────────────────────────────────────────────────


def validate_rollout_gate(checklist: RolloutGateChecklist) -> None:
    """Validate that the rollout gate checklist meets structural requirements.

    Raises:
        ValueError: If required contracts are not met.
    """
    # All categories covered.
    covered = set(checklist.items_by_category.keys())
    missing = REQUIRED_CATEGORIES - covered
    if missing:
        raise ValueError(
            f'Missing gate categories: {sorted(c.value for c in missing)}'
        )

    # Minimum items per category.
    for cat, minimum in MINIMUM_ITEMS_PER_CATEGORY.items():
        count = len(checklist.items_by_category.get(cat, []))
        if count < minimum:
            raise ValueError(
                f'Category {cat.value!r} has {count} items, '
                f'minimum {minimum} required'
            )

    # All items have non-empty requirements and evidence.
    for item in checklist.items:
        if not item.requirement.strip():
            raise ValueError(f'Gate item {item.key!r} has no requirement')
        if not item.evidence_source.strip():
            raise ValueError(f'Gate item {item.key!r} has no evidence source')

    # No duplicate keys within a category.
    for cat, items in checklist.items_by_category.items():
        keys = [item.key for item in items]
        if len(keys) != len(set(keys)):
            raise ValueError(f'Duplicate keys in category {cat.value!r}')

    # Owner required.
    if not checklist.owner:
        raise ValueError('Rollout gate checklist has no owner')

    # Release ID required.
    if not checklist.release_id:
        raise ValueError('Rollout gate checklist has no release_id')

    # At least one required item exists.
    if checklist.required_count == 0:
        raise ValueError('Rollout gate has no required items')
