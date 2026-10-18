import hashlib
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace, ModuleType

import pytest

from repro.archive import json_bytes
from repro.locator_trace import LocatorTrace
from repro.scoring import evaluate_response
from scripts import audit_formal_r1 as audit
from scripts import run_formal_r1 as r1
from scripts import run_formal_r2 as r2


def test_r2_freeze_rejects_changed_checkpoint_and_retains_r1(tmp_path):
    config, target = r2.load_config(r2.ROOT)
    assert config['whole_detector'] == 'detector_large/checkpoint-5000'
    assert target['target']['max_new_tokens'] == 20000
    (tmp_path / 'configs').mkdir()
    shutil.copyfile(r2.ROOT / r2.CONFIG, tmp_path / r2.CONFIG)
    changed = dict(config, whole_detector='detector_small/checkpoint-500')
    (tmp_path / r2.CONFIG).write_bytes(json_bytes(changed))
    with pytest.raises(ValueError, match='Frozen R2 configuration changed'):
        r2.load_config(tmp_path)


def detector():
    return SimpleNamespace(detect=lambda *a: 0, query=lambda *a: 0,
        model=SimpleNamespace(query=lambda *a: '', query_localization=lambda *a: '',
                              ft_model=SimpleNamespace(generate=lambda *a, **k: None)))


def test_boundary_observation_reads_actual_values_and_restores_numpy_reference():
    class Values(list):
        def tolist(self): return list(self)
    indices = (Values([0]),)
    original_np = SimpleNamespace(where=lambda *a, **k: indices)
    module = ModuleType('synthetic_boundaries')
    module.np = original_np
    module.Values = Values
    exec('''def split_sentence(sentence, nlp, tokenizer, embedding_layer, thres=0.0):
    sub_sentence = sentence
    words = ['A', 'B']
    offsets = [(0, 1), (2, 3)]
    cos_sim = Values([-0.25])
    positions = np.where([True])
    assert positions is expected_indices
    return ['A', 'B']
''', module.__dict__)
    module.expected_indices = indices
    for name in ['compute_conditional_probability', 'causal_influence', 'binary_search', 'binary_search_injection', 'find_data_end']:
        setattr(module, name, lambda *a: None)
    observer = LocatorTrace(module, record_boundaries=True).install(detector(), SimpleNamespace(bd=detector()))
    try:
        assert module.split_sentence('A B', None, None, None) == ['A', 'B']
        row = observer.events[0]['boundary_observations'][0]
        assert row['adjacent_word_cosine'] == [-0.25] and row['split_positions'] == [0]
        assert row['clause_offsets'] == [[0, 1], [2, 3]]
        assert observer.segment_mapping['spans'] == [[0, 1], [2, 3]]
    finally:
        observer.close()
    assert module.np is original_np


@pytest.mark.parametrize('kind,expected', [('budget', 'CENSORED_RESOURCE'), ('nan', 'F6'), ('cuda', 'F6')])
def test_upstream_swallowed_errors_are_not_normal_defense_paths(kind, expected):
    class Observer:
        def reset(self):
            self.events, self.errors = [], []
            self.nonfinite, self.boundary_nonfinite = False, False
            self.calls, self.segment_mapping = 1, None
        def record(self):
            return {'events': self.events, 'logged_errors': self.errors}
    observer = Observer()
    def swallowed(*args):
        if kind == 'budget': observer.errors.append({'message': 'FORMAL_RESOURCE_GUARD_EXCEEDED'})
        if kind == 'nan': observer.nonfinite = True
        if kind == 'cuda': observer.events.append({'function': 'query', 'error_message': 'CUDA out of memory'})
        if kind == 'cuda': observer.errors.append({'message': 'upstream fallback'})
        return 'original', ''
    record, fatal = r2.defense_case({'case_id': 'email-000-no', 'data_prompt': 'original', 'system_prompt': 'task'},
        SimpleNamespace(detect=lambda *a: 1), SimpleNamespace(locate_and_recover=swallowed), observer)
    assert record['validity'] == expected
    assert fatal is (kind == 'cuda')


