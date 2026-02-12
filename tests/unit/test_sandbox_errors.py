"""Tests for sandbox error hierarchy."""
import pytest

from boring_ui.api.modules.sandbox.errors import (
    CheckpointError,
    CheckpointNotSupportedError,
    SandboxAuthError,
    SandboxError,
    SandboxExistsError,
    SandboxNotFoundError,
    SandboxProvisionError,
    SandboxTimeoutError,
)


class TestSandboxErrorBase:
    def test_basic_message(self):
        err = SandboxError("something broke")
        assert str(err) == "something broke"

    def test_structured_context(self):
        err = SandboxError(
            "failed",
            sandbox_id="sb-123",
            provider="sprites",
            operation="create",
        )
        assert err.sandbox_id == "sb-123"
        assert err.provider == "sprites"
        assert err.operation == "create"

    def test_defaults_are_none(self):
        err = SandboxError("x")
        assert err.sandbox_id is None
        assert err.provider is None
        assert err.operation is None

    def test_repr_minimal(self):
        err = SandboxError("oops")
        assert repr(err) == "SandboxError('oops')"

    def test_repr_full(self):
        err = SandboxError(
            "fail",
            sandbox_id="sb-1",
            provider="local",
            operation="destroy",
        )
        r = repr(err)
        assert "SandboxError('fail'" in r
        assert "sandbox_id='sb-1'" in r
        assert "provider='local'" in r
        assert "operation='destroy'" in r

    def test_is_exception(self):
        assert issubclass(SandboxError, Exception)


class TestSubclasses:
    """Each subclass inherits context fields and is catchable via SandboxError."""

    @pytest.mark.parametrize(
        "cls",
        [
            SandboxNotFoundError,
            SandboxExistsError,
            SandboxProvisionError,
            SandboxTimeoutError,
            SandboxAuthError,
            CheckpointError,
            CheckpointNotSupportedError,
        ],
    )
    def test_inherits_sandbox_error(self, cls):
        assert issubclass(cls, SandboxError)

    @pytest.mark.parametrize(
        "cls",
        [
            SandboxNotFoundError,
            SandboxExistsError,
            SandboxProvisionError,
            SandboxTimeoutError,
            SandboxAuthError,
            CheckpointError,
            CheckpointNotSupportedError,
        ],
    )
    def test_carries_context(self, cls):
        err = cls("msg", sandbox_id="sb-x", provider="sprites", operation="op")
        assert err.sandbox_id == "sb-x"
        assert err.provider == "sprites"
        assert err.operation == "op"

    @pytest.mark.parametrize(
        "cls",
        [
            SandboxNotFoundError,
            SandboxExistsError,
            SandboxProvisionError,
            SandboxTimeoutError,
            SandboxAuthError,
            CheckpointError,
            CheckpointNotSupportedError,
        ],
    )
    def test_catchable_via_base(self, cls):
        with pytest.raises(SandboxError):
            raise cls("test")

    def test_checkpoint_not_supported_is_checkpoint_error(self):
        assert issubclass(CheckpointNotSupportedError, CheckpointError)

    @pytest.mark.parametrize(
        "cls",
        [
            SandboxNotFoundError,
            SandboxExistsError,
            SandboxProvisionError,
            SandboxTimeoutError,
            SandboxAuthError,
            CheckpointError,
            CheckpointNotSupportedError,
        ],
    )
    def test_repr_uses_subclass_name(self, cls):
        err = cls("msg")
        assert repr(err).startswith(f"{cls.__name__}(")


class TestSafeMessages:
    """Error messages must not leak secrets or internal paths."""

    def test_message_does_not_include_token(self):
        err = SandboxError("auth failed for sandbox sb-1")
        assert "token" not in str(err).lower()

    def test_repr_does_not_include_secrets(self):
        err = SandboxAuthError(
            "unauthorized",
            sandbox_id="sb-1",
            provider="sprites",
            operation="health_check",
        )
        r = repr(err)
        assert "secret" not in r.lower()
        assert "password" not in r.lower()
