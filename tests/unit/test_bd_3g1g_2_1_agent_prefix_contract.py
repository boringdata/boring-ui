"""Guards for bd-3g1g.2.1 finalized agent route prefix contract."""

from pathlib import Path
import re


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

SECTION_START = "### Finalized Agent Route Prefix Contract (Phase 1)"
SECTION_END = "## Frontend -> Control Plane Route Contract"


def test_plan_exists() -> None:
    assert PLAN_PATH.exists(), f"Missing plan doc: {PLAN_PATH}"


def test_agent_prefix_contract_section_present() -> None:
    text = PLAN_PATH.read_text(encoding="utf-8")
    assert SECTION_START in text


def _extract_finalized_contract_section(text: str) -> str:
    start = text.find(SECTION_START)
    assert start >= 0, "Missing finalized contract section start"

    end = text.find(SECTION_END, start)
    assert end >= 0, "Missing finalized contract section end"
    return text[start:end]


def test_agent_prefix_families_are_finalized() -> None:
    text = PLAN_PATH.read_text(encoding="utf-8")
    section = _extract_finalized_contract_section(text)

    family_matches = re.findall(
        r"/(?:api/v1|ws)/agent/(?:normal|companion|pi)/\*",
        section,
    )
    actual = set(family_matches)
    expected = set(REQUIRED_FAMILIES)

    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)

    assert not missing, "Missing finalized agent route families:\n- " + "\n- ".join(missing)
    assert not unexpected, "Unexpected finalized agent route families:\n- " + "\n- ".join(unexpected)


def test_provisional_agent_prefix_language_removed() -> None:
    text = PLAN_PATH.read_text(encoding="utf-8")
    found = [line for line in FORBIDDEN_PROVISIONAL_LINES if line in text]
    assert not found, "Found provisional agent prefix language:\n- " + "\n- ".join(found)

    pattern = re.compile(
        r"provisional.{0,200}/(?:api/v1|ws)/agent/(?:normal|companion|pi)/\*",
        re.IGNORECASE | re.DOTALL,
    )
    assert not pattern.search(text), "Found regex match for provisional agent prefix language"
