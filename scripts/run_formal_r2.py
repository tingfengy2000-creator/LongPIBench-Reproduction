"""Frozen R2: audit existing R1, then isolated defense and protected target stages."""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repro.archive import json_bytes
from repro.locator_trace import LocatorTrace
from repro.scoring import evaluate_response
from repro.target_runtime import FixedLocalTarget
from scripts import run_formal_r1 as r1
from scripts import audit_formal_r1 as r1audit
from scripts import run_debug_pilot as pilot

CONFIG = 'configs/formal_r2_v1.json'
CONFIG_SHA = '5d12649f82f7fde7f45b8f1c7ba9adf7b3366163423e8ffc1e3ab428adcec568'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_config(root):
    config = pilot.read_json(root / CONFIG)
    require(hashlib.sha256(json_bytes(config)).hexdigest() == CONFIG_SHA, 'Frozen R2 configuration changed')
    target = r1.load_config(root)
    require(config['target_condition_canonical_sha256'] == r1.FROZEN_CONFIG_SHA256, 'R1 target condition differs')
    require(config['population'] == {k: target[k] for k in config['population']}, 'R2 population differs from R1')
    for key in ['checkpoint_selection', 'r1_receipt']:
        require(pilot.file_sha(root / config[key]) == config[key + '_sha256'], 'Frozen source changed: ' + key)
    selection = pilot.read_json(root / config['checkpoint_selection'])
    require(selection['whole_detector']['relative_path'] == config['whole_detector']
            and selection['oracle']['relative_path'] == config['oracle']
            and selection['status'] == 'OWNER_CONFIRMED_PRIMARY_CHECKPOINT'
            and selection['switch_checkpoint_based_on_asr_allowed'] is False, 'Owner checkpoint decision differs')
    return config, target


def check_runtime(config):
    require(platform.system() == 'Linux' and platform.node().casefold() == 'desktop-b5pnbnc', 'Use actual 5090 WSL host')
    expected = {}
    for line in (ROOT / 'requirements/r0-compat-candidate.txt').read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#'):
            name, version = line.strip().split('==')
            expected[name] = version
    require({k: importlib.metadata.version(k) for k in expected} == expected, 'Frozen package versions changed')
    require(shutil.disk_usage(ROOT / 'runs').free >= config['resource_guards']['minimum_free_disk_gib_before_stage'] * 1024**3,
            'Insufficient raw-record disk space; do not delete old evidence')
    return expected


def make_plan(config, target, report, raw, audit_path):
    audit = pilot.read_json(audit_path)
    require(audit['status'] == 'R1_RAW_VERIFIED_WITH_SEPARATE_INVALID_OUTCOMES'
            and audit['verified_raw_count'] == 400
            and audit['source_receipt_sha256'] == config['r1_receipt_sha256'], 'R1 raw audit has not passed')
    benchmark = pilot.benchmark_module(ROOT)
    cases = r1.build_inputs(ROOT, benchmark, target)
    pilot.write_new(raw / 'inputs.json', cases)
    require(pilot.file_sha(raw / 'inputs.json') == target['input_freeze']['canonical_input_set_sha256'], 'Frozen inputs differ')
    _, source, _, destination = pilot.prepared_source(ROOT / pilot.PREPARED, report)
    selection = pilot.read_json(ROOT / config['checkpoint_selection'])
    expected_files = {f['member']: f for role in ['whole_detector', 'oracle'] for f in selection[role]['files']}
    accepted_files = {f['member']: f for row in source['results'] for f in row.get('files', [])}
    require(all(accepted_files[k] == v for k, v in expected_files.items()), '007 adapter identities differ')
    receipts = {}
    for relative in [pilot.ADAPTER_RECEIPTS[0], pilot.ADAPTER_RECEIPTS[2]]:
        row = pilot.read_json(ROOT / relative)
        require(row['adapter_loaded_verified'] and row['original_query_verified'], 'Accepted adapter receipt missing')
        receipts[relative] = pilot.file_sha(ROOT / relative)
    plan = {'task_id': 'R2-5090-001', 'run_kind': 'formal', 'git_head': pilot.git_head(),
        'config': config, 'config_sha256': CONFIG_SHA, 'target_config': target,
        'inputs_path': str(raw / 'inputs.json'), 'inputs_sha256': pilot.file_sha(raw / 'inputs.json'),
        'r1_audit_path': str(audit_path), 'r1_audit_sha256': pilot.file_sha(audit_path),
        'prepared_receipt_sha256': pilot.file_sha(ROOT / pilot.PREPARED), 'adapter_receipts': receipts,
        'adapter_paths': {'large': str(destination / config['whole_detector']), 'oracle': str(destination / config['oracle'])},
        'adapter_files': {str(destination / member): row['sha256_first_observed'] for member, row in expected_files.items()},
        'model_specs': {role: pilot.local_spec(ROOT, role) for role in ['target', 'helper', 'detector_base']}}
    pilot.write_new(raw / 'plan.json', plan)
    report.update(plan_path=str(raw / 'plan.json'), plan_sha256=pilot.file_sha(raw / 'plan.json'))


