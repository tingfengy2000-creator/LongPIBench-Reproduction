from types import SimpleNamespace
import json
import sys

from scripts import run_email_continuation as continuation
import pytest


def test_prefix_ignores_censoring_and_timing_but_checks_actual_outputs():
    old = {'trace': {'events': [{'function': 'binary_search_injection', 'error_type': 'RuntimeError'},
        {'function': 'generate', 'generated_token_ids': [1, 2], 'seconds': 10},
        {'function': 'compute_conditional_probability', 'finite': True, 'average_log_probability': -0.1}]}}
    new = {'trace': {'events': [{'function': 'binary_search_injection', 'intervals_and_query_count': [[], 1]},
        {'function': 'generate', 'generated_token_ids': [1, 2], 'seconds': 20},
        {'function': 'compute_conditional_probability', 'finite': True, 'average_log_probability': -0.1000001},
        {'function': 'query'}]}}
    assert continuation.compare_completed_prefix(old, new)['logical_prefix_matches'] is True
    new['trace']['events'][1]['generated_token_ids'] = [1, 3]
    mismatch = continuation.compare_completed_prefix(old, new)
    assert mismatch['logical_prefix_matches'] is False and mismatch['first_difference_index'] == 1


def test_shorter_trace_cannot_claim_prefix_equivalence():
    old = {'trace': {'events': [{'function': 'query'}, {'function': 'generate'}]}}
    new = {'trace': {'events': [{'function': 'query'}]}}
    assert continuation.compare_completed_prefix(old, new)['logical_prefix_matches'] is False


def test_wrong_host_does_not_restart_email_models(tmp_path, monkeypatch):
    monkeypatch.setattr(continuation, 'ROOT', tmp_path)
    monkeypatch.setattr(continuation.platform, 'node', lambda: 'cloud-vm')
    monkeypatch.setattr(continuation.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(continuation.pilot, 'git_head', lambda: 'head')
    monkeypatch.setattr(sys, 'argv', ['run_email_continuation.py'])
    assert continuation.main() == 2
    report = json.loads(next((tmp_path / 'coordination/returns').rglob('email_stage.json')).read_text())
    assert report['status'] == 'FAILED' and report['old_evidence_modified'] is False


def test_changed_method_parameter_is_rejected_even_with_new_debug_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(continuation, 'ROOT', tmp_path)
    monkeypatch.setattr(continuation.pilot, 'git_head', lambda: 'new-head')
    folder = tmp_path / 'runs' / 'condition'
    folder.mkdir(parents=True)
    parent_path = folder / 'parent.json'
    parent_path.write_text(json.dumps({'task_id': 'R0-5090-012', 'git_head': 'old-head', 'locator_sep_thres': 0.0}))
    plan = {'task_id': 'R0-5090-014', 'git_head': 'new-head', 'trace_call_budget': 8192,
        'trace_seconds_budget': 3600, 'target_max_new_tokens': 512, 'formal_checkpoint_selected': False,
        'parent_plan_path': str(parent_path), 'parent_plan_sha256': continuation.pilot.file_sha(parent_path),
        'locator_sep_thres': 0.5}
    path = folder / 'plan.json'
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match='Model/method condition differs'):
        continuation.load_plan(path, {})
