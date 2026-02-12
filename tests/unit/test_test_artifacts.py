"""Unit tests for test logging and artifact contract."""
import json
import time
import pytest
from pathlib import Path

from boring_ui.api.test_artifacts import (
    ARTIFACT_PREFIX,
    EventTimeline,
    StructuredLogEntry,
    StructuredTestLogger,
    TestArtifactManifest,
    TimelineEvent,
    artifact_path,
)


NOW = 1700000000.0


class TestStructuredLogEntry:

    def test_to_json(self):
        e = StructuredLogEntry(
            timestamp=NOW, level='INFO', message='test',
            request_id='req-1', test_name='my_test',
        )
        data = json.loads(e.to_json())
        assert data['level'] == 'INFO'
        assert data['request_id'] == 'req-1'

    def test_from_json(self):
        line = json.dumps({
            'timestamp': NOW, 'level': 'ERROR',
            'message': 'fail', 'request_id': '',
            'test_name': '', 'extra': {},
        })
        e = StructuredLogEntry.from_json(line)
        assert e.level == 'ERROR'
        assert e.message == 'fail'

    def test_roundtrip(self):
        e = StructuredLogEntry(
            timestamp=NOW, level='INFO', message='hello',
            extra={'key': 'value'},
        )
        e2 = StructuredLogEntry.from_json(e.to_json())
        assert e2.message == 'hello'
        assert e2.extra == {'key': 'value'}


class TestStructuredTestLogger:

    def test_log_and_count(self):
        logger = StructuredTestLogger()
        logger.info('test message')
        assert logger.count == 1

    def test_levels(self):
        logger = StructuredTestLogger()
        logger.info('info')
        logger.error('error')
        logger.warning('warn')
        assert logger.count == 3
        assert logger.entries[0].level == 'INFO'
        assert logger.entries[1].level == 'ERROR'
        assert logger.entries[2].level == 'WARNING'

    def test_request_id(self):
        logger = StructuredTestLogger()
        logger.info('test', request_id='req-1')
        assert logger.entries[0].request_id == 'req-1'

    def test_extra_fields(self):
        logger = StructuredTestLogger()
        logger.info('test', status_code=200, latency=0.05)
        assert logger.entries[0].extra == {'status_code': 200, 'latency': 0.05}

    def test_save(self, tmp_path):
        logger = StructuredTestLogger()
        logger.info('line1')
        logger.error('line2')
        path = tmp_path / 'test.jsonl'
        logger.save(path)
        lines = path.read_text().strip().split('\n')
        assert len(lines) == 2

    def test_save_creates_parents(self, tmp_path):
        logger = StructuredTestLogger()
        logger.info('test')
        path = tmp_path / 'deep' / 'nested' / 'test.jsonl'
        logger.save(path)
        assert path.exists()

    def test_save_no_path_raises(self):
        logger = StructuredTestLogger()
        with pytest.raises(ValueError):
            logger.save()

    def test_clear(self):
        logger = StructuredTestLogger()
        logger.info('test')
        logger.clear()
        assert logger.count == 0


class TestEventTimeline:

    def test_record_and_count(self):
        tl = EventTimeline()
        tl.record('ws_connect', 'inbound', request_id='r1')
        assert tl.count == 1

    def test_filter_by_request_id(self):
        tl = EventTimeline()
        tl.record('ws_connect', 'inbound', request_id='r1')
        tl.record('ws_message', 'outbound', request_id='r2')
        tl.record('ws_close', 'inbound', request_id='r1')
        filtered = tl.filter_by_request_id('r1')
        assert len(filtered) == 2

    def test_filter_by_type(self):
        tl = EventTimeline()
        tl.record('ws_connect', 'inbound')
        tl.record('ws_message', 'outbound')
        tl.record('ws_connect', 'inbound')
        assert len(tl.filter_by_type('ws_connect')) == 2

    def test_save_and_load(self, tmp_path):
        tl = EventTimeline()
        tl.record('http_request', 'outbound', status=200)
        path = tmp_path / 'timeline.json'
        tl.save(path)

        tl2 = EventTimeline.load(path)
        assert tl2.count == 1
        assert tl2.events[0].event_type == 'http_request'

    def test_data_preserved(self):
        tl = EventTimeline()
        tl.record('ws_message', 'inbound', payload_size=1024)
        assert tl.events[0].data == {'payload_size': 1024}


class TestTestArtifactManifest:

    def test_add_artifact(self):
        m = TestArtifactManifest(
            test_suite='unit', run_id='run-1', started_at=NOW,
        )
        m.add_artifact('log', 'path/to/log.jsonl', 'log')
        assert len(m.artifacts) == 1

    def test_finish(self):
        m = TestArtifactManifest(
            test_suite='unit', run_id='run-1', started_at=NOW,
        )
        m.finish(summary={'passed': 10, 'failed': 0})
        assert m.finished_at > 0
        assert m.summary['passed'] == 10

    def test_duration(self):
        m = TestArtifactManifest(
            test_suite='unit', run_id='run-1',
            started_at=NOW, finished_at=NOW + 5.0,
        )
        assert m.duration_seconds == 5.0

    def test_duration_unfinished(self):
        m = TestArtifactManifest(
            test_suite='unit', run_id='run-1', started_at=NOW,
        )
        assert m.duration_seconds == 0.0

    def test_save_and_load(self, tmp_path):
        m = TestArtifactManifest(
            test_suite='e2e', run_id='run-42', started_at=NOW,
        )
        m.add_artifact('metrics', 'metrics.json', 'metrics')
        m.finish(summary={'tests': 5})
        path = tmp_path / 'manifest.json'
        m.save(path)

        m2 = TestArtifactManifest.load(path)
        assert m2.test_suite == 'e2e'
        assert m2.run_id == 'run-42'
        assert len(m2.artifacts) == 1
        assert m2.summary['tests'] == 5


class TestArtifactPath:

    def test_format(self):
        p = artifact_path(Path('/tmp'), 'unit', 'run-1', '.jsonl')
        assert str(p) == f'/tmp/{ARTIFACT_PREFIX}/unit/run-1.jsonl'

    def test_different_suffixes(self):
        base = Path('/artifacts')
        log = artifact_path(base, 'e2e', 'r1', '.jsonl')
        metrics = artifact_path(base, 'e2e', 'r1', '.metrics.json')
        assert log != metrics
        assert str(log).endswith('.jsonl')
        assert str(metrics).endswith('.metrics.json')
