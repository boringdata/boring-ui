"""Unit tests for git branch operations (service + router)."""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from boring_ui.api.modules.git.service import GitService


# ── Service-level tests ──────────────────────────────────────────────


class TestGitServiceBranches:
    """Test GitService branch operations against a real temporary git repo."""

    @pytest.fixture(autouse=True)
    def setup_repo(self, tmp_path):
        """Create a temporary git repo with an initial commit."""
        self.repo_dir = tmp_path / "repo"
        self.repo_dir.mkdir()
        subprocess.run(["git", "init"], cwd=self.repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=self.repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo_dir, check=True, capture_output=True)
        # Initial commit
        (self.repo_dir / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "."], cwd=self.repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.repo_dir, check=True, capture_output=True)

        class FakeConfig:
            workspace_root = self.repo_dir
            def validate_path(self, p):
                resolved = (self.workspace_root / p).resolve()
                if not str(resolved).startswith(str(self.workspace_root)):
                    raise ValueError("path escape")
                return resolved

        self.service = GitService(FakeConfig())

    def test_current_branch(self):
        result = self.service.current_branch()
        assert result['branch'] in ('main', 'master')

    def test_list_branches_single(self):
        result = self.service.list_branches()
        assert len(result['branches']) == 1
        assert result['current'] in ('main', 'master')

    def test_create_branch_and_checkout(self):
        result = self.service.create_branch('feature-x', checkout=True)
        assert result['created'] is True
        assert result['branch'] == 'feature-x'
        assert result['checked_out'] is True
        assert self.service.current_branch()['branch'] == 'feature-x'

    def test_create_branch_without_checkout(self):
        default_branch = self.service.current_branch()['branch']
        result = self.service.create_branch('feature-y', checkout=False)
        assert result['created'] is True
        assert result['checked_out'] is False
        assert self.service.current_branch()['branch'] == default_branch

    def test_checkout_branch(self):
        self.service.create_branch('dev', checkout=False)
        assert self.service.current_branch()['branch'] != 'dev'
        result = self.service.checkout_branch('dev')
        assert result['checked_out'] is True
        assert self.service.current_branch()['branch'] == 'dev'

    def test_list_branches_multiple(self):
        self.service.create_branch('alpha', checkout=False)
        self.service.create_branch('beta', checkout=False)
        result = self.service.list_branches()
        assert 'alpha' in result['branches']
        assert 'beta' in result['branches']
        assert len(result['branches']) >= 3  # main/master + alpha + beta

    def test_merge_branch(self):
        # Create a branch, add a file, go back to default, merge
        default_branch = self.service.current_branch()['branch']
        self.service.create_branch('feature-merge', checkout=True)
        (self.repo_dir / "new_file.txt").write_text("hello\n")
        self.service.add_files(["new_file.txt"])
        self.service.commit("add new file")
        self.service.checkout_branch(default_branch)
        assert not (self.repo_dir / "new_file.txt").exists()
        result = self.service.merge_branch('feature-merge')
        assert result['merged'] is True
        assert (self.repo_dir / "new_file.txt").exists()

    def test_create_branch_invalid_name(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            self.service.create_branch('--bad-name')
        assert exc_info.value.status_code == 400

    def test_checkout_nonexistent_branch(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            self.service.checkout_branch('no-such-branch')
        assert exc_info.value.status_code == 500


# ── Router-level tests ───────────────────────────────────────────────


class TestGitBranchRouter:
    """Test git branch router endpoints via TestClient."""

    @pytest.fixture(autouse=True)
    def setup_app(self, tmp_path):
        """Create a FastAPI app with git router and a real temp repo."""
        from fastapi import FastAPI
        from boring_ui.api.config import APIConfig
        from boring_ui.api.modules.git.router import create_git_router

        self.repo_dir = tmp_path / "repo"
        self.repo_dir.mkdir()
        subprocess.run(["git", "init"], cwd=self.repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=self.repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo_dir, check=True, capture_output=True)
        (self.repo_dir / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "."], cwd=self.repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.repo_dir, check=True, capture_output=True)

        config = APIConfig(workspace_root=self.repo_dir)
        app = FastAPI()
        app.include_router(create_git_router(config), prefix="/git")
        self.client = TestClient(app)

    def test_get_branches(self):
        r = self.client.get("/git/branches")
        assert r.status_code == 200
        data = r.json()
        assert 'branches' in data
        assert 'current' in data
        assert len(data['branches']) >= 1

    def test_get_current_branch(self):
        r = self.client.get("/git/branch")
        assert r.status_code == 200
        data = r.json()
        assert data['branch'] in ('main', 'master')

    def test_create_branch(self):
        r = self.client.post("/git/branch", json={"name": "new-feature"})
        assert r.status_code == 200
        data = r.json()
        assert data['created'] is True
        assert data['branch'] == 'new-feature'

    def test_create_branch_requires_name(self):
        r = self.client.post("/git/branch", json={})
        assert r.status_code == 400

    def test_checkout(self):
        self.client.post("/git/branch", json={"name": "test-checkout", "checkout": False})
        r = self.client.post("/git/checkout", json={"name": "test-checkout"})
        assert r.status_code == 200
        data = r.json()
        assert data['checked_out'] is True

    def test_checkout_requires_name(self):
        r = self.client.post("/git/checkout", json={})
        assert r.status_code == 400

    def test_merge(self):
        default_branch = self.client.get("/git/branch").json()['branch']
        # Create and switch to feature branch
        self.client.post("/git/branch", json={"name": "merge-test"})
        # Go back to default
        self.client.post("/git/checkout", json={"name": default_branch})
        r = self.client.post("/git/merge", json={"source": "merge-test"})
        assert r.status_code == 200
        data = r.json()
        assert data['merged'] is True

    def test_merge_requires_source(self):
        r = self.client.post("/git/merge", json={})
        assert r.status_code == 400

    def test_full_branch_workflow(self):
        """Create branch → checkout → list → merge → verify."""
        default_branch = self.client.get("/git/branch").json()['branch']

        # Create without checkout
        r = self.client.post("/git/branch", json={"name": "workflow-test", "checkout": False})
        assert r.status_code == 200
        assert self.client.get("/git/branch").json()['branch'] == default_branch

        # List should include new branch
        branches = self.client.get("/git/branches").json()
        assert 'workflow-test' in branches['branches']

        # Checkout
        self.client.post("/git/checkout", json={"name": "workflow-test"})
        assert self.client.get("/git/branch").json()['branch'] == 'workflow-test'

        # Go back and merge
        self.client.post("/git/checkout", json={"name": default_branch})
        r = self.client.post("/git/merge", json={"source": "workflow-test"})
        assert r.status_code == 200
