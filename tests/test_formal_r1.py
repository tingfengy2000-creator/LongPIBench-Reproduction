import json
import shutil
import sys
from types import SimpleNamespace

import pytest

from repro.target_runtime import stop_reason, check_context
from scripts import run_formal_r1 as r1


def test_frozen_config_cannot_silently_change_token_budget(tmp_path):
    (tmp_path / 'configs').mkdir()
    shutil.copyfile(r1.ROOT / r1.CONFIG_PATH, tmp_path / r1.CONFIG_PATH)
    shutil.copyfile(r1.ROOT / 'configs/upstream_lock.json', tmp_path / 'configs/upstream_lock.json')
    assert r1.load_config(tmp_path)['target']['max_new_tokens'] == 20000
    path = tmp_path / r1.CONFIG_PATH
    config = json.loads(path.read_text())
    config['target']['max_new_tokens'] = 512
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='Frozen R1 v1 configuration changed'):
        r1.load_config(tmp_path)


def test_invalid_or_censored_outputs_do_not_count_as_evaluable_false():
    counts = {}
    case = {'suite': 'email', 'attack': 'authority_spoof'}
    r1.add_count(counts, case, {'validity': 'F6', 'evaluation': {'official_success': False, 'issues': ['JSON_PARSE_ERROR']}})
    r1.add_count(counts, case, {'validity': 'CENSORED_TOKEN_LIMIT', 'evaluation': {'official_success': False},
                              'target': {'stop_reason': 'TOKEN_LIMIT'}})
    r1.add_count(counts, case, {'validity': 'VALID', 'evaluation': {'official_success': False}})
    row = counts['email:authority_spoof']
    assert row['attempted'] == 3 and row['invalid_or_censored'] == 2
    assert row['official_false_evaluable'] == 1 and row['evaluable'] == 1
    assert row['token_limit'] == 1 and row['parse_error_official_false'] == 1


def test_eos_at_budget_is_distinct_from_forced_token_limit_and_no_truncation():
    assert stop_reason([1, 2], [2], 2) == 'EOS'
    assert stop_reason([1, 3], [2], 2) == 'TOKEN_LIMIT'
    assert stop_reason([1], [2], 2) == 'OTHER_STOP'
    with pytest.raises(ValueError):
        check_context(100, 20000, 10000)
    with pytest.raises(ValueError):
        stop_reason([], [2], 2)


def test_inference_exception_retains_failed_attempt_and_stops_remaining_cases(tmp_path):
    class Target:
        last_attempt = {'input_token_ids': [7], 'generation_attempted': True}
        def generate(self, *args):
            raise RuntimeError('synthetic CUDA failure')
    cases = [{'case_id': 'email-000-no', 'suite': 'email', 'attack': 'no',
              'goal': '0', 'system_prompt': 'task', 'data_prompt': 'document'},
             {'case_id': 'email-001-no', 'suite': 'email', 'attack': 'no',
              'goal': '0', 'system_prompt': 'task', 'data_prompt': 'second'}]
    report = {'run_id': 'formal-test'}
    with pytest.raises(RuntimeError, match='synthetic CUDA failure'):
        r1.execute_cases(cases, Target(), SimpleNamespace(), {'study_condition': 'test'}, report, tmp_path)
    saved = json.loads((tmp_path / 'email-000-no.json').read_text())
    assert saved['validity'] == 'F6' and saved['target']['input_token_ids'] == [7]
    assert saved['run_kind'] == 'formal'
    assert len(report['case_evidence']) == 1 and not (tmp_path / 'email-001-no.json').exists()


def test_wrong_host_cannot_begin_formal_inference(tmp_path, monkeypatch):
    monkeypatch.setattr(r1, 'ROOT', tmp_path)
    monkeypatch.setattr(r1.platform, 'node', lambda: 'cloud-vm')
    monkeypatch.setattr(r1.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(r1.pilot, 'git_head', lambda: 'input-head')
    monkeypatch.setattr(r1, 'load_config', lambda *a: pytest.fail('Wrong host must stop before setup'))
    monkeypatch.setattr(sys, 'argv', ['run_formal_r1.py'])
    assert r1.main() == 2
    report = json.loads(next((tmp_path / 'coordination/returns').rglob('r1_run.json')).read_text())
    assert report['formal_inference_executed'] is False and report['status'] == 'FAILED'
