"""R0-5090-014: separate Email-only debug condition after audited 012 censoring."""
import argparse
import contextlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import run_debug_pilot as pilot
from scripts.analyze_debug_trace import summarize_case

PARENT = 'coordination/returns/20261018T034344Z-debug-pilot-all-6f236791/pilot_stage.json'
DEFENSE = 'coordination/returns/20261018T034557Z-debug-pilot-defense-16a9eecd/pilot_stage.json'
AUDIT = 'coordination/returns/20261018T044320Z-trace-audit-65b8d1bb/trace_audit.json'


def compare_completed_prefix(old, new):
    """Compare observable logic, not timestamps or bit-level floating scores."""
    old_events, new_events = old['trace']['events'], new['trace']['events']
    keys = ['role', 'data', 'prompt', 'raw_response', 'binary_result', 'input_token_ids', 'generated_token_ids',
            'segments', 'start', 'end', 'prefix', 'result', 'condition_text', 'target_text', 'finite',
            'condition_token_count', 'full_token_count_before_crop']
    compared = 0
    for i, event in enumerate(old_events):
        if i >= len(new_events) or event['function'] != new_events[i]['function']:
            return {'logical_prefix_matches': False, 'first_difference_index': i, 'kind': 'function_sequence',
                    'compared_completed_events': compared}
        if event.get('error_type'):
            continue
        different = [key for key in keys if key in event and event[key] != new_events[i].get(key)]
        if different:
            return {'logical_prefix_matches': False, 'first_difference_index': i, 'different_fields': different,
                    'compared_completed_events': compared}
        compared += 1
    return {'logical_prefix_matches': True, 'compared_completed_events': compared,
            'old_recorded_event_count': len(old_events), 'new_recorded_event_count': len(new_events),
            'scope': 'Completed logical fields only; excludes errors, timings and floating probability/influence values'}


def create_plan(report, raw):
    parent = pilot.read_json(ROOT / PARENT)
    defense = pilot.read_json(ROOT / DEFENSE)
    audit = pilot.read_json(ROOT / AUDIT)
    if audit['status'] != 'TRACE_SUMMARIES_CREATED_NOT_RERUN' or audit['source_receipt_sha256'] != pilot.file_sha(ROOT / DEFENSE):
        raise ValueError('013 receipt does not match original defense')
    if defense['plan_sha256'] != parent['plan_sha256'] or audit['original_plan_sha256'] != parent['plan_sha256']:
        raise ValueError('012/013 parent plan references differ')
    old_path = Path(parent['plan_path']).resolve(strict=True)
    if not old_path.is_relative_to((ROOT / 'runs').resolve()) or pilot.file_sha(old_path) != parent['plan_sha256']:
        raise ValueError('Original 012 plan missing or changed')
    old = pilot.read_json(old_path)
    inputs_path = Path(old['inputs_path']).resolve(strict=True)
    if inputs_path.parent != old_path.parent or pilot.file_sha(inputs_path) != old['inputs_sha256']:
        raise ValueError('Original 012 inputs missing or changed')
    original_inputs = pilot.read_json(inputs_path)
    fixed_inputs = pilot.build_inputs(ROOT, pilot.benchmark_module(ROOT))
    if original_inputs != fixed_inputs:
        raise ValueError('Original inputs differ from fixed official constructions')
    inputs = [case for case in original_inputs if case['suite'] == 'email']
    originals = [case for case in defense['cases'] if case['case_id'].startswith('email-')]
    if len(inputs) != 2 or len(originals) != 2:
        raise ValueError('Exactly two original Email cases required')
    for row in originals:
        path = Path(row['evidence_path']).resolve(strict=True)
        if not path.is_relative_to((ROOT / 'runs').resolve()) or pilot.file_sha(path) != row['evidence_sha256']:
            raise ValueError('Original Email trace hash mismatch')
    plan = dict(old)
    pilot.write_new(raw / 'inputs.json', inputs)
    plan.update(task_id='R0-5090-014', git_head=pilot.git_head(), benchmark_cases=2,
        inputs_path=str(raw / 'inputs.json'), inputs_sha256=pilot.file_sha(raw / 'inputs.json'),
        trace_call_budget=8192, trace_seconds_budget=3600,
        parent_plan_path=str(old_path), parent_plan_sha256=parent['plan_sha256'],
        parent_receipt_sha256=pilot.file_sha(ROOT / PARENT), audit_receipt_sha256=pilot.file_sha(ROOT / AUDIT),
        source_defense_receipt_sha256=pilot.file_sha(ROOT / DEFENSE), original_email_traces=originals,
        inherited_no_defense_receipt='coordination/returns/20261018T034344Z-debug-pilot-target-no-defense-b8ca2158/pilot_stage.json',
        new_condition_reason='013 verified strictly decreasing search segments; 012 observation budget censored progress',
        restart_semantics='Fresh execution from identical original inputs, not resuming an intermediate cache',
        condition_changes={'scope': 'Only original two Email cases; no new baseline/Resume generation',
                           'trace_call_budget': [1024, 8192], 'trace_seconds_budget': [1200, 3600]},
        scope='Separate debug condition; no ASR, no checkpoint/algorithm changes; preserve 012 censored records')
    plan['inherited_no_defense_receipt_sha256'] = pilot.file_sha(ROOT / plan['inherited_no_defense_receipt'])
    pilot.write_new(raw / 'plan.json', plan)
    report.update(plan_path=str(raw / 'plan.json'), plan_sha256=pilot.file_sha(raw / 'plan.json'), status='DEBUG_EMAIL_PLAN_CREATED')


