"""R0-5090-012: fixed real-sample debug pilot, with isolated GPU stages.

No ASR, formal mode, checkpoint comparison, retries or parameter selection.
"""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import importlib
import json
import logging
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repro.archive import json_bytes
from repro.hardware import gpu_gate
from repro.locator_trace import LocatorTrace, safe_value
from repro.scoring import evaluate_response
from scripts.aux_runtime_probe import prepared_source, versions, EXPECTED, ADAPTER_DIRS, file_sha, read_json
from scripts.local_model_probe import local_spec
from scripts.remote_preflight import run

PREPARED = 'coordination/returns/20261018T024846Z-aux-runtime-prepare-f576e035/aux_runtime.json'
ADAPTER_RECEIPTS = [
    'coordination/returns/20261018T030940Z-aux-runtime-adapter-large-6d20db5a/aux_runtime.json',
    'coordination/returns/20261018T031132Z-aux-runtime-adapter-small-6be8f67c/aux_runtime.json',
    'coordination/returns/20261018T031318Z-aux-runtime-adapter-oracle-a59f5a5b/aux_runtime.json',
]


def write_new(path, data):
    with Path(path).open('xb') as stream:
        stream.write(json_bytes(safe_value(data)))


def git_head():
    result = run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'])
    if result['returncode']:
        raise RuntimeError('Cannot determine input Git commit')
    return result['stdout'].strip()


def benchmark_module(root):
    lock = read_json(root / 'configs/upstream_lock.json')
    for name, spec in lock['repositories'].items():
        checkout = root / 'upstream' / name
        head = run(['git', '-C', str(checkout), 'rev-parse', 'HEAD'])
        dirty = run(['git', '-C', str(checkout), 'status', '--porcelain', '--untracked-files=no'])
        if head.get('stdout', '').strip() != spec['commit'] or dirty['returncode'] or dirty['stdout'].strip():
            raise RuntimeError('Pinned upstream missing or changed: ' + name)
    sys.path.insert(0, str(root / 'upstream/LongPIBench'))
    module = importlib.import_module('longpibench.benchmark')
    if not Path(module.__file__).resolve().is_relative_to((root / 'upstream/LongPIBench').resolve()):
        raise RuntimeError('Wrong LongPIBench module imported')
    module.DATA_ROOT = root / 'data' / lock['dataset']['revision']
    return module


def build_inputs(root, benchmark):
    archived = [json.loads(line) for line in (root / 'audit/prepared_inputs.jsonl').read_text(encoding='utf-8').splitlines()]
    cases = []
    for suite, goal, position, folder in [('email', '0', 'last', 'emails'), ('resume', '2', 'footnote', 'person_info')]:
        for attack in ['no', 'authority_spoof']:
            row = next(r for r in archived if r['suite'] == suite and r['item_id'] == 0 and r['attack'] == attack)
            actual = benchmark.prepare_example(suite, 0, attack, goal, position).to_dict()
            if any(actual[k] != row[k] for k in actual):
                raise ValueError('Official construction differs from archived fixed input')
            source = benchmark.DATA_ROOT / folder / '0.json'
            if file_sha(source) != row['source_sha256']:
                raise ValueError('Dataset sample hash differs from original audit')
            actual.update(case_id=suite + '-000-' + attack, dataset_revision=row['dataset_revision'],
                          source_sha256=row['source_sha256'], payload=row.get('payload'),
                          inserted_span_chars=row.get('inserted_span_chars'))
            cases.append(actual)
    return cases


