"""Read-only review of the actual B0-5090-003 Git blobs; no model loads."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COMMIT = '04cc5a879ed9e54800886ae4fc978e7020d71cbc'
PARENT = '514949d6babf14655de8076650e514f493b0138e'
SOURCES = {
    'prompt_guard_2': 'coordination/returns/20261023T013459Z-b0-availability-prompt_guard_2-570957a3/availability.json',
    'datasentinel': 'coordination/returns/20261023T013525Z-b0-availability-datasentinel-ef8859a0/availability.json',
    'llama': 'coordination/returns/20261023T013847Z-b0-availability-llama-5c3f5d39/availability.json',
    'report': 'coordination/returns/20261023T014134Z-b0-5090-003-24f347df/REPORT.md',
}


def check():
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT)
    assert git('rev-parse', COMMIT+'^').decode().strip() == PARENT
    assert sorted(git('diff', '--name-status', PARENT, COMMIT).decode().splitlines()) == sorted('A\t'+p for p in SOURCES.values())
    blobs = {role: git('show', COMMIT+':'+p) for role, p in SOURCES.items()}
    for role, p in SOURCES.items():
        assert (ROOT/p).read_bytes() == blobs[role], 'Source bytes changed: '+p
    pg, ds, ll = [json.loads(blobs[k]) for k in ['prompt_guard_2', 'datasentinel', 'llama']]
    for role, r in [('prompt_guard_2', pg), ('datasentinel', ds), ('llama', ll)]:
        assert r['input_commit'] == PARENT and r['hostname'] == 'DESKTOP-B5PNBNC'
        assert r['role'] == role and r['task_id'] == 'B0-5090-001'
        assert r['candidate_scores_computed'] == 0 and r['model_controls_only'] is True
        assert r['cache_root'] == '/mnt/e/LongPIBench-Reproduction/models/b0-cache'
    assert pg['revision'] == 'a8ded8e697ce7c355e395a0df51f94adb4a2fd27'
    assert pg['status'] == 'BLOCKED_OR_FAILED' and pg['error_type'] == 'GatedRepoError' and pg['http_status'] == 403
    assert ds['status'] == 'DATASENTINEL_MODEL_LOAD_AND_CONTROLS_PASSED_NOT_B0_EVALUATION'
    plan = json.loads((ROOT/'g0_resume_diagnosis/frozen_controls_v1/plan.json').read_text(encoding='utf8'))
    accepted = json.loads((ROOT/'coordination/returns/20261019T054409Z-g0-visibility-fd1beae5/g0_audit.json').read_text(encoding='utf8'))
    assert ds['original_model_configuration'] == plan['model_config']
    assert ds['generation_defaults'] == plan['saved_generation_defaults']
    assert ds['accepted_fixed_file_hashes'] == accepted['model_audit']['actual_fixed_files_sha256_verified']
    assert ds['max_context'] == 32768 and len(ds['controls']) == 3
    assert [c['binary_flag'] for c in ds['controls']] == [0, 0, 0]
    assert all(c['risk_probability'] is None for c in ds['controls'])
    assert ll['status'] == 'LLAMA_MODEL_LOAD_AND_SHORT_CONTROL_PASSED_NOT_B0_EVALUATION'
    assert ll['model_source']['revision'] == '0e9e39f249a16976918f6564b8830bc894c89659'
    assert ll['load_mode'] == 'BF16_NO_QUANTIZATION' and ll['embedding_dtype'] == 'torch.bfloat16'
    assert ll['finite_logits'] and ll['model_load_verified'] and ll['synthetic_forward_verified'] and ll['short_generation_verified']
    assert '5090' in ll['cuda']['device'] and ll['max_context'] == 131072
    assert ll['generation_overrides'] == {'max_new_tokens': 8, 'do_sample': False, 'pad_token_id': 128009}
    report = blobs['report'].decode()
    assert '127' in report and '/tmp' in report
    return {
        'status': 'B0_003_PARTIAL_AVAILABILITY_ACCEPTED_PG2_BLOCKED',
        'source_commit': COMMIT, 'input_commit': PARENT,
        'source_sha256': {p: hashlib.sha256(blobs[k]).hexdigest() for k, p in SOURCES.items()},
        'source_changes_only_four_additions': True,
        'prompt_guard_2': {'accepted': False, 'status': 'BLOCKED_HTTP_403', 'model_loaded': False},
        'datasentinel': {'accepted': True, 'scope': 'Frozen constructor and binary interface load/short controls only',
                         'load_seconds': ds['load_seconds'], 'control_flags': [0, 0, 0],
                         'explicit_override_control_detected': False, 'injection_probability': None},
        'llama': {'accepted': True, 'scope': 'BF16 load, finite forward and short generation only',
                  'load_seconds': ll['load_seconds_including_disk_io'], 'b4_b5_prompt_validation_complete': False,
                  'model_file_check_scope': ll['model_file_check_scope']},
        'llama_initial_shell_failure': {'exit_code': 127, 'model_loaded': False,
                                       'evidence_scope': 'Executor summary declaration only; no independent shell log',
                                       'independently_verified': False, 'preserved': True},
        'dependencies_saved_in_llama_receipt': ll['packages'],
        'not_independent_gpu_rerun': True, 'candidate_scores_computed': 0,
        'datasentinel_control_result_is_b0_performance': False,
        'allowed_next': 'Prepare frozen non-PG2 exploratory score collection; PG2 remains missing, no substitute',
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()
    result = check(); path = HERE/'verification.json'
    if args.check_only:
        assert result == json.loads(path.read_text(encoding='utf8'))
    else:
        with path.open('x', encoding='utf8', newline='\n') as f:
            json.dump(result, f, ensure_ascii=False, indent=2); f.write('\n')
    print(result['status'])


if __name__ == '__main__':
    main()
