"""Execute exactly26 frozen G0 mechanism controls on the original detector.

Original query/detect and generate arguments are unchanged. A read-only hook
copies raw last-position LM logits before generation processors; no risk score.
"""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repro.archive import json_bytes
from repro.locator_trace import LocatorTrace
from g0_resume_diagnosis.audit_existing import extracted_replay, replay_query

PLAN = 'g0_resume_diagnosis/frozen_controls_v1/plan.json'
PLAN_SHA = '39639607866a6cbc5c2a44be6516c68e9022cf0e4bf3733ade4cc7dc64a442f8'
G0 = 'coordination/returns/20261019T054409Z-g0-visibility-fd1beae5/'


def require(value, message):
    if not value:
        raise ValueError(message)


def file_sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    with Path(path).open('xb') as f:
        f.write(json_bytes(value))


class RawLogitObserver:
    """Never returns a replacement output or alters any source tensor."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.arrays = []
        self.original_dtypes = []

    def __call__(self, module, args, output):
        logits = output.logits
        require(logits.ndim == 3 and logits.shape[0] == 1, 'Unexpected LM logits shape')
        self.original_dtypes.append(str(logits.dtype))
        self.arrays.append(logits[0, -1, :].detach().float().cpu().numpy().copy())
        return None


def load_and_verify_plan():
    require(file_sha(ROOT / PLAN) == PLAN_SHA, 'Frozen plan changed')
    plan = read(ROOT / PLAN)
    require(plan['query_count'] == len(plan['controls']) == 26
            and len({c['control_id'] for c in plan['controls']}) == 26
            and plan['task_id'] == 'G0-5090-002', 'Frozen control population differs')
    require(plan['max_new_tokens'] == 10 and plan['repetition_penalty'] == 1.2, 'Frozen query overrides changed')
    for package, version in plan['runtime_versions'].items():
        require(importlib.metadata.version(package) == version, 'Original GPU environment differs: ' + package)
    accepted = read(ROOT / G0 / 'g0_audit.json')
    require(accepted['status'] == 'G0_HISTORICAL_VISIBILITY_AUDIT_COMPLETE_REVIEW_REQUIRED'
            and accepted['model_audit']['runtime_whole_config'] == plan['model_config'], 'G0 detector source differs')
    for entry in accepted['model_audit']['actual_fixed_files_sha256_verified']:
        if entry['kind'] == 'base_snapshot':
            path = Path(plan['model_config']['model_info']['name']) / entry['filename']
            expected = entry['sha256']
        else:
            path = Path(plan['model_config']['params']['ft_path']) / Path(entry['member']).name
            expected = entry['sha256_first_observed']
        print('Checking fixed file: ' + path.name, flush=True)
        require(path.stat().st_size == entry['size_bytes'] and file_sha(path) == expected, 'Fixed model/tokenizer/adapter changed: ' + path.name)
    return plan, accepted


def execute(folder, raw, report):
    require(platform.system() == 'Linux' and platform.node().casefold() == 'desktop-b5pnbnc', 'Use actual5090 WSL')
    require(shutil.disk_usage(ROOT / 'runs').free >= 1024**3, 'Need1GiB raw space; preserve old evidence')
    plan, accepted = load_and_verify_plan()
    from transformers import AutoTokenizer
    detector_type, formatter_type, manifest = extracted_replay(ROOT / 'upstream/Open-Prompt-Injection')
    require(manifest == plan['upstream_sources'], 'Upstream code differs')
    tokenizer = AutoTokenizer.from_pretrained(plan['model_config']['model_info']['name'], add_bos_token=True,
        local_files_only=True, token=False, trust_remote_code=False)
    formatter = formatter_type()
    # Validate the committed exact text/token manifest before loading any model.
    for case in plan['controls']:
        require(hashlib.sha256(case['data'].encode()).hexdigest() == case['data_sha256'], 'Frozen control text differs')
        _, query, _ = replay_query(detector_type, case['data'], 'DGDSGNH')
        prompt = formatter.formatting_func(query) + '\n### Response: '
        ids = tokenizer(prompt)['input_ids']
        require(prompt == case['formatted_prompt'] and ids == case['input_token_ids']
                and len(ids) == case['input_token_count'], 'Frozen control tokenization differs')
    report.update(plan_sha256=PLAN_SHA, control_manifest_validated_before_model_load=True,
                  original_model_configuration=plan['model_config'], source_G0_run_id=accepted['run_id'])
    save(raw / 'validated_plan.json', plan)
    import torch
    import numpy as np
    require(torch.cuda.is_available(), 'CUDA unavailable')
    props = torch.cuda.get_device_properties(0)
    require('5090' in props.name and props.total_memory >= 30000*1024**2, 'Wrong GPU')
    free, total = torch.cuda.mem_get_info(0)
    require(free >= 16*1024**3, 'Need16GiB free; preserve other processes, do not evict')
    report['cuda_before'] = {'name': props.name, 'free_bytes': free, 'total_bytes': total}
    from repro.opi_loader import load_opi_core
    from scripts.run_debug_pilot import assert_cuda_model
    core = load_opi_core()
    report['model_load_attempted'] = True
    whole = core.DataSentinelDetector(plan['model_config'])
    report['model_weights_loaded'] = True
    assert_cuda_model(whole.model.ft_model)
    require(whole.model.ft_model.active_adapters == ['default'], 'Wrong active adapter')
    require(whole.model.ft_model.generation_config.to_dict() == plan['saved_generation_defaults'], 'Original generation defaults differ')
    report['loaded_generation_defaults'] = whole.model.ft_model.generation_config.to_dict()
    report['loaded_attention_implementation'] = getattr(whole.model.base_model.config, '_attn_implementation', None)
    observer = LocatorTrace(sys.modules[core.PromptLocate.__module__], max_calls=8192, max_seconds=3600,
                            whole_label='whole_large_g0_control')
    observer.observe_query_model(whole, 'whole_large_g0_control')
    logit_observer = RawLogitObserver()
    hook = whole.model.base_model.register_forward_hook(logit_observer)
    historical = {}
    for name in ['email_attack_visibility.jsonl', 'resume_attack_visibility.jsonl']:
        for line in (ROOT / G0 / name).read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            historical[row['case_id']] = row
    public_rows = []
    report['new_forward_queries_attempted'] = 0
    try:
        for case in plan['controls']:
            cid = case['control_id']; observer.reset(); logit_observer.reset()
            report['last_attempted_control_id'] = cid
            error = None; flag = None
            report['new_forward_queries_attempted'] += 1
            try:
                flag = whole.detect(case['data'])
            except Exception as exc:
                error = exc
            trace = observer.record()
            row = {'control_id': cid, 'condition': case['condition'], 'domain': case['domain'],
                'source_document_id': case['source_document_id'], 'payload_domain': case['payload_domain'],
                'body_budget': case['body_budget'], 'data_sha256': case['data_sha256'],
                'input_ids_sha256': case['input_ids_sha256'], 'input_token_count': case['input_token_count'],
                'payload_present_after_preprocessing': case['payload_present_after_preprocessing'],
                'payload_token_span': case['payload_token_span'], 'binary_flag': flag,
                'native_injection_probability': None, 'logit_semantics': 'Unprocessed causal-LM next-token logits, not an injection risk score.',
                'measurement_hook_returns_replacement': False, 'generation_arguments_changed': False,
                'original_logit_dtypes': logit_observer.original_dtypes,
                'error': None if error is None else type(error).__name__+': '+str(error)}
            if logit_observer.arrays:
                values = np.stack(logit_observer.arrays)
                logit_path = raw / (cid + '.raw_lm_logits.npz')
                with logit_path.open('xb') as f:
                    np.savez_compressed(f, raw_last_position_logits=values)
                finite = bool(np.isfinite(values).all())
                row.update(raw_lm_logits_path=str(logit_path), raw_lm_logits_sha256=file_sha(logit_path),
                           raw_lm_logits_shape=list(values.shape), raw_lm_logits_finite=finite)
                if finite:
                    top = np.argsort(values, axis=1)[:, -5:][:, ::-1]
                    row['raw_logit_top5_by_step'] = [{'token_ids': ids.tolist(), 'raw_logits': values[i, ids].tolist()} for i, ids in enumerate(top)]
            raw_path = raw / (cid + '.json')
            # Save the attempt before any post-execution assertion or failure.
            save(raw_path, {'task_id': 'G0-5090-002', 'run_id': report['run_id'], 'frozen_case': case,
                            'trace': trace, 'summary_before_postchecks': row})
            row.update(raw_record_path=str(raw_path), raw_record_sha256=file_sha(raw_path))
            if error is not None:
                public_rows.append(row)
                raise error
            def get_event(name):
                events = [e for e in trace['events'] if e.get('function') == name and e.get('role') == 'whole_large_g0_control']
                require(len(events) == 1, 'Unexpected observation events')
                return events[0]
            detection, query, generation = [get_event(name) for name in ['detect', 'query', 'generate']]
            require(detection['data'] == case['data'] and detection['binary_result'] == flag, 'Observed detect differs')
            require(generation['input_token_ids'] == case['input_token_ids'], 'Actual input differs from frozen IDs')
            require(generation['generation_kwargs'] == {'max_new_tokens': 10, 'repetition_penalty': 1.2}, 'Original generate kwargs changed')
            generated = generation['generated_token_ids']
            require(len(logit_observer.arrays) == len(generated) and row.get('raw_lm_logits_finite') is True,
                    'Missing/nonfinite raw per-step logits; preserve attempt and stop')
            continuation = whole.model.tokenizer.decode(generated, skip_special_tokens=True)
            raw_flag, _, _ = replay_query(detector_type, case['data'], query['raw_response'])
            continuation_flag, _, _ = replay_query(detector_type, case['data'], continuation)
            require(raw_flag == flag, 'Saved response/rule mismatch')
            row.update(generated_token_ids=generated, generated_continuation=continuation,
                original_query_response=query['raw_response'], binary_replayed_from_query=raw_flag,
                binary_replayed_from_continuation_only=continuation_flag,
                interface_decision_difference=continuation_flag != flag,
                declared_query_completed=True)
            if case['condition'] == 'natural_full':
                old = historical[case['source_document_id']+'-authority_spoof']
                row['historical_R2_tokens_identical'] = generated == old['generated_token_ids']
                row['historical_R2_binary_identical'] = flag == old['binary_flag']
            public_rows.append(row)
            save(folder / (cid + '.json'), row)
            report['new_forward_queries_completed'] = len(public_rows)
            print(json.dumps({'completed_frozen_queries': len(public_rows), 'planned': 26, 'last_control': cid}), flush=True)
    finally:
        hook.remove(); observer.close()
        save(raw / 'completed_or_failed_rows.json', public_rows)
    require(len(public_rows) == 26, 'Incomplete frozen population')
    save(folder / 'control_results.json', public_rows)
    report.update(status='G0_FROZEN26_CONTROLS_EXECUTED_REVIEW_REQUIRED', new_forward_queries_completed=26,
        inference_scope='Only one frozen DataSentinel whole model; no helper/oracle/target and no new defense.',
        source_document_count=4, historical_R2_unchanged=True, stop_after_G0=True)


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_IMPLICIT_TOKEN='1', CUDA_VISIBLE_DEVICES='0')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-g0-controls-'+uuid.uuid4().hex[:8]
    folder = ROOT / 'coordination/returns' / run_id; folder.mkdir(parents=True, exist_ok=False)
    raw = ROOT / 'runs' / run_id; raw.mkdir(parents=True, exist_ok=False)
    report = {'task_id': 'G0-5090-002', 'run_id': run_id, 'started_utc': datetime.now(timezone.utc).isoformat(),
        'input_commit': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).decode().strip(),
        'runner_sha256': file_sha(Path(__file__)), 'frozen_plan_sha256': PLAN_SHA, 'model_weights_loaded': False,
        'model_load_attempted': False, 'new_forward_queries_completed': 0, 'local_raw_dir': str(raw),
        'command': 'conda run --no-capture-output -n longpibench-r0 python g0_resume_diagnosis/run_controls.py'}
    save(raw / 'RUN_STARTED.json', report)
    with (folder / 'runtime.log').open('x', encoding='utf-8') as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            try:
                execute(folder, raw, report)
            except Exception as exc:
                report.update(status='FAILED', error_type=type(exc).__name__, error_message=str(exc), traceback=traceback.format_exc(limit=15))
                print(report['traceback'])
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    save(folder / 'g0_controls.json', report)
    with (folder / 'REPORT.md').open('x', encoding='utf-8', newline='\n') as f:
        f.write(f"# G0-5090-002 frozen controls\n\nInput commit: `{report['input_commit']}`\n\nRun ID: `{run_id}`\n\nStatus: `{report['status']}`\n\n"
                f"Completed frozen queries: {report['new_forward_queries_completed']}/26\n\nFull raw: `{raw}`\n\n"
                'Four sources, two fixed payloads, constructed mechanism controls; not26 independent documents or a performance test. '
                'Raw LM logits are unprocessed next-token values, not injection probabilities. Original detect/query unchanged. '
                'No threshold fit, training, algorithm development, R2 overwrite or subsequent tasks. Coordinator review required.\n')
    names = [p.relative_to(ROOT).as_posix() for p in sorted(folder.iterdir()) if p.is_file()]
    require(all((ROOT / p).stat().st_size <= 1024**2 for p in names), 'Large return; preserve raw and stop automatic publication')
    with (folder / 'PUBLISH_FILES.txt').open('x', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(names)+'\n')
    print(json.dumps({'status': report['status'], 'run_id': run_id, 'return_path': (folder/'g0_controls.json').relative_to(ROOT).as_posix()}))
    return 2 if report['status'] == 'FAILED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
