"""Guards for bd-3g1g.6.1 PTY session_id validation and canonicalization."""

from __future__ import annotations

import uuid

import pytest

from boring_ui.api.modules.pty.service import PTYService


@pytest.mark.asyncio
async def test_get_or_create_session_validates_and_canonicalizes_session_id(tmp_path) -> None:
    service = PTYService()
    # This is not executed by get_or_create_session(); the PTY subprocess is only
    # spawned when a websocket client starts the session.
    command = ["__test_noop__"]

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

    sess3, is_new3 = await service.get_or_create_session(
        session_id=None,
        command=command,
        cwd=tmp_path,
    )
    assert is_new3 is True
    uuid.UUID(sess3.session_id)

    sess4, is_new4 = await service.get_or_create_session(
        # Blank/whitespace IDs are treated as "unset" (equivalent to None).
        session_id="   ",
        command=command,
        cwd=tmp_path,
    )
    assert is_new4 is True
    uuid.UUID(sess4.session_id)

    sess5, is_new5 = await service.get_or_create_session(
        session_id="",
        command=command,
        cwd=tmp_path,
    )
    assert is_new5 is True
    uuid.UUID(sess5.session_id)

    with pytest.raises(ValueError):
        await service.get_or_create_session(
            session_id=123,  # type: ignore[arg-type]
            command=command,
            cwd=tmp_path,
        )
