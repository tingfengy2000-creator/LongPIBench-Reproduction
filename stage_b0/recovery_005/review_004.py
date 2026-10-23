"""Read-only receipt review; cached score contents are verified later on5090."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = '204867e8af93f285657905c80f0c5a01e4acef36'
PARENT = 'd0eca701b3a2ae207bf52f40fe0b110bc63b94e5'
RECEIPT = ROOT/'coordination/returns/20261023T034320Z-b0-scores-23f075cc'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check():
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT)
    assert git('rev-parse', SOURCE+'^').decode().strip() == PARENT
    expected = ['REPORT.md', 'collection_run.json', 'datasentinel_collection.json', 'piguard_collection.json', 'prompt_guard_1_collection.json']
    files = [(RECEIPT/name).relative_to(ROOT).as_posix() for name in expected]
    assert sorted(git('diff', '--name-status', PARENT, SOURCE).decode().splitlines()) == sorted('A\t'+p for p in files)
    for path in files:
        assert (ROOT/path).read_bytes() == git('show', SOURCE+':'+path)
    state = json.loads((RECEIPT/'collection_run.json').read_text(encoding='utf8'))
    assert state['status'] == 'COLLECTION_FAILED_STOP_REVIEW' and state['candidate_records_saved'] == 800
    assert state['input_commit'] == PARENT and not state['holdout_metrics_computed'] and not state['thresholds_fitted']
    assert state['execution_plan_sha256'] == sha(ROOT/'stage_b0/scoring_v2/execution_plan.json')
    assert [(r['role'], r['exit_code']) for r in state['roles']] == [('piguard', 0), ('prompt_guard_1', 0), ('datasentinel', 3)]
    summaries = {}
    for role in ['piguard', 'prompt_guard_1', 'datasentinel']:
        path = RECEIPT/(role+'_collection.json')
        r = json.loads(path.read_text(encoding='utf8'))
        parent_record = next(x for x in state['roles'] if x['role'] == role)
        assert parent_record['completion_sha256'] == sha(path)
        assert r['execution_plan_sha256'] == state['execution_plan_sha256']
        if role != 'datasentinel':
            assert r['record_counts'] == {'VALID': 400} and r['candidate_records_saved'] == 400
            assert r['dtype'] == 'torch.float32' and '5090' in r['device']
            assert len(r['warmup_controls_excluded']) == 3 and all(c['native_equivalence'] for c in r['warmup_controls_excluded'])
            assert len(r['raw_file_sha256']) == 801
            for name, digest in r['raw_file_sha256'].items():
                assert state['raw_manifest_sha256'][role+'/'+name] == digest
        else:
            assert r['error_type'] == 'AssertionError' and r['assertion_reason'] == ''
            assert r['candidate_records_saved'] == 0 and r['record_counts'] == {}
            assert set(r['raw_file_sha256']) == {'start.json'}
        summaries[role] = {'candidate_records_saved': r['candidate_records_saved'], 'record_counts': r['record_counts']}
    return {'status': 'B0_004_PARTIAL_RECEIPT_ACCEPTED_RAW_VERIFICATION_REQUIRED', 'source_commit': SOURCE,
            'source_sha256': {p: sha(ROOT/p) for p in files}, 'roles': summaries, 'llama_started': False,
            'supervisor_exit_code': 3, 'cached_classifier_records': 800, 'cached_raw_independently_read_on_coordinator': False,
            'new_performance_metrics_computed': False, 'nf4_class_name_collision': 'Static defect identified; historical failing guard not recorded',
            'historical_model_or_data_modified': False}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--check-only', action='store_true'); args = ap.parse_args()
    result = check(); output = HERE/'receipt_review.json'
    if args.check_only:
        assert result == json.loads(output.read_text(encoding='utf8'))
    else:
        with output.open('x', encoding='utf8', newline='\n') as f:
            json.dump(result, f, ensure_ascii=False, indent=2); f.write('\n')
    print(result['status'])