def load_plan(path, report):
    path = path.resolve(strict=True)
    if not path.is_relative_to((ROOT / 'runs').resolve()):
        raise ValueError('014 plan must be inside runs')
    plan = pilot.read_json(path)
    if (plan['task_id'] != 'R0-5090-014' or plan['git_head'] != pilot.git_head() or
            plan['trace_call_budget'] != 8192 or plan['trace_seconds_budget'] != 3600 or
            plan['target_max_new_tokens'] != 512 or plan['formal_checkpoint_selected'] is not False):
        raise ValueError('014 fixed condition or input commit changed')
    parent = pilot.read_json(plan['parent_plan_path'])
    if pilot.file_sha(plan['parent_plan_path']) != plan['parent_plan_sha256']:
        raise ValueError('Original 012 plan changed')
    allowed = {'task_id', 'git_head', 'benchmark_cases', 'inputs_path', 'inputs_sha256',
               'trace_call_budget', 'trace_seconds_budget', 'scope'}
    if any(plan.get(k) != v for k, v in parent.items() if k not in allowed):
        raise ValueError('Model/method condition differs from parent plan')
    for relative, key in [(PARENT, 'parent_receipt_sha256'), (DEFENSE, 'source_defense_receipt_sha256'), (AUDIT, 'audit_receipt_sha256')]:
        if pilot.file_sha(ROOT / relative) != plan[key]:
            raise ValueError('Original linked receipt changed')
    if pilot.file_sha(ROOT / pilot.PREPARED) != plan['prepared_receipt_sha256']:
        raise ValueError('010 prepared receipt changed')
    for relative, sha in plan['adapter_receipts_sha256'].items():
        if pilot.file_sha(ROOT / relative) != sha:
            raise ValueError('011 adapter receipt changed')
    for role, spec in plan['model_specs'].items():
        if pilot.local_spec(ROOT, role) != spec:
            raise ValueError('Fixed local model source changed')
    inputs_path = Path(plan['inputs_path']).resolve(strict=True)
    if inputs_path.parent != path.parent or pilot.file_sha(inputs_path) != plan['inputs_sha256']:
        raise ValueError('014 inputs changed')
    inputs = pilot.read_json(inputs_path)
    if {c['case_id'] for c in inputs} != {'email-000-no', 'email-000-authority_spoof'} or len(inputs) != 2:
        raise ValueError('Unexpected 014 sample set')
    report.update(plan_path=str(path), plan_sha256=pilot.file_sha(path))
    return plan, inputs