def load_plan(path, report):
    path = path.resolve(strict=True)
    require(path.is_relative_to((ROOT / 'runs').resolve()), 'Plan outside runs')
    plan = pilot.read_json(path)
    config, target = load_config(ROOT)
    require(plan['git_head'] == pilot.git_head() and plan['config_sha256'] == CONFIG_SHA
            and plan['config'] == config and plan['target_config'] == target
            and plan['task_id'] == 'R2-5090-001' and plan['run_kind'] == 'formal', 'Plan condition/code changed')
    inputs_path = Path(plan['inputs_path']).resolve(strict=True)
    require(inputs_path.parent == path.parent and pilot.file_sha(inputs_path) == plan['inputs_sha256']
            == target['input_freeze']['canonical_input_set_sha256'], 'Inputs changed')
    audit_path = Path(plan['r1_audit_path']).resolve(strict=True)
    require(audit_path.is_relative_to((ROOT / 'coordination/returns').resolve())
            and pilot.file_sha(audit_path) == plan['r1_audit_sha256'], 'R1 audit changed')
    require(pilot.file_sha(ROOT / pilot.PREPARED) == plan['prepared_receipt_sha256'], 'Prepare receipt changed')
    for relative, digest in plan['adapter_receipts'].items():
        require(pilot.file_sha(ROOT / relative) == digest, 'Adapter receipt changed')
    for role, spec in plan['model_specs'].items():
        require(pilot.local_spec(ROOT, role) == spec, 'Fixed local model changed')
    cases = pilot.read_json(inputs_path)
    require(cases == r1.build_inputs(ROOT, pilot.benchmark_module(ROOT), target), 'Official input population differs')
    report.update(plan_path=str(path), plan_sha256=pilot.file_sha(path))
    return plan, cases


def persist_case(raw, report, record):
    path = raw / (record['case_id'] + '.json')
    pilot.write_new(path, record)
    summary = {k: record.get(k) for k in ['case_id', 'validity', 'detector_flag', 'error_stage', 'seconds', 'trace_counts',
                                         'cleaned_sha256', 'mapping_status']}
    spans = record.get('original_removed_segment_spans')
    summary['removed_original_segment_count'] = sum(len(group) for group in spans) if spans is not None else None
    summary.update(path=str(path), sha256=pilot.file_sha(path), bytes=path.stat().st_size)
    target, evaluation = record.get('target'), record.get('evaluation')
    if target:
        summary['target'] = {k: target.get(k) for k in ['input_token_count', 'output_token_count', 'stop_reason', 'generation_seconds']}
    if evaluation:
        summary['evaluation'] = {k: evaluation[k] for k in ['official_success', 'audit_success', 'issues', 'review_required']}
    report['cases'].append(summary)
    if len(report['cases']) % 10 == 0:
        print(json.dumps({'recorded_cases': len(report['cases']), 'planned_cases': 400,
                          'last_case': record['case_id'], 'validity': record['validity']}), flush=True)


def fatal_cuda(trace, error=None):
    messages = [str(error or '')] + [e.get('error_message', '') for e in trace['events']] + [e['message'] for e in trace['logged_errors']]
    return any(any(word in message.lower() for word in ['out of memory', 'cuda error', 'device-side assert', 'cublas', 'cudnn'])
               for message in messages)