def make_plan(report, raw):
    benchmark = benchmark_module(ROOT)
    inputs = build_inputs(ROOT, benchmark)
    prepared, source, _, destination = prepared_source(ROOT / PREPARED, report)
    receipts = {}
    for relative in ADAPTER_RECEIPTS:
        row = read_json(ROOT / relative)
        if row['status'] != 'ADAPTER_LOAD_AND_SYNTHETIC_QUERY_PASSED' or not row['adapter_loaded_verified']:
            raise RuntimeError('011 adapter receipt missing or not passed')
        receipts[relative] = file_sha(ROOT / relative)
    specs = {role: local_spec(ROOT, role) for role in ['target', 'helper', 'detector_base']}
    write_new(raw / 'inputs.json', inputs)
    plan = {'task_id': 'R0-5090-012', 'git_head': git_head(), 'run_kind': 'debug',
            'fixed_ids': [0], 'benchmark_cases': 4, 'target_conditions': ['no_defense', 'promptlocate'],
            'formal_checkpoint_selected': False, 'formal_datasentinel_checkpoint': 'unknown',
            'debug_whole_adapter': 'large', 'debug_adapter_reason': 'Predetermined engineering path, no quality comparison',
            'prepared_receipt': PREPARED, 'prepared_receipt_sha256': file_sha(ROOT / PREPARED),
            'adapter_receipts_sha256': receipts,
            'adapter_paths': {key: str(destination / relative) for key, relative in ADAPTER_DIRS.items()},
            'adapter_files_sha256': {str(destination / f['member']): f['sha256_first_observed']
                                    for row in source['results'] for f in row.get('files', [])},
            'model_specs': specs, 'target_max_new_tokens': 512, 'target_do_sample': False,
            'target_tokenization_add_special_tokens': False, 'target_dtype': 'bfloat16',
            'locator_sep_thres': 0.0, 'seed': 42, 'trace_call_budget': 1024, 'trace_seconds_budget': 1200,
            'inputs_path': str(raw / 'inputs.json'), 'inputs_sha256': file_sha(raw / 'inputs.json'),
            'scope': 'Real benchmark debug inputs; no ASR, no formal 20000-token or long-context acceptance',
            'differences_from_public_release': ['Explicit debug 512-token budget instead of formal 20000',
                'Target rendered chat tokenized without duplicated BOS',
                'Debug trace budgets and surfaced errors/nonfinite helpers stop downstream target for that case',
                'Sequential model stages; whole large used only for predetermined engineering debug'],
            'prepared_inputs_audit_sha256': file_sha(ROOT / 'audit/prepared_inputs.jsonl')}
    write_new(raw / 'plan.json', plan)
    report.update(plan_path=str(raw / 'plan.json'), plan_sha256=file_sha(raw / 'plan.json'), benchmark_samples_used=True,
                  case_ids=[c['case_id'] for c in inputs], status='DEBUG_PLAN_CREATED')


def load_plan(path, report):
    path = path.resolve(strict=True)
    if not path.is_relative_to((ROOT / 'runs').resolve()):
        raise ValueError('Plan must be inside runs')
    plan = read_json(path)
    if (plan['task_id'] != 'R0-5090-012' or plan['git_head'] != git_head() or plan['run_kind'] != 'debug'
            or plan['fixed_ids'] != [0] or plan['target_max_new_tokens'] != 512
            or plan['formal_checkpoint_selected'] is not False or plan['debug_whole_adapter'] != 'large'):
        raise ValueError('Plan fingerprint or fixed debug scope differs')
    if file_sha(ROOT / PREPARED) != plan['prepared_receipt_sha256']:
        raise ValueError('Prepare receipt changed')
    for relative, sha in plan['adapter_receipts_sha256'].items():
        if file_sha(ROOT / relative) != sha:
            raise ValueError('011 adapter receipt changed')
    inputs_path = Path(plan['inputs_path']).resolve(strict=True)
    if inputs_path.parent != path.parent or file_sha(inputs_path) != plan['inputs_sha256']:
        raise ValueError('Plan inputs changed or outside plan directory')
    inputs = read_json(inputs_path)
    if len(inputs) != 4 or {c['case_id'] for c in inputs} != {
            'email-000-no', 'email-000-authority_spoof', 'resume-000-no', 'resume-000-authority_spoof'}:
        raise ValueError('Unexpected debug sample set')
    for role, expected_spec in plan['model_specs'].items():
        if local_spec(ROOT, role) != expected_spec:
            raise ValueError('Local fixed model source changed since plan creation')
    report.update(plan_path=str(path), plan_sha256=file_sha(path))
    return plan, inputs


