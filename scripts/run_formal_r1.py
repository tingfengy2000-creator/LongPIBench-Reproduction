"""R1-5090-001: frozen full 400-input no-defense public-snapshot condition."""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repro.archive import json_bytes
from repro.scoring import evaluate_response
from repro.target_runtime import FixedLocalTarget
from scripts import run_debug_pilot as pilot

CONFIG_PATH = 'configs/formal_r1_v1.json'
FROZEN_CONFIG_SHA256 = 'efe2a0665ba627cf9a72b5d465690a3fc6fd62b8922cf3ed7fd902d871bf15b1'


def load_config(root):
    config = pilot.read_json(root / CONFIG_PATH)
    if hashlib.sha256(json_bytes(config)).hexdigest() != FROZEN_CONFIG_SHA256:
        raise ValueError('Frozen R1 v1 configuration changed; requires a separate declared version')
    lock = pilot.read_json(root / 'configs/upstream_lock.json')
    fixed = lock['model_snapshots_observed_at_audit']['target']
    if any(config['target'][k] != fixed[k] for k in ['repo_id', 'revision']) or config['dataset_revision'] != lock['dataset']['revision']:
        raise ValueError('Frozen R1 model/data differs from upstream lock')
    return config


def build_inputs(root, benchmark, config):
    archived = [json.loads(line) for line in (root / 'audit/prepared_inputs.jsonl').read_text(encoding='utf-8').splitlines()]
    index = {(r['suite'], r['item_id'], r['attack']): r for r in archived}
    if len(archived) != 400 or len(index) != 400:
        raise ValueError('Expected 400 unique archived inputs')
    sources, cases = {}, []
    for attack in config['attack_order']:
        for suite in config['suite_order']:
            setting = config['suites'][suite]
            folder = 'emails' if suite == 'email' else 'person_info'
            for item_id in range(config['ids']['start'], config['ids']['end_exclusive']):
                row = index[(suite, item_id, attack)]
                actual = benchmark.prepare_example(suite, item_id, attack, setting['goal'], setting['position']).to_dict()
                if any(actual[k] != row[k] for k in actual) or row['dataset_revision'] != config['dataset_revision']:
                    raise ValueError('Official input construction differs from fixed archive')
                source = benchmark.DATA_ROOT / folder / (str(item_id) + '.json')
                if source not in sources:
                    sources[source] = pilot.file_sha(source)
                if sources[source] != row['source_sha256']:
                    raise ValueError('Source dataset differs from original audit')
                actual.update(case_id=f'{suite}-{item_id:03d}-{attack}', dataset_revision=row['dataset_revision'],
                    source_sha256=row['source_sha256'], payload=row.get('payload'), inserted_span_chars=row.get('inserted_span_chars'))
                cases.append(actual)
    if len(cases) != config['planned_cases'] or len(sources) != 200:
        raise ValueError('Formal population is incomplete')
    return cases


def add_count(counts, case, record):
    key = case['suite'] + ':' + case['attack']
    row = counts.setdefault(key, {'planned': 100, 'attempted': 0, 'evaluable': 0, 'official_true_evaluable': 0,
        'official_false_evaluable': 0, 'invalid_or_censored': 0, 'review_required': 0,
        'token_limit': 0, 'parse_error_official_false': 0})
    row['attempted'] += 1
    evaluation = record.get('evaluation') or {}
    evaluable = record['validity'] in {'VALID', 'REVIEW_REQUIRED'}
    if evaluable:
        row['evaluable'] += 1
        row['official_true_evaluable' if evaluation['official_success'] else 'official_false_evaluable'] += 1
    else:
        row['invalid_or_censored'] += 1
    row['review_required'] += bool(evaluation.get('review_required'))
    row['token_limit'] += (record.get('target') or {}).get('stop_reason') == 'TOKEN_LIMIT'
    row['parse_error_official_false'] += 'JSON_PARSE_ERROR' in evaluation.get('issues', [])


