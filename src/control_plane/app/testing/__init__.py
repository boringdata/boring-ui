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

__all__ = [
    'ApiSignal',
    'ArtifactType',
    'BrowserCapture',
    'CaptureConfig',
    'EvidenceArtifact',
    'FailureMode',
    'ProofReportBuilder',
    'ProofSession',
    'RunConfig',
    'ScenarioResult',
    'ScenarioRunner',
    'ScenarioSpec',
    'StepOutcome',
    'StepResult',
    'build_proof_report',
    'parse_scenario',
    'parse_scenario_file',
    'scan_scenario_dir',
]