def assert_cuda_model(model):
    if any(p.device.type != 'cuda' for p in model.parameters()):
        raise RuntimeError('CPU offload or non-CUDA parameters detected')


def runtime_memory(minimum_gib):
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable')
    props = torch.cuda.get_device_properties(0)
    free, total = torch.cuda.mem_get_info()
    if '5090' not in props.name or total < 30000 * 1024**2 or free < minimum_gib * 1024**3:
        raise RuntimeError('Wrong CUDA GPU or insufficient free memory; do not evict other jobs')
    torch.cuda.reset_peak_memory_stats()
    torch.manual_seed(42)
    return {'device': props.name, 'free_before_bytes': free, 'total_bytes': total}


def write_case(raw, record):
    path = raw / (record['case_id'] + '.json')
    write_new(path, record)
    target = record.get('target')
    compact_target = ({k: target[k] for k in ['input_token_count', 'output_token_count', 'stop_reason',
                        'seconds', 'peak_allocated_bytes', 'peak_reserved_bytes', 'generation_overrides',
                        'chat_template_sha256'] if k in target} if target else None)
    return {'case_id': record['case_id'], 'validity': record['validity'], 'evidence_path': str(path),
            'evidence_sha256': file_sha(path), 'error_stage': record.get('error_stage'),
            'detector_flag': record.get('detector_flag'), 'evaluation': record.get('evaluation'),
            'raw_response': record.get('raw_response'), 'target': compact_target,
            'trace_counts': record.get('trace_counts'), 'cleaned_sha256': record.get('cleaned_sha256')}


