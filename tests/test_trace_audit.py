import json

import pytest

from scripts import analyze_debug_trace as audit


def record():
    return {'case_id': 'email-000-no', 'validity': 'F6_DEBUG', 'detector_flag': 1, 'seconds': 3,
        'trace': {'events': [
            {'function': 'query', 'role': 'localization_oracle', 'data': 'same', 'binary_result': 1, 'seconds': 3},
            {'function': 'query_localization', 'role': 'localization_oracle', 'prompt': 'format', 'raw_response': 'output', 'seconds': 2},
            {'function': 'generate', 'role': 'localization_oracle', 'generated_token_ids': [1, 2], 'seconds': 1},
            {'function': 'binary_search', 'segments': ['a', 'b'], 'start': 0, 'end': 2, 'prefix': '', 'result': [1, 1, {'a': 1}]},
            {'function': 'binary_search', 'segments': ['b'], 'start': 0, 'end': 1, 'prefix': '', 'result': [1, 0, {'a': 1}]},
        ], 'call_count': 6, 'debug_budgets': {'max_observed_calls': 5, 'max_seconds': 1200},
            'logged_errors': [{'message': 'DEBUG_TRACE_BUDGET_EXCEEDED'}], 'nonfinite_helper': False}}


def test_nested_observations_are_not_counted_as_multiple_generations():
    summary = audit.summarize_case(record())
    assert summary['recorded_event_count'] == 5
    assert summary['completed_model_generate_calls'] == 1
    assert summary['completed_generation_seconds_sum'] == 1
    assert summary['completed_oracle_decisions'] == 1
    assert summary['consecutive_segment_count_changes'] == [-1]
    assert summary['completed_helper_probability_calls'] == 0
    assert summary['model_executed'] is False


def test_repeated_search_state_and_query_are_reported_without_claiming_infinite_loop():
    data = record()
    data['trace']['events'].append(dict(data['trace']['events'][0]))
    data['trace']['events'].append(dict(data['trace']['events'][3]))
    summary = audit.summarize_case(data)
    assert summary['repeated_role_query_texts'][0]['count'] == 2
    assert summary['repeated_completed_search_states'][0]['count'] == 2
    assert 'do not prove an infinite loop' in summary['search_progress_interpretation']


@pytest.mark.parametrize('corrupt', [False, True])
def test_local_raw_digest_must_match_original_receipt(tmp_path, corrupt):
    raw = tmp_path / 'runs' / 'original'
    raw.mkdir(parents=True)
    path = raw / 'case.json'
    blob = json.dumps(record()).encode()
    path.write_bytes(blob)
    receipt = {'task_id': 'R0-5090-012', 'operation': 'defense', 'status': 'DEBUG_DEFENSE_RECORDED',
        'run_id': 'old-run', 'git_head': 'old-commit', 'plan_sha256': 'plan-hash',
        'cases': [{'case_id': 'email-000-no', 'validity': 'F6_DEBUG', 'evidence_path': str(path),
                   'evidence_sha256': audit.sha_bytes(blob)}]}
    receipt_path = tmp_path / 'stage.json'
    receipt_path.write_text(json.dumps(receipt))
    if corrupt:
        path.write_bytes(blob + b' ')
        with pytest.raises(ValueError, match='differs from original'):
            audit.analyze_receipt(tmp_path, receipt_path)
    else:
        result = audit.analyze_receipt(tmp_path, receipt_path)
        assert result['cases'][0]['source_raw_sha256'] == audit.sha_bytes(blob)
        assert path.read_bytes() == blob