def defense_case(case, whole, locator, observer):
    observer.reset()
    record = {'case_id': case['case_id'], 'input': case, 'run_kind': 'formal', 'stage': 'R2-defense',
        'config_sha256': CONFIG_SHA, 'validity': 'VALID_DEFENSE_PATH', 'detector_flag': None,
        'cleaned_input': case['data_prompt'], 'localized_text': None, 'original_removed_segment_spans': None,
        'mapping_status': 'NOT_CALLED', 'error_stage': 'detection'}
    started, error = time.monotonic(), None
    try:
        flag = whole.detect(case['data_prompt'])
        require(type(flag) in (int, bool) and flag in (0, 1), 'Detector must return binary 0/1')
        record['detector_flag'] = int(flag)
        if flag:
            record['error_stage'] = 'localization'
            recovered, localized = locator.locate_and_recover(case['data_prompt'], case['system_prompt'])
            require(isinstance(recovered, str) and isinstance(localized, str), 'Non-string locator output')
            record.update(cleaned_input=recovered, localized_text=localized)
            if observer.errors or observer.nonfinite or observer.boundary_nonfinite:
                raise RuntimeError('Recorded upstream error or nonfinite localization values')
            mapping = observer.segment_mapping
            record['mapping_status'] = mapping['status'] if mapping else 'UNKNOWN'
            intervals = [e['intervals_and_query_count'][0] for e in observer.events
                         if e['function'] == 'binary_search_injection' and 'intervals_and_query_count' in e]
            if mapping and mapping['spans'] is not None and intervals:
                bounds = intervals[-1]
                if all(type(a) is int and type(b) is int and 0 <= a < b <= len(mapping['spans']) for a, b in bounds):
                    record['original_removed_segment_spans'] = [mapping['spans'][a:b] for a, b in bounds]
                else:
                    record['mapping_status'] = 'UNKNOWN_INVALID_ORIGINAL_INTERVALS'
        record['error_stage'] = None
    except Exception as exc:
        error = exc
        record.update(validity='F6', error_type=type(exc).__name__, error_message=str(exc), traceback=traceback.format_exc(limit=10))
    trace = observer.record()
    if 'debug_budgets' in trace:
        trace['declared_resource_guards'] = trace.pop('debug_budgets')
    guard = any('FORMAL_RESOURCE_GUARD_EXCEEDED' in e['message'] for e in trace['logged_errors'])
    if guard:
        record['validity'] = 'CENSORED_RESOURCE'
    record.update(trace=trace, seconds=time.monotonic()-started,
        trace_counts={'calls': observer.calls, 'events': len(observer.events), 'logged_errors': len(observer.errors),
                      'nonfinite_helper': observer.nonfinite, 'nonfinite_boundary': observer.boundary_nonfinite},
        cleaned_sha256=hashlib.sha256(record['cleaned_input'].encode()).hexdigest())
    return record, fatal_cuda(trace, error)


def defense_stage(plan, cases, report, raw):
    from repro.opi_loader import load_opi_core
    report['cuda'] = pilot.runtime_memory(20)
    core = load_opi_core()
    report['opi_provenance'] = core.provenance
    for path, digest in plan['adapter_files'].items():
        require(pilot.file_sha(path) == digest, 'Adapter file changed')
    template = pilot.read_json(ROOT / 'upstream/Open-Prompt-Injection/configs/model_configs/mistral_config.json')
    template['model_info']['name'] = plan['model_specs']['detector_base']['resolved_path']
    template['params'].update(gpus=['0'], device='cuda', seed=42)
    whole_config, oracle_config = json.loads(json.dumps(template)), json.loads(json.dumps(template))
    whole_config['params']['ft_path'] = plan['adapter_paths']['large']
    oracle_config['params']['ft_path'] = plan['adapter_paths']['oracle']
    report.update(whole_config=whole_config, oracle_config=oracle_config)
    whole = core.DataSentinelDetector(whole_config)
    locator = core.PromptLocate(oracle_config, helper_model_name=plan['model_specs']['helper']['resolved_path'], sep_thres=0.0)
    for model in [whole.model.ft_model, locator.bd.model.ft_model, locator.helper_model]:
        pilot.assert_cuda_model(model)
    report.update(full_promptlocate_constructor_verified=True, defense_generation_configs={
        'whole': whole.model.ft_model.generation_config.to_dict(), 'oracle': locator.bd.model.ft_model.generation_config.to_dict()},
        helper_runtime={'embedding_dtype': str(locator.helper_model.get_input_embeddings().weight.dtype),
                        'attention_implementation': getattr(locator.helper_model.config, '_attn_implementation', None)})
    guard = plan['config']['resource_guards']
    observer = LocatorTrace(importlib.import_module(core.PromptLocate.__module__),
        max_calls=guard['max_observed_calls_per_case'], max_seconds=guard['max_seconds_per_case'],
        whole_label='whole_large_formal', budget_error='FORMAL_RESOURCE_GUARD_EXCEEDED', record_boundaries=True)
    observer.install(whole, locator)
    report['cases'] = []
    try:
        for case in cases:
            report['formal_inference_attempted'] = True
            record, fatal = defense_case(case, whole, locator, observer)
            record['run_id'] = report['run_id']
            report['formal_inference_executed'] |= any(e['function'] == 'generate' and 'generated_token_ids' in e for e in record['trace']['events'])
            persist_case(raw, report, record)
            if fatal:
                raise RuntimeError('CUDA failure in defense; preserved case, stop without retry')
    finally:
        observer.close()
    report['status'] = 'FORMAL_R2_DEFENSE_EXECUTED_REVIEW_REQUIRED'


