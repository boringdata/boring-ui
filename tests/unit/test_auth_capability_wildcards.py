"""Auth/capability wildcard regression gates for clean-state architecture."""

from boring_ui.api.auth_middleware import AuthContext
from boring_ui.api.sandbox_auth import CapabilityAuthContext
from boring_ui.api.capability_tokens import CapabilityTokenValidator


def _capability_context(operations: set[str]) -> CapabilityAuthContext:
    return CapabilityAuthContext(
        workspace_id="ws",
        operations=operations,
        jti="jti-1",
        issued_at=1,
        expires_at=2,
    )


class TestAuthContextWildcardSemantics:
    def test_exact(self):
        ctx = AuthContext(user_id="u", permissions={"files:read"})
        assert ctx.has_permission("files:read") is True
        assert ctx.has_permission("files:write") is False

    def test_namespace_wildcard(self):
        ctx = AuthContext(user_id="u", permissions={"git:*"})
        assert ctx.has_permission("git:status") is True
        assert ctx.has_permission("files:read") is False

    def test_global_wildcard(self):
        ctx = AuthContext(user_id="u", permissions={"*"})
        assert ctx.has_permission("anything:at_all") is True


class TestCapabilityContextWildcardSemantics:
    def test_exact(self):
        ctx = _capability_context({"exec:run"})
        assert ctx.has_operation("exec:run") is True
        assert ctx.has_operation("exec:stop") is False

    def test_namespace_wildcard(self):
        ctx = _capability_context({"files:*"})
        assert ctx.has_operation("files:read") is True
        assert ctx.has_operation("git:status") is False

    def test_global_wildcard(self):
        ctx = _capability_context({"*"})
        assert ctx.has_operation("sandbox:anything") is True


class TestCapabilityTokenValidatorWildcardSemantics:
    def test_exact_namespace_global_matrix(self):
        validator = CapabilityTokenValidator.__new__(CapabilityTokenValidator)

        assert validator.validate_operation({"ops": ["files:read"]}, "files:read") is True
        assert validator.validate_operation({"ops": ["files:*"]}, "files:write") is True
        assert validator.validate_operation({"ops": ["*"]}, "exec:run") is True
        assert validator.validate_operation({"ops": ["git:*"]}, "files:read") is False