def run_defense(plan, inputs, report, raw):
    from repro.opi_loader import load_opi_core
    report['cuda'] = runtime_memory(20)
    core = load_opi_core()
    report['opi_provenance'] = core.provenance
    for path, sha in plan['adapter_files_sha256'].items():
        if any(Path(path).parent == Path(plan['adapter_paths'][role]) for role in ['large', 'oracle']):
            if file_sha(path) != sha:
                raise ValueError('Adapter member changed since accepted 007/010/011 evidence')
    template = read_json(ROOT / 'upstream/Open-Prompt-Injection/configs/model_configs/mistral_config.json')
    template['model_info']['name'] = plan['model_specs']['detector_base']['resolved_path']
    template['params'].update(gpus=['0'], device='cuda', seed=42)
    whole_config = json.loads(json.dumps(template))
    oracle_config = json.loads(json.dumps(template))
    whole_config['params']['ft_path'] = plan['adapter_paths']['large']
    oracle_config['params']['ft_path'] = plan['adapter_paths']['oracle']
    report.update(stage='full_promptlocate_constructor', whole_config=whole_config, oracle_config=oracle_config)
    whole = core.DataSentinelDetector(whole_config)
    locator = core.PromptLocate(oracle_config, helper_model_name=plan['model_specs']['helper']['resolved_path'], sep_thres=0.0)
    for model in [whole.model.ft_model, locator.bd.model.ft_model, locator.helper_model]:
        assert_cuda_model(model)
    report['full_promptlocate_constructor_verified'] = True
    report['defense_generation_configs'] = {'whole': whole.model.ft_model.generation_config.to_dict(),
                                            'oracle': locator.bd.model.ft_model.generation_config.to_dict()}
    report['helper_runtime'] = {'embedding_dtype': str(locator.helper_model.get_input_embeddings().weight.dtype),
                               'attention_implementation': getattr(locator.helper_model.config, '_attn_implementation', None)}
    module = importlib.import_module(core.PromptLocate.__module__)
    observer = LocatorTrace(module, max_calls=plan['trace_call_budget'], max_seconds=plan['trace_seconds_budget'])
    observer.install(whole, locator)
    outputs = []
    try:
        for case in inputs:
            observer.reset()
            record = {'case_id': case['case_id'], 'input': case, 'validity': 'VALID_DEBUG_PATH',
                      'condition': 'promptlocate', 'detector_flag': None, 'cleaned_input': case['data_prompt'],
                      'localized_text': None, 'original_removed_segment_spans': None}
            started = time.monotonic()
            try:
                record['error_stage'] = 'detection'
                flag = whole.detect(case['data_prompt'])
                if type(flag) not in (int, bool) or flag not in (0, 1):
                    raise ValueError('Detector did not return binary 0/1')
                record['detector_flag'] = int(flag)
                if flag:
                    record['error_stage'] = 'localization'
                    recovered, localized = locator.locate_and_recover(case['data_prompt'], case['system_prompt'])
                    record.update(cleaned_input=recovered, localized_text=localized)
                    if observer.errors or observer.nonfinite:
                        raise RuntimeError('Locator error or non-finite helper; debug downstream stopped')
                    mapping = observer.segment_mapping
                    intervals = [e['intervals_and_query_count'][0] for e in observer.events
                                 if e['function'] == 'binary_search_injection' and 'intervals_and_query_count' in e]
                    if mapping and mapping['spans'] is not None and intervals:
                        bounds = intervals[-1]
                        if all(type(start) is int and type(end) is int and 0 <= start < end <= len(mapping['spans'])
                               for start, end in bounds):
                            record['original_removed_segment_spans'] = [mapping['spans'][start:end] for start, end in bounds]
                        else:
                            record['interval_mapping_status'] = 'UNKNOWN_INVALID_ORIGINAL_INTERVALS'
                record['error_stage'] = None
            except Exception as exc:
                record.update(validity='F6_DEBUG', error_type=type(exc).__name__, error_message=str(exc),
                              traceback=traceback.format_exc(limit=10))
                # CUDA failures invalidate the process, not just one case.
                if 'out of memory' in str(exc).lower() or 'cuda error' in str(exc).lower():
                    record['trace'] = observer.record()
                    outputs.append(write_case(raw, record))
                    raise
            record.update(seconds=time.monotonic()-started, trace=observer.record(),
                          trace_counts={'calls': observer.calls, 'events': len(observer.events),
                                        'logged_errors': len(observer.errors), 'nonfinite_helper': observer.nonfinite},
                          cleaned_sha256=hashlib.sha256(record['cleaned_input'].encode()).hexdigest())
            outputs.append(write_case(raw, record))
    finally:
        observer.close()
        report['cases'] = outputs
    report.update(stage='complete', status='DEBUG_DEFENSE_RECORDED',
                  case_error_count=sum(c['validity'] == 'F6_DEBUG' for c in outputs))
    import torch
    report['cuda'].update(peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                          peak_reserved_bytes=torch.cuda.max_memory_reserved())


