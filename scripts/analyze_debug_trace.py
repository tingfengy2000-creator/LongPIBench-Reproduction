"""R0-5090-013: read existing 012 raw traces; never import GPU/model runtimes."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
DEFENSE_RECEIPT = 'coordination/returns/20261018T034557Z-debug-pilot-defense-16a9eecd/pilot_stage.json'


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(value):
    return sha_bytes(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8'))


def text_summary(text):
    return {'sha256': sha_bytes(text.encode('utf-8')), 'chars': len(text),
            'head': text[:120], 'tail': text[-120:] if len(text) > 120 else ''}


def compact_event(event, index):
    row = {k: event[k] for k in ['function', 'role', 'seconds', 'error_type', 'error_message',
        'binary_result', 'finite', 'average_log_probability', 'total_log_probability', 'influence',
        'condition_token_count', 'full_token_count_before_crop', 'upstream_full_token_count_after_crop',
        'condition_exceeds_cropped_length', 'generation_kwargs', 'input_token_count'] if k in event}
    row['event_index'] = index
    if 'segments' in event:
        row['segment_count'] = len(event['segments'])
        row['segments_sha256'] = fingerprint(event['segments'])
    for key in ['data', 'prompt', 'prefix', 'raw_response', 'condition_text', 'target_text', 'middle', 'suffix']:
        if isinstance(event.get(key), str):
            row[key] = text_summary(event[key])
    if 'generated_token_ids' in event:
        row['output_token_count'] = len(event['generated_token_ids'])
        row['generated_token_ids'] = event['generated_token_ids']
    return row


def summarize_case(record):
    trace = record['trace']
    events = trace['events']
    function_counts = Counter(e['function'] for e in events)
    roles = Counter((e['function'], e.get('role', 'locator')) for e in events)
    generations = [e for e in events if e['function'] == 'generate' and 'generated_token_ids' in e]
    decisions = [e for e in events if e['function'] == 'query' and 'binary_result' in e]
    query_signatures = Counter((e.get('role'), fingerprint(e.get('data'))) for e in decisions)
    generation_roles = Counter(e.get('role', 'unknown') for e in generations)
    helper = [e for e in events if e['function'] == 'compute_conditional_probability']
    completed_helper = [e for e in helper if 'finite' in e]
    searches = []
    states = Counter()
    for index, event in enumerate(events):
        if event['function'] != 'binary_search' or 'result' not in event:
            continue
        result = event['result']
        state = {'segments': event['segments'], 'start': event['start'], 'end': event['end'], 'prefix': event['prefix']}
        state_sha = fingerprint(state)
        states[state_sha] += 1
        cache = result[2]
        searches.append({'event_index': index, 'segment_count': len(event['segments']),
            'start': event['start'], 'end': event['end'], 'returned_end': result[0],
            'new_query_count_reported_by_original': result[1], 'cache_entries': len(cache),
            'prefix_sha256': fingerprint(event['prefix']), 'state_sha256': state_sha})
    split_events = [e for e in events if e['function'] == 'split_sentence' and 'segments' in e]
    counts = [e['segment_count'] for e in searches]
    elapsed = record.get('seconds')
    errors = [{'event_index': i, 'function': e['function'], 'error_type': e.get('error_type'),
               'error_message': e.get('error_message')} for i, e in enumerate(events) if e.get('error_type')]
    return {'case_id': record['case_id'], 'validity': record['validity'],
        'detector_flag': record.get('detector_flag'), 'error_stage': record.get('error_stage'),
        'error_type': record.get('error_type'), 'error_message': record.get('error_message'),
        'case_elapsed_seconds': elapsed, 'trace_call_count': trace['call_count'], 'recorded_event_count': len(events),
        'debug_budgets': trace['debug_budgets'], 'logged_errors': trace['logged_errors'],
        'function_counts': dict(function_counts),
        'function_role_counts': {name + ':' + role: count for (name, role), count in roles.items()},
        'completed_model_generate_calls': len(generations), 'completed_generate_by_role': dict(generation_roles),
        'completed_generation_seconds_sum': sum(e['seconds'] for e in generations),
        'time_scope': 'Only generate timings summed; nested search/helper timings are not additive',
        'completed_oracle_decisions': sum(e.get('role') == 'localization_oracle' for e in decisions),
        'unique_role_query_texts': len(query_signatures),
        'repeated_role_query_texts': [{'role': role, 'text_sha256': sha, 'count': count}
                                      for (role, sha), count in query_signatures.most_common(12) if count > 1],
        'completed_helper_probability_calls': len(completed_helper), 'entered_helper_probability_calls': len(helper),
        'helper_nonfinite_observed': trace['nonfinite_helper'],
        'nonfinite_completed_helper_calls': sum(e['finite'] is False for e in completed_helper),
        'helper_condition_exceeds_crop_count': sum(bool(e.get('condition_exceeds_cropped_length')) for e in completed_helper),
        'absence_of_nan_scope': 'Recorded completed helper calls only; not unexecuted remainder',
        'raw_segment_counts': [len(e['segments']) for e in split_events],
        'segment_mapping_status': (trace.get('segment_mapping') or {}).get('status'),
        'completed_binary_searches': searches,
        'consecutive_segment_count_changes': [b-a for a, b in zip(counts, counts[1:])],
        'repeated_completed_search_states': [{'state_sha256': sha, 'count': count} for sha, count in states.items() if count > 1],
        'search_progress_interpretation': 'Observed completed calls only; repeats alone do not prove an infinite loop',
        'last_completed_oracle_decisions': [compact_event(e, i) for i, e in list(enumerate(events))
            if e['function'] == 'query' and 'binary_result' in e][-8:],
        'last_events': [compact_event(e, i) for i, e in list(enumerate(events))[-20:]],
        'exception_events': errors[-20:], 'full_trace_replayed': False, 'model_executed': False}


def analyze_receipt(root, receipt_path):
    raw_receipt = receipt_path.read_bytes()
    receipt = json.loads(raw_receipt)
    if (receipt['task_id'] != 'R0-5090-012' or receipt['operation'] != 'defense'
            or receipt['status'] != 'DEBUG_DEFENSE_RECORDED'):
        raise ValueError('Expected original 012 defense receipt')
    results = []
    for case in receipt['cases']:
        path = Path(case['evidence_path']).resolve(strict=True)
        if not path.is_relative_to((root / 'runs').resolve()):
            raise ValueError('Raw case is outside repository runs storage')
        blob = path.read_bytes()
        if sha_bytes(blob) != case['evidence_sha256']:
            raise ValueError('Raw evidence differs from original 012 receipt')
        record = json.loads(blob)
        if record['case_id'] != case['case_id'] or record['validity'] != case['validity']:
            raise ValueError('Raw case identity/status differs from receipt')
        summary = summarize_case(record)
        summary.update(source_raw_path=str(path), source_raw_sha256=sha_bytes(blob), source_raw_bytes=len(blob))
        results.append(summary)
    return {'source_receipt': receipt_path.relative_to(root).as_posix(),
            'source_receipt_sha256': sha_bytes(raw_receipt), 'original_run_id': receipt['run_id'],
            'original_git_head': receipt['git_head'], 'original_plan_sha256': receipt['plan_sha256'], 'cases': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-trace-audit-' + uuid.uuid4().hex[:8]
    report = {'task_id': 'R0-5090-013', 'run_id': run_id, 'run_kind': 'debug_evidence_review',
              'hostname': platform.node(), 'platform': platform.system(), 'model_executed': False,
              'gpu_runtime_imported': False, 'asr_computed': False, 'formal_checkpoint_selected': False,
              'original_evidence_modified': False, 'status': 'NOT_STARTED'}
    head = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True)
    report['git_head'] = head.stdout.strip()
    try:
        if platform.node().casefold() != 'desktop-b5pnbnc' or platform.system() != 'Linux':
            raise RuntimeError('Read existing raw on actual execution host in WSL')
        report.update(analyze_receipt(ROOT, ROOT / DEFENSE_RECEIPT))
        report['status'] = 'TRACE_SUMMARIES_CREATED_NOT_RERUN'
    except Exception as exc:
        report.update(status='FAILED', error_type=type(exc).__name__, error_message=str(exc),
                      traceback=traceback.format_exc(limit=10))
    folder = ROOT / 'coordination/returns' / run_id
    folder.mkdir(parents=True, exist_ok=False)
    output = folder / 'trace_audit.json'
    encoded = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    if len(encoded) > 1024**2:
        raise RuntimeError('Summary exceeds 1MiB; preserve raw and report without committing large file')
    with output.open('xb') as stream:
        stream.write(encoded)
    print(json.dumps({'return_path': output.relative_to(ROOT).as_posix(), 'status': report['status']}))
    return 2 if report['status'] == 'FAILED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
