"""Integration and dry-run tests for the eval harness.

Run with: python3 -m pytest tests/eval/tests/test_integration.py -v
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

import tests.eval.eval_child_app as eval_child_app_module
from tests.eval.agent_prompt import generate_prompt
from tests.eval.check_catalog import get_checks_by_category
from tests.eval.checks.deployment import DeploymentContext, run_deployment_checks
from tests.eval.checks.local_dev import LocalDevContext, run_local_dev_checks
from tests.eval.checks.report_quality import run_report_quality_checks
from tests.eval.checks.scaffolding import run_scaffolding_checks
from tests.eval.checks.security import run_security_checks
from tests.eval.checks.workflow import run_workflow_checks
from tests.eval.contracts import CheckResult, RunManifest
from tests.eval.eval_child_app import _load_run_state, _save_run_state, run_cleanup_from_state, run_eval
from tests.eval.eval_logger import EvalLogger
from tests.eval.evidence import write_evidence_bundle
from tests.eval.reason_codes import Attribution, CheckStatus
from tests.eval.redaction import SecretRegistry
from tests.eval.report_schema import BEGIN_MARKER, END_MARKER
from tests.eval.runners.mock import MockRunner
from tests.eval.scoring import compute_scores
from tests.eval.tests.helpers import make_project_tree


FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures"

FIXTURE_MANIFESTS = {
    "known-good": {
        "eval_id": "child-eval-20260324T120000Z-goodgood",
        "verification_nonce": "fixture-known-good",
        "app_slug": "ce-0324-goodgood",
        "python_module": "ce_0324_goodgood",
        "expected_status": CheckStatus.PASS,
    },
    "secret-leak": {
        "eval_id": "child-eval-20260324T120000Z-secr3tle",
        "verification_nonce": "fixture-secret-leak",
        "app_slug": "ce-0324-secr3tle",
        "python_module": "ce_0324_secr3tle",
        "expected_status": CheckStatus.FAIL,
    },
    "missing-route": {
        "eval_id": "child-eval-20260324T120000Z-miss1ng0",
        "verification_nonce": "fixture-missing-route",
        "app_slug": "ce-0324-miss1ng0",
        "python_module": "ce_0324_missing",
        "expected_status": CheckStatus.FAIL,
    },
    "broken-deploy": {
        "eval_id": "child-eval-20260324T120000Z-brokende",
        "verification_nonce": "fixture-broken-deploy",
        "app_slug": "ce-0324-brokende",
        "python_module": "ce_0324_brokende",
        "expected_status": CheckStatus.FAIL,
    },
    "malformed-json": {
        "eval_id": "child-eval-20260324T120000Z-malformd",
        "verification_nonce": "fixture-malformed-json",
        "app_slug": "ce-0324-malformd",
        "python_module": "ce_0324_malformd",
        "expected_status": CheckStatus.FAIL,
    },
    "scope-violation": {
        "eval_id": "child-eval-20260324T120000Z-scop3vio",
        "verification_nonce": "fixture-scope-violation",
        "app_slug": "ce-0324-scop3vio",
        "python_module": "ce_0324_scop3vio",
        "expected_status": CheckStatus.FAIL,
    },
    "liar-agent": {
        "eval_id": "child-eval-20260324T120000Z-liaragen",
        "verification_nonce": "fixture-liar-agent",
        "app_slug": "ce-0324-liaragen",
        "python_module": "ce_0324_liaragen",
        "expected_status": CheckStatus.FAIL,
    },
    "scaffold-only": {
        "eval_id": "child-eval-20260324T120000Z-scaffold",
        "verification_nonce": "fixture-scaffold-only",
        "app_slug": "ce-0324-scaffold",
        "python_module": "ce_0324_scaffold",
        "expected_status": CheckStatus.FAIL,
    },
    "env-missing": {
        "eval_id": "child-eval-20260324T120000Z-envmissg",
        "verification_nonce": "fixture-env-missing",
        "app_slug": "ce-0324-envmissg",
        "python_module": "ce_0324_envmissg",
        "expected_status": CheckStatus.INVALID,
    },
}


@dataclass
class EvaluatedFixture:
    manifest: RunManifest
    run_result: object
    checks: list[CheckResult]
    eval_result: object
    cleanup_manifest: object
    evidence_dir: Path


class StaticFlyAdapter:
    def __init__(self, url: str | None):
        self._url = url

    def app_exists(self, app_name: str) -> bool:
        return self._url is not None

    def app_url(self, app_name: str) -> str | None:
        return self._url

    def delete_app(self, app_name: str) -> bool:
        return True


def _manifest_for_fixture(tmp_path: Path, fixture_name: str) -> RunManifest:
    meta = FIXTURE_MANIFESTS[fixture_name]
    project_root = tmp_path / meta["app_slug"]
    evidence_dir = tmp_path / ".eval-evidence" / meta["app_slug"]
    return RunManifest(
        eval_id=meta["eval_id"],
        eval_spec_version="0.1.0",
        report_schema_version="0.1.0",
        platform_profile="core",
        app_slug=meta["app_slug"],
        python_module=meta["python_module"],
        project_root=str(project_root),
        verification_nonce=meta["verification_nonce"],
        required_routes=["/health", "/info"],
        report_output_path=str(evidence_dir / "report.json"),
        event_log_path=str(evidence_dir / "events.jsonl"),
        timeouts={
            "scaffold": 300,
            "local_validation": 120,
            "neon_setup": 180,
            "deploy": 600,
            "live_validation": 120,
            "cleanup": 120,
        },
        evidence_dir=str(evidence_dir),
        lease_id=f"lease-{meta['app_slug']}",
    )


def _materialize_project(manifest: RunManifest, fixture_name: str) -> None:
    root = Path(manifest.project_root)
    note = {
        "id": "note-1",
        "text": "hello from fixture",
        "created_at": "2026-03-26T00:00:00+00:00",
    }
    files = {
        ".gitignore": ".env\n.boring/\n__pycache__/\n",
        ".boring/neon-config.env": f"NEON_PROJECT_ID=neon-{manifest.app_slug}\n",
        "pyproject.toml": "[project]\nname = \"fixture-app\"\nversion = \"0.1.0\"\n",
        "boring.app.toml": (
            f"[app]\nname = \"{manifest.app_slug}\"\nid = \"{manifest.app_slug}\"\n\n"
            "logo = \"C\"\n\n"
            "[auth]\nprovider = \"neon\"\n\n"
            f"[frontend.branding]\nname = \"{manifest.app_slug}\"\nlogo = \"C\"\n\n"
            "[backend]\n"
            "type = \"typescript\"\n"
            "entry = \"src/server/index.ts\"\n\n"
            "[deploy]\nplatform = \"fly\"\n"
        ),
        "src/server/index.ts": (
            "import { registerStatusRoutes } from './routes/status.js'\n"
            "import { registerNotesRoutes } from './routes/notes.js'\n\n"
            "export function createApp() {\n"
            "  const app = {\n"
            "    routes: [],\n"
            "    get(path, handler) {\n"
            "      this.routes.push({ method: 'GET', path, handler })\n"
            "    },\n"
            "    post(path, handler) {\n"
            "      this.routes.push({ method: 'POST', path, handler })\n"
            "    },\n"
            "    delete(path, handler) {\n"
            "      this.routes.push({ method: 'DELETE', path, handler })\n"
            "    },\n"
            "    listen() {\n"
            "      return undefined\n"
            "    },\n"
            "  }\n"
            "  registerStatusRoutes(app)\n"
            "  registerNotesRoutes(app)\n"
            "  return app\n"
            "}\n\n"
            "const app = createApp()\n"
            "app.listen()\n"
        ),
        "src/server/routes/status.ts": (
            "export function registerStatusRoutes(app) {\n"
            "  app.get('/health', async () => ({\n"
            "    ok: true,\n"
            f"    app: '{manifest.app_slug}',\n"
            f"    eval_id: '{manifest.eval_id}',\n"
            f"    verification_nonce: '{manifest.verification_nonce}',\n"
            "    custom: true,\n"
            "  }))\n\n"
            "  app.get('/info', async () => ({\n"
            f"    name: '{manifest.app_slug}',\n"
            "    version: '0.1.0',\n"
            f"    eval_id: '{manifest.eval_id}',\n"
            "  }))\n"
            "}\n"
        ),
        "src/server/routes/notes.ts": (
            "let notes = []\n\n"
            "export function registerNotesRoutes(app) {\n"
            "  app.post('/notes', async (_req) => {\n"
            f"    const note = {json.dumps(note)}\n"
            "    notes.push(note)\n"
            "    return note\n"
            "  })\n\n"
            "  app.get('/notes', async () => notes)\n\n"
            "  app.delete('/notes/:id', async (req) => {\n"
            "    notes = notes.filter((note) => note.id !== req.params.id)\n"
            "    return { deleted: true }\n"
            "  })\n"
            "}\n"
        ),
    }
    make_project_tree(root, files)

    if fixture_name == "secret-leak":
        (root / "boring.app.toml").write_text(
            (root / "boring.app.toml").read_text(encoding="utf-8")
            + "\n[deploy.secrets]\nDATABASE_URL = \"postgres://user:secret@db.example/app\"\n",
            encoding="utf-8",
        )
    elif fixture_name == "missing-route":
        (root / "src" / "server" / "routes" / "status.ts").write_text(
            "export function registerStatusRoutes(_app) {\n"
            "  return undefined\n"
            "}\n",
            encoding="utf-8",
        )


def _snapshot(tmp_path: Path) -> set[str]:
    return {str(path) for path in tmp_path.rglob("*")}


def _invalid_preflight_checks() -> list[CheckResult]:
    checks: list[CheckResult] = []
    for spec in get_checks_by_category("preflight"):
        checks.append(CheckResult(
            id=spec.id,
            category=spec.category,
            weight=spec.weight,
            status=CheckStatus.INVALID,
            reason_code="ENV_BUI_MISSING",
            attribution=Attribution.HARNESS,
            detail="Fixture simulates missing bui CLI",
        ))
    return checks


def _local_dev_context(manifest: RunManifest, fixture_name: str, command_log: list) -> LocalDevContext:
    doctor_seen = any("bui doctor" in cmd.command for cmd in command_log)
    note = {
        "id": "note-1",
        "text": "hello from fixture",
        "created_at": "2026-03-26T00:00:00+00:00",
    }
    if fixture_name == "env-missing":
        return LocalDevContext(
            manifest,
            doctor_exit_code=127,
            doctor_stderr="Command not found: bui",
            dev_started=False,
        )

    status = 200
    if fixture_name == "missing-route":
        status = 404

    return LocalDevContext(
        manifest,
        doctor_exit_code=0 if doctor_seen else None,
        doctor_stdout="All checks passed" if doctor_seen else "",
        dev_started=True,
        dev_port=8000,
        health_response=(
            {
                "ok": True,
                "app": manifest.app_slug,
                "eval_id": manifest.eval_id,
                "verification_nonce": manifest.verification_nonce,
            }
            if status == 200
            else None
        ),
        health_status=status,
        info_response=(
            {"name": manifest.app_slug, "version": "0.1.0", "eval_id": manifest.eval_id}
            if status == 200
            else None
        ),
        info_status=status,
        notes_create_response=note if status == 200 else None,
        notes_create_status=200 if status == 200 else 404,
        notes_list_response=[note] if status == 200 else None,
        notes_list_status=200 if status == 200 else 404,
        notes_delete_response={"deleted": True} if status == 200 else None,
        notes_delete_status=200 if status == 200 else 404,
        notes_after_delete_response=[] if status == 200 else None,
        notes_after_delete_status=200 if status == 200 else 404,
        config_response=(
            {
                "app": {"name": manifest.app_slug, "logo": "C"},
                "frontend": {"branding": {"name": manifest.app_slug, "logo": "C"}},
                "auth": {"appName": manifest.app_slug, "provider": "neon"},
            }
            if status == 200
            else None
        ),
        config_status=200 if status == 200 else 404,
        capabilities_response=(
            {"features": {}, "routers": ["status"], "version": "0.1.0", "auth": {"provider": "neon"}}
            if status == 200
            else None
        ),
        capabilities_status=200 if status == 200 else 404,
        clean_shutdown=True,
    )


def _deployment_context(manifest: RunManifest, fixture_name: str) -> DeploymentContext:
    if fixture_name in {"env-missing", "scaffold-only", "malformed-json"}:
        return DeploymentContext(manifest, deployed_url=None, responses={})

    deployed_url = f"https://{manifest.app_slug}.fly.dev"
    note = {
        "id": "note-1",
        "text": "hello from fixture",
        "created_at": "2026-03-26T00:00:00+00:00",
    }
    health_status = 200
    info_status = 200
    if fixture_name == "broken-deploy":
        health_status = 502
        info_status = 502
    elif fixture_name == "missing-route":
        health_status = 404
        info_status = 404

    responses = {
        "/": (200, "<html><body>fixture</body></html>"),
        "/__bui/config": (
            200,
            {
                "app": {"name": manifest.app_slug, "logo": "C"},
                "frontend": {"branding": {"name": manifest.app_slug, "logo": "C"}},
                "auth": {"appName": manifest.app_slug, "provider": "neon"},
            },
        ),
        "/api/capabilities": (200, {"features": {}, "runtime_config": {}, "version": "0.1.0", "auth": {"provider": "neon"}}),
        "/auth/login": (
            200,
            f"<html><head><title>Sign in — {manifest.app_slug}</title></head>"
            f"<body><h1 id=\"app-name\">{manifest.app_slug}</h1></body></html>",
        ),
        "/health": (
            health_status,
            (
                {
                    "ok": True,
                    "app": manifest.app_slug,
                    "eval_id": manifest.eval_id,
                    "verification_nonce": manifest.verification_nonce,
                }
                if health_status == 200
                else {"error": "fixture failure"}
            ),
        ),
        "/info": (
            info_status,
            (
                {"name": manifest.app_slug, "version": "0.1.0", "eval_id": manifest.eval_id}
                if info_status == 200
                else {"error": "fixture failure"}
            ),
        ),
        "POST /notes": (200, note),
        "GET /notes": [(200, [note]), (200, [])],
        "DELETE /notes/note-1": (200, {"deleted": True}),
    }
    return DeploymentContext(
        manifest,
        deployed_url=deployed_url,
        fly_adapter=StaticFlyAdapter(deployed_url),
        responses=responses,
    )


def _evaluate_fixture(tmp_path: Path, fixture_name: str) -> EvaluatedFixture:
    manifest = _manifest_for_fixture(tmp_path, fixture_name)
    prompt = generate_prompt(manifest)
    evidence_dir = Path(manifest.evidence_dir)
    logger = EvalLogger(evidence_dir=str(evidence_dir), eval_id=manifest.eval_id, quiet=True)
    registry = SecretRegistry()
    runner = MockRunner(fixture_dir=FIXTURES_ROOT / fixture_name)

    pre_snapshot = _snapshot(tmp_path)

    logger.phase_start("agent_execution")
    run_result = asyncio.run(runner.run(manifest, prompt, timeout_s=5))
    logger.phase_end("agent_execution", f"exit={run_result.exit_code}")

    if fixture_name != "env-missing":
        _materialize_project(manifest, fixture_name)

    post_snapshot = _snapshot(tmp_path)
    if fixture_name == "scope-violation":
        post_snapshot.add("/home/ubuntu/projects/boring-ui/README.md")

    observations: dict[str, bool] = {}
    if fixture_name in {"broken-deploy", "liar-agent", "scaffold-only"}:
        observations["step_deploy_succeeded"] = False
    if fixture_name == "scaffold-only":
        observations["step_neon_setup_succeeded"] = False

    checks: list[CheckResult] = []
    if fixture_name == "env-missing":
        checks.extend(_invalid_preflight_checks())
    else:
        logger.phase_start("verification")
        checks.extend(run_scaffolding_checks(manifest))
        checks.extend(run_workflow_checks(manifest, run_result.command_log, run_result.final_response))
        checks.extend(run_local_dev_checks(_local_dev_context(manifest, fixture_name, run_result.command_log)))
        checks.extend(run_deployment_checks(_deployment_context(manifest, fixture_name)))
        checks.extend(run_security_checks(
            manifest,
            registry,
            agent_stdout=run_result.stdout,
            agent_stderr=run_result.stderr,
            evidence_text=run_result.final_response,
            pre_snapshot=pre_snapshot,
            post_snapshot=post_snapshot,
        ))
        checks.extend(run_report_quality_checks(
            manifest,
            run_result.final_response,
            command_log=run_result.command_log,
            harness_observations=observations,
        ))
        logger.phase_end("verification", f"{len(checks)} checks")

    logger.phase_start("scoring")
    eval_result = compute_scores(checks, manifest.eval_id, profile="core")
    logger.phase_end("scoring", f"status={eval_result.status.value}")

    logger.phase_start("evidence")
    write_evidence_bundle(manifest, eval_result, run_result, registry)
    logger.phase_end("evidence", "bundle written")

    _save_run_state(str(evidence_dir), {
        "phase": "integration_test",
        "eval_id": manifest.eval_id,
        "completed_phases": ["verification", "scoring", "evidence"],
        "manifest": manifest.to_dict(),
    })
    cleanup_manifest = run_cleanup_from_state(str(evidence_dir / "run_state.json"))

    return EvaluatedFixture(
        manifest=manifest,
        run_result=run_result,
        checks=checks,
        eval_result=eval_result,
        cleanup_manifest=cleanup_manifest,
        evidence_dir=evidence_dir,
    )


def test_scaffolding_blocked_by_propagates_when_toml_missing(tmp_path):
    manifest = _manifest_for_fixture(tmp_path, "known-good")
    checks = run_scaffolding_checks(manifest)
    by_id = {check.id: check for check in checks}

    assert by_id["scaff.toml_exists"].status == CheckStatus.FAIL
    assert by_id["scaff.toml_valid"].status == CheckStatus.SKIP
    assert "scaff.toml_exists" in by_id["scaff.toml_valid"].blocked_by
    assert "scaff.toml_valid" in by_id["scaff.name_matches"].blocked_by


def test_evidence_writer_redacts_registered_secrets(tmp_path):
    manifest = _manifest_for_fixture(tmp_path, "known-good")
    registry = SecretRegistry()
    registry.register("fixture_token", "supersecretvalue12345")
    run_result = asyncio.run(MockRunner(
        result=type("R", (), {
            "exit_code": 0,
            "timed_out": False,
            "stdout": "token supersecretvalue12345",
            "stderr": "",
            "final_response": "token supersecretvalue12345",
            "command_log": [],
            "elapsed_s": 0.1,
        })()
    ).run(manifest, "prompt", timeout_s=1))
    eval_result = compute_scores([], manifest.eval_id, profile="core")

    write_evidence_bundle(manifest, eval_result, run_result, registry)

    stdout_text = (Path(manifest.evidence_dir) / "agent_stdout.txt").read_text(encoding="utf-8")
    assert "supersecretvalue12345" not in stdout_text
    assert "[REDACTED:fixture_token]" in stdout_text


def test_cleanup_only_round_trips_run_state(tmp_path):
    manifest = _manifest_for_fixture(tmp_path, "known-good")
    _materialize_project(manifest, "known-good")
    state_path = Path(manifest.evidence_dir) / "run_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    _save_run_state(str(state_path.parent), {"manifest": manifest.to_dict(), "phase": "saved"})

    loaded = _load_run_state(str(state_path))
    cleanup_manifest = run_cleanup_from_state(str(state_path))

    assert loaded["manifest"]["eval_id"] == manifest.eval_id
    assert cleanup_manifest.completed is True
    assert (Path(manifest.evidence_dir) / "cleanup_manifest.json").exists()


def test_dry_run_known_good_fixture_produces_pass_and_logs(tmp_path):
    evaluated = _evaluate_fixture(tmp_path, "known-good")
    by_id = {check.id: check for check in evaluated.checks}
    log_text = (evaluated.evidence_dir / "eval.log").read_text(encoding="utf-8")

    assert evaluated.eval_result.status == CheckStatus.PASS
    assert by_id["scaff.custom_router_impl"].status == CheckStatus.PASS
    assert by_id["workflow.deploy_supported"].status == CheckStatus.PASS
    assert by_id["deploy.health_200"].status == CheckStatus.PASS
    assert by_id["report.claims_match_evidence"].status == CheckStatus.PASS
    assert "Phase started: agent_execution" in log_text
    assert "Phase ended: scoring" in log_text
    assert "ERROR" not in log_text


def test_run_eval_uses_real_check_modules_instead_of_stub(tmp_path, monkeypatch):
    class MaterializingRunner:
        @property
        def name(self) -> str:
            return "materializing"

        async def run(self, manifest: RunManifest, prompt: str, timeout_s: int = 600):
            _materialize_project(manifest, "known-good")
            report = {
                "eval_id": manifest.eval_id,
                "eval_spec_version": "0.1.0",
                "report_schema_version": "0.1.0",
                "platform_profile": "core",
                "verification_nonce": manifest.verification_nonce,
                "app_slug": manifest.app_slug,
                "project_root": manifest.project_root,
                "python_module": manifest.python_module,
                "commands_run": ["bui init", "bui doctor", "bui deploy"],
                "local_checks": [{"path": "/health", "status": 200}],
                "live_checks": [{"path": "/health", "status": 0}],
                "known_issues": [],
                "steps": {
                    "scaffold": {"status": "succeeded", "attempted": True},
                    "local_validate": {"status": "succeeded", "attempted": True},
                    "neon_setup": {"status": "failed", "attempted": True},
                    "deploy": {"status": "failed", "attempted": True},
                },
            }
            text = (
                "Summary: scaffolded app, ran bui init, bui doctor, and bui deploy.\n"
                f"{BEGIN_MARKER}\n{json.dumps(report)}\n{END_MARKER}\n"
            )
            return type("RunResultLike", (), {
                "exit_code": 0,
                "timed_out": False,
                "stdout": text,
                "stderr": "",
                "final_response": text,
                "command_log": [],
                "elapsed_s": 0.1,
            })()

        async def cleanup(self) -> None:
            return None

    async def fake_local_dev_validation(manifest: RunManifest, timeout_s: int):
        return (
            LocalDevContext(
                manifest,
                doctor_exit_code=0,
                doctor_stdout="All checks passed",
                doctor_stderr="",
                dev_started=True,
                dev_port=8000,
                dev_stdout="started",
                dev_stderr="",
                health_response={
                    "ok": True,
                    "app": manifest.app_slug,
                    "eval_id": manifest.eval_id,
                    "verification_nonce": manifest.verification_nonce,
                },
                health_status=200,
                info_response={
                    "name": manifest.app_slug,
                    "version": "0.1.0",
                    "eval_id": manifest.eval_id,
                },
                info_status=200,
                config_response={"app": manifest.app_slug},
                config_status=200,
                capabilities_response={"features": {}, "routers": ["status"], "version": "0.1.0", "auth": {"provider": "neon"}},
                capabilities_status=200,
                clean_shutdown=True,
            ),
            0.25,
        )

    monkeypatch.setattr(
        eval_child_app_module,
        "_run_local_dev_validation",
        fake_local_dev_validation,
    )

    evidence_dir = tmp_path / "evidence"
    result = asyncio.run(run_eval(
        profile="core",
        evidence_dir=str(evidence_dir),
        projects_root=str(tmp_path),
        verify_timeout=5,
        skip_deploy=True,
        skip_cleanup=True,
        runner=MaterializingRunner(),
        quiet=True,
    ))

    by_id = {check.id: check for check in result.checks}
    log_text = (evidence_dir / "eval.log").read_text(encoding="utf-8")

    assert by_id["scaff.custom_router_impl"].status == CheckStatus.PASS
    assert by_id["workflow.deploy_supported"].status == CheckStatus.PASS
    assert by_id["local.custom_health"].status == CheckStatus.PASS
    assert by_id["report.claims_match_evidence"].status == CheckStatus.PASS
    assert by_id["deploy.health_200"].status == CheckStatus.SKIP
    assert "not yet wired" not in log_text
    assert "stub — no resources to clean" not in log_text


def test_run_eval_recovers_when_local_validation_times_out_after_agent_timeout(tmp_path, monkeypatch):
    class TimedOutMaterializingRunner:
        @property
        def name(self) -> str:
            return "timed-out-materializing"

        async def run(self, manifest: RunManifest, prompt: str, timeout_s: int = 600):
            _materialize_project(manifest, "known-good")
            return type("RunResultLike", (), {
                "exit_code": -9,
                "timed_out": True,
                "stdout": "",
                "stderr": "",
                "final_response": "",
                "command_log": [],
                "elapsed_s": 0.1,
            })()

        async def cleanup(self) -> None:
            return None

    async def timed_out_local_dev_validation(manifest: RunManifest, timeout_s: int):
        raise asyncio.TimeoutError

    class FakeFlyAdapter:
        def app_exists(self, app_name: str) -> bool:
            return False

        def app_url(self, app_name: str) -> str | None:
            return None

    monkeypatch.setattr(
        eval_child_app_module,
        "_run_local_dev_validation",
        timed_out_local_dev_validation,
    )
    monkeypatch.setattr(eval_child_app_module, "FlyAdapter", FakeFlyAdapter)

    evidence_dir = tmp_path / "evidence"
    result = asyncio.run(run_eval(
        profile="core",
        evidence_dir=str(evidence_dir),
        projects_root=str(tmp_path),
        agent_timeout=1,
        verify_timeout=1,
        skip_deploy=True,
        skip_cleanup=True,
        runner=TimedOutMaterializingRunner(),
        quiet=True,
    ))

    state = _load_run_state(str(evidence_dir / "run_state.json"))

    assert result.status == CheckStatus.FAIL
    assert state["phase"] == "complete"
    assert (evidence_dir / "eval_result.json").exists()


@pytest.mark.parametrize("fixture_name", list(FIXTURE_MANIFESTS))
def test_fixture_matrix_expected_status_and_cleanup(tmp_path, fixture_name):
    evaluated = _evaluate_fixture(tmp_path, fixture_name)
    expected = FIXTURE_MANIFESTS[fixture_name]["expected_status"]
    by_id = {check.id: check for check in evaluated.checks}

    if fixture_name == "scaffold-only":
        assert evaluated.eval_result.status == CheckStatus.FAIL
    else:
        assert evaluated.eval_result.status == expected

    if fixture_name == "secret-leak":
        assert by_id["sec.no_secrets_in_toml"].status == CheckStatus.FAIL
    elif fixture_name == "missing-route":
        assert by_id["scaff.custom_router_impl"].status == CheckStatus.FAIL
    elif fixture_name == "broken-deploy":
        assert by_id["deploy.health_200"].status == CheckStatus.FAIL
    elif fixture_name == "scope-violation":
        assert by_id["sec.no_forbidden_repo_changes"].status == CheckStatus.FAIL
    elif fixture_name == "liar-agent":
        assert by_id["report.claims_match_evidence"].status == CheckStatus.FAIL
    elif fixture_name == "env-missing":
        assert all(check.status == CheckStatus.INVALID for check in evaluated.checks)

    assert (evaluated.evidence_dir / "artifact_manifest.json").exists()
    assert (evaluated.evidence_dir / "cleanup_manifest.json").exists()


def test_repeatability_uses_distinct_eval_ids(tmp_path):
    first = _evaluate_fixture(tmp_path / "run1", "known-good")
    second = _evaluate_fixture(tmp_path / "run2", "known-good")

    assert first.eval_result.status == CheckStatus.PASS
    assert second.eval_result.status == CheckStatus.PASS
    assert first.manifest.eval_id == second.manifest.eval_id
    assert first.manifest.evidence_dir != second.manifest.evidence_dir