def protected_stage(plan, cases, defense_path, report, raw):
    defense_path = defense_path.resolve(strict=True)
    require(defense_path.is_relative_to((ROOT / 'coordination/returns').resolve()), 'Defense receipt outside returns')
    defense = pilot.read_json(defense_path)
    require(defense['plan_sha256'] == report['plan_sha256']
            and defense['status'] == 'FORMAL_R2_DEFENSE_EXECUTED_REVIEW_REQUIRED'
            and [c['case_id'] for c in defense['cases']] == [c['case_id'] for c in cases], 'Defense population/plan incomplete')
    report.update(defense_receipt=str(defense_path), defense_receipt_sha256=pilot.file_sha(defense_path), cases=[], counts={})
    # Validate every raw before loading target weights; no target for invalid defense paths.
    previous = []
    defense_raw = Path(defense['raw_dir']).resolve(strict=True)
    require(defense_raw.is_relative_to((ROOT / 'runs').resolve()), 'Defense raw outside runs')
    for case, row in zip(cases, defense['cases']):
        path = Path(row['path']).resolve(strict=True)
        require(path.parent == defense_raw and path.name == case['case_id'] + '.json'
                and path.stat().st_size == row['bytes'] and pilot.file_sha(path) == row['sha256'], 'Defense raw changed')
        item = pilot.read_json(path)
        require(item['input'] == case and item['validity'] == row['validity'] and item['config_sha256'] == CONFIG_SHA, 'Defense input/validity differs')
        previous.append((path, row['sha256'], item['validity']))
    target = None
    if any(v == 'VALID_DEFENSE_PATH' for _, _, v in previous):
        report['cuda'] = pilot.runtime_memory(20)
        target = FixedLocalTarget(plan['model_specs']['target'], plan['target_config'])
        report['target_runtime'] = target.metadata
    benchmark = pilot.benchmark_module(ROOT)
    for case, (path, digest, validity) in zip(cases, previous):
        require(pilot.file_sha(path) == digest, 'Defense raw changed before use')
        prior = pilot.read_json(path)
        record = {'run_id': report['run_id'], 'case_id': case['case_id'], 'input': case, 'run_kind': 'formal',
            'stage': 'R2-protected', 'condition': 'promptlocate', 'config_sha256': CONFIG_SHA,
            'defense_raw_sha256': digest, 'detector_flag': prior['detector_flag'], 'evaluation': None, 'target': None,
            'validity': validity if validity != 'VALID_DEFENSE_PATH' else 'NOT_RUN', 'error_stage': 'upstream_defense'}
        error = None
        if validity == 'VALID_DEFENSE_PATH':
            try:
                record['error_stage'] = 'target_generation'
                report['formal_inference_attempted'] = True
                record['target'] = target.generate(case['system_prompt'], prior['cleaned_input'])
                report['formal_inference_executed'] = True
                record['evaluation'] = evaluate_response(case['suite'], case['goal'], record['target']['raw_response'],
                    parse=benchmark.parse_json_response, score=benchmark.score_response)
                record['validity'] = record['evaluation']['validity']
                if record['target']['stop_reason'] != 'EOS':
                    record['validity'] = 'CENSORED_TOKEN_LIMIT' if record['target']['stop_reason'] == 'TOKEN_LIMIT' else 'UNKNOWN_STOP_REVIEW_REQUIRED'
                record['error_stage'] = None
            except Exception as exc:
                error = exc
                record.update(validity='F6', target=getattr(target, 'last_attempt', None), error_type=type(exc).__name__,
                    error_message=str(exc), traceback=traceback.format_exc(limit=12))
        persist_case(raw, report, record)
        r1.add_count(report['counts'], case, record)
        count = report['counts'][case['suite'] + ':' + case['attack']]
        count['target_generation_attempted'] = count.get('target_generation_attempted', 0) + bool((record['target'] or {}).get('generation_attempted'))
        count['target_generation_returned'] = count.get('target_generation_returned', 0) + bool((record['target'] or {}).get('generated_token_ids'))
        if error is not None:
            raise error
    report['status'] = 'FORMAL_R2_PROTECTED_EXECUTED_REVIEW_REQUIRED'


