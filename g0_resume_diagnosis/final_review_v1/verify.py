"""Independent final G0 count/source verification. No model or new experiments."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
COMMIT = 'a857540235093e302b0644c4aebf38184a6045a9'
PREFIX = 'coordination/returns/20261019T060252Z-g0-controls-c9032be1/'


def blob(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', COMMIT+':'+path])


def csv_rows(name):
    with (OUT / name).open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check-only', action='store_true', help='Repeat checks without replacing verification.json')
    args = ap.parse_args()
    analysis = json.loads((OUT/'analysis.json').read_text(encoding='utf-8'))
    rows = json.loads(blob(PREFIX+'control_results.json'))
    assert len(rows) == len({r['control_id'] for r in rows}) == 26
    assert Counter(r['binary_flag'] for r in rows) == {0: 22, 1: 4}
    assert Counter(r['condition'] for r in rows) == {'natural_full': 4, 'payload_only': 2, 'crossed_prefix': 16, 'intentional_payload_exclusion': 4}
    assert all(r['error'] is None and r['raw_lm_logits_finite'] and not r['interface_decision_difference'] for r in rows)
    assert all(r['native_injection_probability'] is None for r in rows)
    assert len(csv_rows('all26_controls.csv')) == 26 and len(csv_rows('resume100_visibility.csv')) == 100
    assert all(r['root_category'] == 'B' and r['payload_complete_in_actual_input'] == 'True' and r['truncation_direction'] == 'none'
               for r in csv_rows('resume100_visibility.csv'))
    matrix = csv_rows('crossed_matrix.csv')
    assert len(matrix) == 8
    for m in matrix:
        subset = [r for r in rows if r['condition'] == 'crossed_prefix' and r['domain'] == m['body_domain']
                  and r['payload_domain'] == m['payload_domain'] and r['body_budget'] == int(m['body_tokens'])]
        assert len(subset) == int(m['source_count']) == 2
        assert sum(r['binary_flag'] == 1 for r in subset) == int(m['flag1_count'])
        assert sum(r['binary_flag'] == 0 for r in subset) == int(m['flag0_count'])
        assert all(r['input_token_count'] == int(m['actual_total_tokens']) for r in subset)
    crossed_positive = {r['control_id'] for r in rows if r['condition'] == 'crossed_prefix' and r['binary_flag'] == 1}
    assert crossed_positive == {'prefix-resume-000-n128-pemail', 'prefix-resume-050-n128-pemail'}
    assert all(r['binary_flag'] == 0 for r in rows if r['payload_domain'] == 'resume')
    for pair in csv_rows('domain_pairs.csv'):
        a = next(r for r in rows if r['control_id'] == pair['email_control'])
        b = next(r for r in rows if r['control_id'] == pair['resume_control'])
        assert a['input_token_count'] == b['input_token_count'] == int(pair['total_tokens_each'])
        assert a['payload_domain'] == b['payload_domain']
        assert a['binary_flag'] == int(pair['email_flag']) and b['binary_flag'] == int(pair['resume_flag'])
    assert all(r['historical_R2_tokens_identical'] and r['historical_R2_binary_identical']
               for r in rows if r['condition'] == 'natural_full')
    shape_values = sum(r['raw_lm_logits_shape'][0]*r['raw_lm_logits_shape'][1] for r in rows)
    preview = [v for r in rows for step in r['raw_logit_top5_by_step'] for v in step['raw_logits']]
    assert shape_values == analysis['raw_full_logit_values_stored_on_source'] == 8320000
    assert len(preview) == analysis['raw_logit_top5_values_checked_on_coordinator'] == 1300
    assert all(math.isfinite(v) for v in preview)
    assert all(dtype == 'torch.float16' for r in rows for dtype in r['original_logit_dtypes'])
    assert analysis['full_npz_arrays_independently_read_on_coordinator'] is False
    assert analysis['algorithm_development_go'] is False and analysis['stop_after_G0'] is True
    assert analysis['script_sha256'] == hashlib.sha256((OUT/'analyze.py').read_bytes()).hexdigest()
    for path, expected in analysis['source_return_file_sha256'].items():
        original = blob(path)
        assert hashlib.sha256(original).hexdigest() == expected
        working = (ROOT/path).read_bytes()
        assert working == original or working.replace(b'\r\n', b'\n') == original
    changes = subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--name-only', COMMIT]).decode().splitlines()
    assert all(p.startswith('g0_resume_diagnosis/final_review_v1/') for p in changes), changes
    result = {'status': 'PASS_G0_COMPLETE_WITH_DECLARED_LIMITS_STOP', 'source_commit': COMMIT,
        'source_return_files_preserved': len(analysis['source_return_file_sha256']),
        'control_rows_independently_recounted': 26, 'frozen_cross_domain_pairs_equal_length': 8,
        'historical_resume_visibility_rows': 100, 'historical_resume_category': 'B100',
        'raw_logit_preview_values_finite': 1300, 'full_raw_npz_locally_verified': False,
        'natural_replay_equal_tokens_and_binary': 4, 'new_model_forward_during_review': 0,
        'algorithm_development_go': False, 'stop_after_G0': True,
        'not_a_population_performance_test': True}
    if not args.check_only:
        with (OUT/'verification.json').open('x', encoding='utf-8', newline='\n') as f:
            json.dump(result, f, indent=2); f.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
