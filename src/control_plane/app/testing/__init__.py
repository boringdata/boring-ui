"""Scenario runner and testing infrastructure for E2E validation."""

from .scenario_parser import (
    ApiSignal,
    FailureMode,
    ScenarioSpec,
    parse_scenario,
    parse_scenario_file,
    scan_scenario_dir,
)
from .scenario_runner import (
    RunConfig,
    ScenarioResult,
    ScenarioRunner,
    StepOutcome,
    StepResult,
)
from .run_log import RunLog
from .visual_proof import (
    ArtifactType,
    BrowserCapture,
    CaptureConfig,
    EvidenceArtifact,
    ProofSession,
)
from .proof_report import (
    ProofReportBuilder,
    build_proof_report,
)
from .evidence_store import (
    AttachedScenario,
    EvidenceStore,
    format_beads_comment,
)

__all__ = [
    'ApiSignal',
    'ArtifactType',
    'AttachedScenario',
    'BrowserCapture',
    'CaptureConfig',
    'EvidenceArtifact',
    'EvidenceStore',
    'FailureMode',
    'ProofReportBuilder',
    'ProofSession',
    'RunConfig',
    'RunLog',
    'ScenarioResult',
    'ScenarioRunner',
    'ScenarioSpec',
    'StepOutcome',
    'StepResult',
    'build_proof_report',
    'format_beads_comment',
    'parse_scenario',
    'parse_scenario_file',
    'scan_scenario_dir',
]
