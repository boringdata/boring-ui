"""Guards for bd-3g1g.6.1 PTY session_id validation and canonicalization."""

from __future__ import annotations

import uuid

import pytest

from boring_ui.api.modules.pty.service import PTYService


@pytest.mark.asyncio
async def test_get_or_create_session_validates_and_canonicalizes_session_id(tmp_path) -> None:
    service = PTYService()
    command = ["bash"]

    canonical = str(uuid.uuid4())
    non_canonical = f"{{{canonical.upper()}}}"

    sess1, is_new1 = await service.get_or_create_session(
        session_id=non_canonical,
        command=command,
        cwd=tmp_path,
    )
    assert is_new1 is True
    assert sess1.session_id == canonical

    sess2, is_new2 = await service.get_or_create_session(
        session_id=canonical,
        command=command,
        cwd=tmp_path,
    )
    assert is_new2 is False
    assert sess2 is sess1

    with pytest.raises(ValueError):
        await service.get_or_create_session(
            session_id="not-a-uuid",
            command=command,
            cwd=tmp_path,
        )