def target_stage(plan, inputs, report, raw, condition, defense_report=None):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    benchmark = benchmark_module(ROOT)
    report['cuda'] = runtime_memory(20)
    spec = plan['model_specs']['target']
    local = {'local_files_only': True, 'trust_remote_code': False, 'token': False}
    tokenizer = AutoTokenizer.from_pretrained(spec['resolved_path'], **local)
    model = AutoModelForCausalLM.from_pretrained(spec['resolved_path'], **local, use_safetensors=True,
             torch_dtype=torch.bfloat16, device_map={'': 0}, low_cpu_mem_usage=True).eval()
    assert_cuda_model(model)
    if model.get_input_embeddings().weight.dtype != torch.bfloat16:
        raise RuntimeError('Target is not BF16')
    report.update(generation_config=model.generation_config.to_dict(), embedding_dtype=str(model.get_input_embeddings().weight.dtype))
    cleaned = {}
    if condition == 'promptlocate':
        defense = read_json(defense_report)
        if defense['plan_sha256'] != report['plan_sha256'] or defense['status'] != 'DEBUG_DEFENSE_RECORDED':
            raise ValueError('Defense stage does not match this plan')
        report['defense_receipt_sha256'] = file_sha(defense_report)
        for row in defense['cases']:
            if file_sha(row['evidence_path']) != row['evidence_sha256']:
                raise ValueError('Defense raw evidence changed')
            cleaned[row['case_id']] = read_json(row['evidence_path'])
    report['cases'] = []
    for case in inputs:
        record = {'case_id': case['case_id'], 'input': case, 'condition': condition, 'validity': 'NOT_RUN',
                  'raw_response': None, 'evaluation': None}
        data = case['data_prompt']
        if condition == 'promptlocate':
            earlier = cleaned[case['case_id']]
            if earlier['validity'] != 'VALID_DEBUG_PATH':
                record.update(validity='F6_DEBUG', error_stage='upstream_defense',
                              error_message='Debug target skipped after recorded defense error')
                report['cases'].append(write_case(raw, record))
                continue
            data = earlier['cleaned_input']
        messages = [{'role': 'system', 'content': case['system_prompt']}, {'role': 'user', 'content': data}]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        batch = tokenizer(prompt, return_tensors='pt', add_special_tokens=False).to('cuda')
        ids = batch['input_ids'][0].tolist()
        if ids != tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True):
            raise RuntimeError('Actual target tokens differ from direct chat template')
        if len(ids) + 512 > model.config.max_position_embeddings:
            raise RuntimeError('Target input plus debug budget exceeds model context; no truncation permitted')
        record['target'] = {'messages': messages, 'rendered_prompt': prompt, 'input_token_ids': ids,
            'input_token_count': len(ids), 'chat_template_sha256': hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
            'generation_overrides': {'max_new_tokens': 512, 'do_sample': False, 'pad_token_id': tokenizer.eos_token_id}}
        torch.cuda.reset_peak_memory_stats()
        started = time.monotonic()
        try:
            with torch.inference_mode():
                output = model.generate(**batch, **record['target']['generation_overrides'])
            torch.cuda.synchronize()
            generated = output[0, len(ids):].tolist()
            eos = model.generation_config.eos_token_id
            eos = eos if isinstance(eos, list) else [eos]
            stop = 'EOS' if generated and generated[-1] in eos else ('DEBUG_TOKEN_LIMIT' if len(generated) >= 512 else 'OTHER_STOP')
            # Keep the large exact target prompt/tokens in immutable local raw
            # evidence; the Git receipt holds only counts, hashes and response.
            record['target'].update(generated_token_ids=generated, output_token_count=len(generated), stop_reason=stop,
                                    seconds=time.monotonic()-started,
                                    peak_allocated_bytes=torch.cuda.max_memory_allocated(), peak_reserved_bytes=torch.cuda.max_memory_reserved())
            record['raw_response'] = tokenizer.decode(generated, skip_special_tokens=True).strip()
            record['evaluation'] = evaluate_response(case['suite'], case['goal'], record['raw_response'],
                                       parse=benchmark.parse_json_response, score=benchmark.score_response)
            record['validity'] = record['evaluation']['validity']
            if record['validity'] == 'F6':
                record['error_stage'] = 'evaluation'
            if stop == 'DEBUG_TOKEN_LIMIT':
                record.update(validity='DEBUG_BUDGET_CENSORED', error_stage='target_debug_token_budget')
        except Exception as exc:
            record.update(validity='F6_DEBUG', error_stage='target', error_type=type(exc).__name__,
                          error_message=str(exc), traceback=traceback.format_exc(limit=10))
            report['cases'].append(write_case(raw, record))
            raise
        report['cases'].append(write_case(raw, record))
    report.update(stage='complete', status='DEBUG_TARGET_RECORDED')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['all', 'plan', 'target-no-defense', 'defense', 'target-protected'], default='all')
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--defense-report', type=Path)
    args = parser.parse_args()
    if args.stage not in {'all', 'plan'} and args.plan is None:
        parser.error('--plan required')
    if args.stage == 'target-protected' and args.defense_report is None:
        parser.error('--defense-report required')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-debug-pilot-' + args.stage + '-' + uuid.uuid4().hex[:8]
    folder = ROOT / 'coordination/returns' / run_id
    raw = ROOT / 'runs' / run_id
    folder.mkdir(parents=True, exist_ok=False)
    raw.mkdir(parents=True, exist_ok=False)
    report = {'task_id': 'R0-5090-012', 'run_id': run_id, 'operation': args.stage, 'run_kind': 'debug',
              'git_head': git_head(), 'hostname': platform.node(), 'platform': platform.system(),
              'formal_inference_executed': False, 'benchmark_samples_used': False, 'asr_computed': False,
              'formal_checkpoint_selected': False, 'status': 'NOT_STARTED', 'stage': 'host_gate', 'raw_dir': str(raw),
              'formal_readiness': False, 'missing_formal_features': ['Formal checkpoint/config freeze',
                  'Full 20000-token generation budget', 'Per-token cosine scores and full semantic span review',
                  'Complete population run and paired validity accounting']}
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_IMPLICIT_TOKEN='1', CUDA_VISIBLE_DEVICES='0')
    try:
        with (folder / 'runtime.log').open('x', encoding='utf-8') as log:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                if platform.node().casefold() != 'desktop-b5pnbnc' or platform.system() != 'Linux':
                    raise RuntimeError('Must run on actual 5090 WSL host')
                inventory = run(['/usr/lib/wsl/lib/nvidia-smi', '--query-gpu=name,memory.total,memory.free,driver_version', '--format=csv'])
                report['hardware_gate'] = gpu_gate(inventory, 'RTX 5090', 30000)
                report['packages'] = versions()
                if not report['hardware_gate']['passed'] or report['packages'] != EXPECTED:
                    raise RuntimeError('Hardware or accepted runtime versions differ')
                if args.stage in {'plan', 'all'}:
                    make_plan(report, raw)
                    if args.stage == 'all':
                        plan_path = report['plan_path']
                        report['children'] = []
                        defense_path = None
                        for stage in ['target-no-defense', 'defense', 'target-protected']:
                            command = [sys.executable, str(Path(__file__).resolve()), '--stage', stage, '--plan', plan_path]
                            if stage == 'target-protected':
                                command += ['--defense-report', defense_path]
                            result = subprocess.run(command, capture_output=True, text=True)
                            log.write(result.stderr)
                            log.write(result.stdout)
                            child = {'stage': stage, 'command': command, 'exit_code': result.returncode}
                            report['children'].append(child)
                            summary = json.loads(result.stdout)
                            child.update(summary)
                            if result.returncode:
                                raise RuntimeError('Child stage failed: ' + stage)
                            if stage == 'defense':
                                defense_path = str(ROOT / summary['return_path'])
                        report.update(status='DEBUG_PILOT_EXECUTED_REVIEW_REQUIRED', stage='complete')
                else:
                    plan, inputs = load_plan(args.plan, report)
                    benchmark_module(ROOT)
                    report['benchmark_samples_used'] = True
                    report['stage'] = args.stage
                    if args.stage == 'defense':
                        run_defense(plan, inputs, report, raw)
                    else:
                        target_stage(plan, inputs, report, raw,
                                     'no_defense' if args.stage == 'target-no-defense' else 'promptlocate', args.defense_report)
    except Exception as exc:
        report.update(status='FAILED', error_type=type(exc).__name__, error_message=str(exc), traceback=traceback.format_exc(limit=12))
    output = folder / 'pilot_stage.json'
    write_new(output, report)
    print(json.dumps({'return_path': output.relative_to(ROOT).as_posix(), 'status': report['status'], 'stage': report['stage']}))
    return 2 if report['status'] == 'FAILED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
