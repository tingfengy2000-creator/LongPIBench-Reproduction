import json
import pytest
from repro.archive import RunArchive


def test_existing_run_and_attempt_are_never_overwritten(tmp_path):
    archive = RunArchive(tmp_path, {'seed': 42}, run_kind='debug', run_id='test-run')
    path = archive.write_attempt(suite='email', item_id=0, condition='promptlocate', attempt=1, evidence={'raw_response': 'first'})
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        archive.write_attempt(suite='email', item_id=0, condition='promptlocate', attempt=1, evidence={'raw_response': 'replacement'})
    assert path.read_bytes() == before
    with pytest.raises(FileExistsError):
        RunArchive(tmp_path, {'seed': 43}, run_kind='debug', run_id='test-run')
    archive.write_attempt(suite='email', item_id=0, condition='promptlocate', attempt=2, evidence={'raw_response': 'retry'})


def test_config_is_detached_and_identity_cannot_be_overridden(tmp_path):
    config = {'model': {'name': 'test-double'}}
    archive = RunArchive(tmp_path, config, run_kind='debug', run_id='test')
    config['model']['name'] = 'changed'
    path = archive.write_attempt(suite='resume', item_id=2, condition='no_defense', attempt=1,
                                 evidence={'run_kind': 'formal', 'item_id': 99})
    record = json.loads(path.read_text(encoding='utf-8'))
    assert record['run_kind'] == 'debug' and record['item_id'] == 2
    assert archive.config['model']['name'] == 'test-double'


def test_nan_is_rejected_without_creating_result_file(tmp_path):
    archive = RunArchive(tmp_path, {}, run_kind='debug', run_id='test')
    with pytest.raises(ValueError):
        archive.write_attempt(suite='email', item_id=0, condition='no_defense', attempt=1, evidence={'score': float('nan')})
    assert list(archive.path.glob('*attempt*')) == []


def test_unsafe_run_path_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        RunArchive(tmp_path, {}, run_kind='debug', run_id='../escape')