def child(command, report, log):
    result = subprocess.run(command, capture_output=True, text=True)
    log.write(result.stdout + result.stderr)
    item = {'command': command, 'exit_code': result.returncode}
    report.setdefault('children', []).append(item)
    item.update(json.loads(result.stdout))
    require(result.returncode == 0, 'Child stopped: ' + str(item))
    return ROOT / item['return_path']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['all', 'defense', 'protected'], default='all')
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--defense-report', type=Path)
    args = parser.parse_args()
    if args.stage != 'all' and args.plan is None:
        parser.error('--plan required for a child stage')
    if args.stage == 'protected' and args.defense_report is None:
        parser.error('--defense-report required')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-formal-r2-' + args.stage + '-' + uuid.uuid4().hex[:8]
    folder, raw = ROOT / 'coordination/returns' / run_id, ROOT / 'runs' / run_id
    folder.mkdir(parents=True, exist_ok=False)
    raw.mkdir(parents=True, exist_ok=False)
    report = {'task_id': 'R2-5090-001', 'run_id': run_id, 'operation': args.stage, 'run_kind': 'formal',
        'git_head': pilot.git_head(), 'hostname': platform.node(), 'raw_dir': str(raw), 'status': 'NOT_STARTED',
        'config_sha256': CONFIG_SHA, 'formal_inference_attempted': False, 'formal_inference_executed': False,
        'asr_computed': False, 'retries': 0, 'debug_output_reused': False, 'strict_paper_configuration_recovered': False}
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_IMPLICIT_TOKEN='1', CUDA_VISIBLE_DEVICES='0')
    try:
        with (folder / 'runtime.log').open('x', encoding='utf-8') as log:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                config, target = load_config(ROOT)
                report['runtime_versions'] = check_runtime(config)
                if args.stage == 'all':
                    audit_path = child([sys.executable, str(ROOT / 'scripts/audit_formal_r1.py')], report, log)
                    make_plan(config, target, report, raw, audit_path)
                    defense_path = child([sys.executable, str(Path(__file__).resolve()), '--stage', 'defense', '--plan', report['plan_path']], report, log)
                    protected_path = child([sys.executable, str(Path(__file__).resolve()), '--stage', 'protected', '--plan', report['plan_path'],
                        '--defense-report', str(defense_path)], report, log)
                    children = [pilot.read_json(path) for path in [defense_path, protected_path]]
                    report.update(status='FORMAL_R2_EXECUTED_REVIEW_REQUIRED',
                        formal_inference_attempted=any(c['formal_inference_attempted'] for c in children),
                        formal_inference_executed=any(c['formal_inference_executed'] for c in children), counts=children[-1]['counts'])
                else:
                    plan, cases = load_plan(args.plan, report)
                    if args.stage == 'defense':
                        defense_stage(plan, cases, report, raw)
                    else:
                        protected_stage(plan, cases, args.defense_report, report, raw)
    except Exception as exc:
        report.update(status='FAILED', error_type=type(exc).__name__, error_message=str(exc), traceback=traceback.format_exc(limit=12))
        # Preserve observed child execution even if a later stage fails.
        for row in report.get('children', []):
            if row.get('return_path') and (ROOT / row['return_path']).exists():
                earlier = pilot.read_json(ROOT / row['return_path'])
                for flag in ['formal_inference_attempted', 'formal_inference_executed']:
                    report[flag] |= earlier.get(flag, False)
    output = folder / 'r2_stage.json'
    pilot.write_new(output, report)
    print(json.dumps({'return_path': output.relative_to(ROOT).as_posix(), 'status': report['status']}))
    return 2 if report['status'] == 'FAILED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