def execute_cases(cases, target, benchmark, config, report, raw):
    report.update(counts={}, case_evidence=[], stage='formal_inference')
    for case in cases:
        record = {'run_id': report['run_id'], 'run_kind': 'formal', 'stage': 'R1', 'condition': 'no_defense',
            'study_condition': config['study_condition'], 'frozen_config_sha256': FROZEN_CONFIG_SHA256,
            'case_id': case['case_id'], 'input': case, 'validity': 'NOT_RUN', 'target': None, 'evaluation': None}
        error = None
        try:
            report['formal_inference_attempted'] = True
            record['target'] = target.generate(case['system_prompt'], case['data_prompt'])
            report['formal_inference_executed'] = True
            record['evaluation'] = evaluate_response(case['suite'], case['goal'], record['target']['raw_response'],
                parse=benchmark.parse_json_response, score=benchmark.score_response)
            record['validity'] = record['evaluation']['validity']
            if record['target']['stop_reason'] != 'EOS':
                record['validity'] = 'CENSORED_TOKEN_LIMIT' if record['target']['stop_reason'] == 'TOKEN_LIMIT' else 'UNKNOWN_STOP_REVIEW_REQUIRED'
        except Exception as exc:
            error = exc
            record['target'] = getattr(target, 'last_attempt', None)
            record.update(validity='F6', error_type=type(exc).__name__, error_message=str(exc), traceback=traceback.format_exc(limit=12))
        path = raw / (case['case_id'] + '.json')
        pilot.write_new(path, record)
        report['case_evidence'].append({'case_id': case['case_id'], 'validity': record['validity'],
            'path': str(path), 'sha256': pilot.file_sha(path), 'bytes': path.stat().st_size})
        add_count(report['counts'], case, record)
        if len(report['case_evidence']) % 25 == 0:
            print(json.dumps({'recorded_cases': len(report['case_evidence']), 'planned_cases': len(cases),
                              'last_case': case['case_id'], 'validity': record['validity']}), flush=True)
        # No runtime retries or silent fallbacks. Parsing/schema F6 remains an
        # explicit recorded model outcome; inference exceptions stop the process.
        if error is not None:
            raise error
    report.update(stage='complete', status='FORMAL_R1_EXECUTED_REVIEW_REQUIRED', attempted=len(cases))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-formal-r1-' + uuid.uuid4().hex[:8]
    folder, raw = ROOT / 'coordination/returns' / run_id, ROOT / 'runs' / run_id
    folder.mkdir(parents=True, exist_ok=False)
    raw.mkdir(parents=True, exist_ok=False)
    report = {'task_id': 'R1-5090-001', 'run_id': run_id, 'run_kind': 'formal', 'stage': 'host_gate',
        'git_head': pilot.git_head(), 'hostname': platform.node(), 'platform': platform.system(),
        'formal_inference_executed': False, 'formal_inference_attempted': False, 'strict_paper_configuration_recovered': False,
        'asr_computed': False, 'status': 'NOT_STARTED', 'raw_dir': str(raw), 'retries': 0,
        'debug_records_reused_as_formal': False, 'r2_checkpoint_selected': False}
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_IMPLICIT_TOKEN='1', CUDA_VISIBLE_DEVICES='0')
    try:
        with (folder / 'runtime.log').open('x', encoding='utf-8') as log:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                if platform.node().casefold() != 'desktop-b5pnbnc' or platform.system() != 'Linux':
                    raise RuntimeError('Must run on actual 5090 WSL host')
                config = load_config(ROOT)
                report.update(frozen_config_sha256=FROZEN_CONFIG_SHA256, frozen_config=config,
                              config_source_file_sha256=pilot.file_sha(ROOT / CONFIG_PATH))
                expected = {}
                for line in (ROOT / 'requirements/r0-compat-candidate.txt').read_text(encoding='utf-8').splitlines():
                    if line.strip() and not line.startswith('#'):
                        name, version = line.strip().split('==')
                        expected[name] = version
                actual = {name: importlib.metadata.version(name) for name in expected}
                report['runtime_versions'] = actual
                if actual != expected:
                    raise RuntimeError('Runtime differs from frozen compatibility candidate')
                benchmark = pilot.benchmark_module(ROOT)
                cases = build_inputs(ROOT, benchmark, config)
                pilot.write_new(raw / 'inputs.json', cases)
                report['input_set_sha256'] = pilot.file_sha(raw / 'inputs.json')
                if (report['input_set_sha256'] != config['input_freeze']['canonical_input_set_sha256'] or
                        pilot.file_sha(ROOT / 'audit/prepared_inputs.jsonl') != config['input_freeze']['prepared_archive_sha256']):
                    raise ValueError('Full formal input set differs from frozen pre-execution fingerprint')
                report['cuda'] = pilot.runtime_memory(20)
                spec = pilot.local_spec(ROOT, 'target')
                target = FixedLocalTarget(spec, config)
                report['target_runtime'] = target.metadata
                manifest = {'task_id': report['task_id'], 'run_id': run_id, 'run_kind': 'formal',
                    'git_head': report['git_head'], 'frozen_config_sha256': FROZEN_CONFIG_SHA256,
                    'config': config, 'input_set_sha256': report['input_set_sha256'],
                    'runtime_versions': actual, 'target_runtime': target.metadata,
                    'tokenization_patch_sha256': pilot.file_sha(ROOT / 'patches/target_chat_tokenization.diff'),
                    'requirement_candidate_sha256': pilot.file_sha(ROOT / 'requirements/r0-compat-candidate.txt')}
                pilot.write_new(raw / 'manifest.json', manifest)
                report['manifest_sha256'] = pilot.file_sha(raw / 'manifest.json')
                execute_cases(cases, target, benchmark, config, report, raw)
    except Exception as exc:
        report.update(status='FAILED', error_type=type(exc).__name__, error_message=str(exc), traceback=traceback.format_exc(limit=12))
    output = folder / 'r1_run.json'
    pilot.write_new(output, report)
    print(json.dumps({'return_path': output.relative_to(ROOT).as_posix(), 'status': report['status'],
                      'recorded_cases': len(report.get('case_evidence', []))}))
    return 2 if report['status'] == 'FAILED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
