"""Guards for bd-3g1g.2.1 finalized agent route prefix contract."""

from pathlib import Path


PLAN_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs/SERVICE_SPLIT_AND_LEGACY_CLEANUP_PLAN.md"
)


REQUIRED_FAMILIES = [
    "/api/v1/agent/normal/*",
    "/ws/agent/normal/*",
    "/api/v1/agent/companion/*",
    "/ws/agent/companion/*",
    "/api/v1/agent/pi/*",
    "/ws/agent/pi/*",
]


FORBIDDEN_PROVISIONAL_LINES = [
    "Provisional prefix `/api/v1/agent/normal/*`",
    "Provisional prefix `/api/v1/agent/companion/*`",
    "Provisional prefix `/api/v1/agent/pi/*`",
]


def test_plan_exists() -> None:
    assert PLAN_PATH.exists(), f"Missing plan doc: {PLAN_PATH}"


def test_agent_prefix_contract_section_present() -> None:
    text = PLAN_PATH.read_text(encoding="utf-8")
    assert "Finalized Agent Route Prefix Contract (Phase 1)" in text


def test_agent_prefix_families_are_finalized() -> None:
    text = PLAN_PATH.read_text(encoding="utf-8")
    missing = [family for family in REQUIRED_FAMILIES if family not in text]
    assert not missing, "Missing finalized agent route families:\n- " + "\n- ".join(missing)


def test_provisional_agent_prefix_language_removed() -> None:
    text = PLAN_PATH.read_text(encoding="utf-8")
    found = [line for line in FORBIDDEN_PROVISIONAL_LINES if line in text]
    assert not found, "Found provisional agent prefix language:\n- " + "\n- ".join(found)

