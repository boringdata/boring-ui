"""Unit tests for server-owned exec command template allowlist."""
import pytest

from boring_ui.api.exec_policy import (
    ExecPolicyError,
    ExecTemplate,
    ExecTemplateRegistry,
    MAX_OUTPUT_BYTES,
    MAX_TIMEOUT_SECONDS,
    TEMPLATE_ID_PATTERN,
    create_default_registry,
    validate_template,
    validate_template_id,
)


class TestValidateTemplateId:

    def test_valid_ids(self):
        for tid in ('shell', 'claude', 'my-template', 'pty_v2', 'a'):
            validate_template_id(tid)

    def test_empty(self):
        with pytest.raises(ExecPolicyError) as exc:
            validate_template_id('')
        assert 'required' in str(exc.value)

    def test_uppercase_rejected(self):
        with pytest.raises(ExecPolicyError):
            validate_template_id('Shell')

    def test_starts_with_number(self):
        with pytest.raises(ExecPolicyError):
            validate_template_id('1shell')

    def test_special_chars(self):
        with pytest.raises(ExecPolicyError):
            validate_template_id('shell;rm')

    def test_too_long(self):
        with pytest.raises(ExecPolicyError):
            validate_template_id('a' * 65)

    def test_max_length(self):
        validate_template_id('a' * 64)


class TestValidateTemplate:

    def test_valid_template(self):
        t = ExecTemplate(
            id='shell', description='test',
            command=('/bin/bash',),
        )
        assert validate_template(t) == []

    def test_empty_command(self):
        t = ExecTemplate(
            id='shell', description='test',
            command=(),
        )
        issues = validate_template(t)
        assert any('empty command' in i for i in issues)

    def test_negative_timeout(self):
        t = ExecTemplate(
            id='shell', description='test',
            command=('/bin/bash',), timeout_seconds=-1,
        )
        issues = validate_template(t)
        assert any('positive' in i for i in issues)

    def test_excessive_timeout(self):
        t = ExecTemplate(
            id='shell', description='test',
            command=('/bin/bash',),
            timeout_seconds=MAX_TIMEOUT_SECONDS + 1,
        )
        issues = validate_template(t)
        assert any('exceeds' in i for i in issues)

    def test_max_timeout_ok(self):
        t = ExecTemplate(
            id='shell', description='test',
            command=('/bin/bash',),
            timeout_seconds=MAX_TIMEOUT_SECONDS,
        )
        assert validate_template(t) == []

    def test_negative_output_bytes(self):
        t = ExecTemplate(
            id='shell', description='test',
            command=('/bin/bash',), max_output_bytes=-1,
        )
        issues = validate_template(t)
        assert any('positive' in i for i in issues)

    def test_excessive_output_bytes(self):
        t = ExecTemplate(
            id='shell', description='test',
            command=('/bin/bash',),
            max_output_bytes=MAX_OUTPUT_BYTES + 1,
        )
        issues = validate_template(t)
        assert any('exceeds' in i for i in issues)

    def test_shell_metachar_in_command(self):
        t = ExecTemplate(
            id='shell', description='test',
            command=('/bin/bash', '-c', 'echo; rm -rf /'),
        )
        issues = validate_template(t)
        assert any('metacharacter' in i for i in issues)

    def test_backtick_in_command(self):
        t = ExecTemplate(
            id='shell', description='test',
            command=('echo', '`whoami`'),
        )
        issues = validate_template(t)
        assert any('metacharacter' in i for i in issues)

    def test_dollar_in_command(self):
        t = ExecTemplate(
            id='shell', description='test',
            command=('echo', '$HOME'),
        )
        issues = validate_template(t)
        assert any('metacharacter' in i for i in issues)

    def test_pipe_in_command(self):
        t = ExecTemplate(
            id='shell', description='test',
            command=('ls', '|', 'grep', 'x'),
        )
        issues = validate_template(t)
        assert any('metacharacter' in i for i in issues)

    def test_invalid_id(self):
        t = ExecTemplate(
            id='BAD ID', description='test',
            command=('/bin/bash',),
        )
        issues = validate_template(t)
        assert any('does not match' in i for i in issues)


class TestExecTemplateRegistry:

    def test_register_and_get(self):
        reg = ExecTemplateRegistry()
        t = ExecTemplate(id='shell', description='shell', command=('/bin/bash',))
        reg.register(t)
        assert reg.get('shell') is t

    def test_get_unknown(self):
        reg = ExecTemplateRegistry()
        with pytest.raises(ExecPolicyError) as exc:
            reg.get('unknown')
        assert 'Unknown template' in str(exc.value)

    def test_get_invalid_id(self):
        reg = ExecTemplateRegistry()
        with pytest.raises(ExecPolicyError):
            reg.get('BAD;ID')

    def test_duplicate_registration(self):
        reg = ExecTemplateRegistry()
        t = ExecTemplate(id='shell', description='shell', command=('/bin/bash',))
        reg.register(t)
        with pytest.raises(ExecPolicyError) as exc:
            reg.register(t)
        assert 'already registered' in str(exc.value)

    def test_register_invalid_template(self):
        reg = ExecTemplateRegistry()
        t = ExecTemplate(id='shell', description='bad', command=())
        with pytest.raises(ExecPolicyError) as exc:
            reg.register(t)
        assert 'Invalid template' in str(exc.value)

    def test_freeze(self):
        reg = ExecTemplateRegistry()
        t = ExecTemplate(id='shell', description='shell', command=('/bin/bash',))
        reg.register(t)
        reg.freeze()
        assert reg.is_frozen is True

    def test_register_after_freeze(self):
        reg = ExecTemplateRegistry()
        reg.freeze()
        t = ExecTemplate(id='shell', description='shell', command=('/bin/bash',))
        with pytest.raises(ExecPolicyError) as exc:
            reg.register(t)
        assert 'frozen' in str(exc.value)

    def test_list_ids(self):
        reg = ExecTemplateRegistry()
        reg.register(ExecTemplate(id='b-templ', description='b', command=('/bin/b',)))
        reg.register(ExecTemplate(id='a-templ', description='a', command=('/bin/a',)))
        assert reg.list_ids() == ['a-templ', 'b-templ']

    def test_len(self):
        reg = ExecTemplateRegistry()
        assert len(reg) == 0
        reg.register(ExecTemplate(id='shell', description='s', command=('/bin/bash',)))
        assert len(reg) == 1


class TestCreateDefaultRegistry:

    def test_has_shell(self):
        reg = create_default_registry()
        t = reg.get('shell')
        assert t.command == ('/bin/bash',)

    def test_has_claude(self):
        reg = create_default_registry()
        t = reg.get('claude')
        assert 'claude' in t.command[0]

    def test_is_frozen(self):
        reg = create_default_registry()
        assert reg.is_frozen is True

    def test_two_templates(self):
        reg = create_default_registry()
        assert len(reg) == 2

    def test_cannot_add_after_default(self):
        reg = create_default_registry()
        with pytest.raises(ExecPolicyError):
            reg.register(ExecTemplate(
                id='evil', description='evil', command=('/bin/evil',),
            ))


class TestExecTemplate:

    def test_defaults(self):
        t = ExecTemplate(
            id='test', description='test', command=('/bin/test',),
        )
        assert t.working_directory == '/home/sprite/workspace'
        assert t.timeout_seconds == 3600
        assert t.max_output_bytes == 204800
        assert 'TERM' in t.env

    def test_frozen(self):
        t = ExecTemplate(
            id='test', description='test', command=('/bin/test',),
        )
        with pytest.raises(AttributeError):
            t.id = 'changed'