def test_all_invalid_defense_cases_skip_target_model_and_keep_denominators(tmp_path, monkeypatch):
    monkeypatch.setattr(r2, 'ROOT', tmp_path)
    monkeypatch.setattr(r2, 'FixedLocalTarget', lambda *a: pytest.fail('Must not load target for invalid defense'))
    monkeypatch.setattr(r2.pilot, 'benchmark_module', lambda *a: SimpleNamespace())
    raw = tmp_path / 'runs/defense'; raw.mkdir(parents=True)
    out = tmp_path / 'runs/protected'; out.mkdir()
    returns = tmp_path / 'coordination/returns'; returns.mkdir(parents=True)
    case = {'case_id': 'email-072-authority_spoof', 'suite': 'email', 'attack': 'authority_spoof'}
    record = {'input': case, 'validity': 'CENSORED_RESOURCE', 'config_sha256': r2.CONFIG_SHA, 'detector_flag': 1}
    path = raw / (case['case_id'] + '.json'); path.write_bytes(json_bytes(record))
    defense = {'plan_sha256': 'plan', 'status': 'FORMAL_R2_DEFENSE_EXECUTED_REVIEW_REQUIRED', 'raw_dir': str(raw),
        'cases': [{'case_id': case['case_id'], 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                   'bytes': path.stat().st_size, 'validity': 'CENSORED_RESOURCE'}]}
    receipt = returns / 'defense.json'; receipt.write_bytes(json_bytes(defense))
    report = {'plan_sha256': 'plan', 'run_id': 'new-protected'}
    r2.protected_stage({}, [case], receipt, report, out)
    counts = report['counts']['email:authority_spoof']
    assert counts['attempted'] == 1 and counts['target_generation_attempted'] == 0
    assert counts['invalid_or_censored'] == 1 and counts['official_false_evaluable'] == 0


def test_r1_readonly_audit_rejects_changed_counts_and_decoded_tokens(tmp_path):
    root = tmp_path
    raw = root / 'runs/original'; raw.mkdir(parents=True)
    config = r1.load_config(r1.ROOT)
    case = {'case_id': 'email-000-no', 'suite': 'email', 'attack': 'no', 'goal': '0',
            'system_prompt': 'task', 'data_prompt': 'document'}
    text = '{"summary":"a","response":"b"}'
    benchmark = SimpleNamespace(parse_json_response=json.loads, score_response=lambda *a: False)
    evaluation = evaluate_response('email', '0', text, parse=json.loads, score=benchmark.score_response)
    target = {'messages': [{'role': 'system', 'content': 'task'}, {'role': 'user', 'content': 'document'}],
        'rendered_prompt': 'rendered', 'input_token_ids': [128000, 5], 'input_token_count': 2,
        'generated_token_ids': [7, 128009], 'output_token_count': 2, 'raw_response': text,
        'chat_template_sha256': config['target']['chat_template_sha256'], 'stop_reason': 'EOS',
        'generation_attempted': True, 'generation_overrides': {'max_new_tokens': 20000, 'do_sample': False, 'pad_token_id': 128009}}
    record = {'run_id': 'original', 'run_kind': 'formal', 'stage': 'R1', 'condition': 'no_defense',
        'frozen_config_sha256': r1.FROZEN_CONFIG_SHA256, 'study_condition': config['study_condition'],
        'case_id': case['case_id'], 'input': case, 'target': target, 'evaluation': evaluation, 'validity': 'VALID'}
    path = raw / (case['case_id'] + '.json'); path.write_bytes(json_bytes(record))
    row = {'case_id': case['case_id'], 'path': str(path), 'bytes': path.stat().st_size,
           'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'validity': 'VALID'}
    counts = {}; r1.add_count(counts, case, record)
    source = {'raw_dir': str(raw), 'run_id': 'original', 'case_evidence': [row], 'counts': counts}
    tokenizer = SimpleNamespace(apply_chat_template=lambda *a, tokenize, **k: [128000, 5] if tokenize else 'rendered',
                                decode=lambda *a, **k: text)
    assert audit.audit_cases(root, source, [case], benchmark, config, tokenizer)['verified_raw_count'] == 1
    counts['email:no']['official_true_evaluable'] = 1
    with pytest.raises(ValueError, match='Recomputed counts differ'):
        audit.audit_cases(root, source, [case], benchmark, config, tokenizer)
    counts['email:no']['official_true_evaluable'] = 0
    tokenizer.decode = lambda *a, **k: 'tampered'
    with pytest.raises(ValueError, match='Decoded response mismatch'):
        audit.audit_cases(root, source, [case], benchmark, config, tokenizer)


def test_wrong_host_stops_before_reading_raw_or_loading_models(tmp_path, monkeypatch):
    (tmp_path / 'runs').mkdir()
    monkeypatch.setattr(r2, 'ROOT', tmp_path)
    monkeypatch.setattr(r2, 'load_config', lambda *a: ({}, {}))
    monkeypatch.setattr(r2.pilot, 'git_head', lambda: 'test-head')
    monkeypatch.setattr(r2.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(r2.platform, 'node', lambda: 'cloud-vm')
    monkeypatch.setattr(sys, 'argv', ['run_formal_r2.py'])
    assert r2.main() == 2
    report = json.loads(next((tmp_path / 'coordination/returns').rglob('r2_stage.json')).read_text())
    assert report['formal_inference_attempted'] is False and report['status'] == 'FAILED'