def add_defense_audit(plan, report):
    audits = []
    for case in report['cases']:
        original = next(row for row in plan['original_email_traces'] if row['case_id'] == case['case_id'])
        if pilot.file_sha(original['evidence_path']) != original['evidence_sha256']:
            raise ValueError('Original trace changed before prefix comparison')
        old = pilot.read_json(original['evidence_path'])
        current = pilot.read_json(case['evidence_path'])
        audit = summarize_case(current)
        audit['prefix_comparison'] = compare_completed_prefix(old, current)
        audits.append(audit)
    report['trace_audits'] = audits
    if not all(a['prefix_comparison']['logical_prefix_matches'] for a in audits):
        raise RuntimeError('Recorded logical prefix differs; preserve new raw and stop for coordinator review')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['all', 'defense', 'target-protected'], default='all')
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--defense-report', type=Path)
    args = parser.parse_args()
    if args.stage != 'all' and args.plan is None:
        parser.error('--plan required')
    if args.stage == 'target-protected' and args.defense_report is None:
        parser.error('--defense-report required')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-email-continuation-' + args.stage + '-' + uuid.uuid4().hex[:8]
    folder, raw = ROOT / 'coordination/returns' / run_id, ROOT / 'runs' / run_id
    folder.mkdir(parents=True, exist_ok=False)
    raw.mkdir(parents=True, exist_ok=False)
    report = {'task_id': 'R0-5090-014', 'run_id': run_id, 'operation': args.stage, 'run_kind': 'debug',
              'git_head': pilot.git_head(), 'hostname': platform.node(), 'platform': platform.system(),
              'formal_inference_executed': False, 'asr_computed': False, 'formal_checkpoint_selected': False,
              'old_evidence_modified': False, 'formal_readiness': False, 'status': 'NOT_STARTED', 'raw_dir': str(raw)}
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_IMPLICIT_TOKEN='1', CUDA_VISIBLE_DEVICES='0')
    try:
        with (folder / 'runtime.log').open('x', encoding='utf-8') as log:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                if platform.node().casefold() != 'desktop-b5pnbnc' or platform.system() != 'Linux':
                    raise RuntimeError('Run on actual 5090 WSL host')
                report['packages'] = pilot.versions()
                if report['packages'] != pilot.EXPECTED:
                    raise RuntimeError('Accepted runtime packages changed')
                pilot.benchmark_module(ROOT)
                if args.stage == 'all':
                    create_plan(report, raw)
                    report['children'] = []
                    defense_path = None
                    for stage in ['defense', 'target-protected']:
                        if stage == 'target-protected':
                            defense = pilot.read_json(defense_path)
                            if not any(c['validity'] == 'VALID_DEBUG_PATH' for c in defense['cases']):
                                report['children'].append({'operation': stage, 'status': 'SKIPPED_ALL_UPSTREAM_INVALID'})
                                break
                        command = [sys.executable, str(Path(__file__).resolve()), '--stage', stage, '--plan', report['plan_path']]
                        if defense_path:
                            command += ['--defense-report', str(defense_path)]
                        child = subprocess.run(command, capture_output=True, text=True)
                        log.write(child.stdout + child.stderr)
                        record = {'operation': stage, 'command': command, 'exit_code': child.returncode}
                        report['children'].append(record)
                        record.update(json.loads(child.stdout))
                        if child.returncode:
                            raise RuntimeError('Child failed: ' + stage)
                        if stage == 'defense':
                            defense_path = ROOT / record['return_path']
                    report['status'] = 'DEBUG_EMAIL_CONDITION_EXECUTED_REVIEW_REQUIRED'
                else:
                    plan, inputs = load_plan(args.plan, report)
                    if args.stage == 'defense':
                        pilot.run_defense(plan, inputs, report, raw)
                        add_defense_audit(plan, report)
                    else:
                        pilot.target_stage(plan, inputs, report, raw, 'promptlocate', args.defense_report)
    except Exception as exc:
        report.update(status='FAILED', error_type=type(exc).__name__, error_message=str(exc), traceback=traceback.format_exc(limit=12))
    output = folder / 'email_stage.json'
    pilot.write_new(output, report)
    print(json.dumps({'return_path': output.relative_to(ROOT).as_posix(), 'status': report['status']}))
    return 2 if report['status'] == 'FAILED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
