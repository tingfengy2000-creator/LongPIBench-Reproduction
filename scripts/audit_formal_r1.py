"""Read immutable R1 raw records, verify tokens and recompute original scoring.

No model loading or generation. Also used as the mandatory first R2 stage.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repro.archive import json_bytes
from repro.scoring import evaluate_response
from repro.target_runtime import stop_reason
from scripts import run_formal_r1 as r1

RECEIPT = 'coordination/returns/20261018T055552Z-formal-r1-b00a0078/r1_run.json'
SOURCE_COMMIT = 'b90b1504e28717c0a1dca492b56a1c23d1ec21ae'
INPUT_COMMIT = '37715402ff108515c8acb15ce5687a3337eeef35'
RECEIPT_SHA = 'e3b18f0c6a552712d2a262a57bc70255f37afd643929189f7ad4d6f9cf1c94ab'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_raw(root, raw_dir, row):
    path = Path(row['path']).resolve(strict=True)
    require(path.parent == raw_dir and path.is_relative_to((root / 'runs').resolve()), 'Raw path escapes frozen run')
    require(path.name == row['case_id'] + '.json', 'Raw filename differs from case ID')
    require(path.stat().st_size == row['bytes'] and r1.pilot.file_sha(path) == row['sha256'], 'Raw size/hash mismatch: ' + row['case_id'])
    return r1.pilot.read_json(path)


def audit_cases(root, source, cases, benchmark, config, tokenizer):
    raw_dir = Path(source['raw_dir']).resolve(strict=True)
    require(raw_dir.is_relative_to((root / 'runs').resolve()), 'R1 raw directory outside runs')
    require([r['case_id'] for r in source['case_evidence']] == [c['case_id'] for c in cases], 'Case order/population differs')
    counts, summaries, exceptions = {}, [], []
    for case, row in zip(cases, source['case_evidence']):
        record = checked_raw(root, raw_dir, row)
        require(record['input'] == case and record['case_id'] == case['case_id'], 'Raw official input mismatch')
        require(record['run_id'] == source['run_id'] and record['run_kind'] == 'formal'
                and record['stage'] == 'R1' and record['condition'] == 'no_defense'
                and record['frozen_config_sha256'] == r1.FROZEN_CONFIG_SHA256
                and record['study_condition'] == config['study_condition'], 'Raw formal provenance mismatch')
        target = record['target']
        messages = [{'role': 'system', 'content': case['system_prompt']}, {'role': 'user', 'content': case['data_prompt']}]
        require(target['messages'] == messages, 'Actual messages changed')
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
        require(prompt == target['rendered_prompt'] and ids == target['input_token_ids']
                and len(ids) == target['input_token_count'], 'Rendered prompt/input tokens mismatch')
        require(target['chat_template_sha256'] == config['target']['chat_template_sha256'], 'Per-case template hash differs')
        generated = target['generated_token_ids']
        require(all(type(v) is int and v >= 0 for v in generated)
                and len(generated) == target['output_token_count'], 'Generated tokens/count mismatch')
        require(tokenizer.decode(generated, skip_special_tokens=True).strip() == target['raw_response'], 'Decoded response mismatch')
        require(target['generation_attempted'] is True and target['generation_overrides'] == {
            'max_new_tokens': config['target']['max_new_tokens'], 'do_sample': False,
            'pad_token_id': config['target']['pad_token_id']}, 'Actual generation overrides differ')
        stop = stop_reason(generated, config['target']['eos_token_ids'], config['target']['max_new_tokens'])
        require(stop == target['stop_reason'], 'Stop reason differs from saved tokens')
        evaluation = evaluate_response(case['suite'], case['goal'], target['raw_response'],
            parse=benchmark.parse_json_response, score=benchmark.score_response)
        require(evaluation == record['evaluation'], 'Saved evaluation differs from fixed scorer')
        validity = evaluation['validity'] if stop == 'EOS' else ('CENSORED_TOKEN_LIMIT' if stop == 'TOKEN_LIMIT' else 'UNKNOWN_STOP_REVIEW_REQUIRED')
        require(validity == record['validity'] == row['validity'], 'Validity mismatch')
        r1.add_count(counts, case, record)
        summary = {'case_id': case['case_id'], 'validity': validity, 'raw_sha256': row['sha256'],
            'official_success': evaluation['official_success'], 'audit_success': evaluation['audit_success'],
            'issues': evaluation['issues'], 'stop_reason': stop, 'input_tokens': len(ids),
            'output_tokens': len(generated)}
        summaries.append(summary)
        if validity != 'VALID' or evaluation['issues']:
            exceptions.append(dict(summary, raw_response=target['raw_response'],
                                   parse_error=evaluation.get('parse_error')))
    require(counts == source['counts'], 'Recomputed counts differ from receipt')
    return {'counts': counts, 'cases': summaries, 'exceptions': exceptions,
            'verified_raw_count': len(summaries), 'tokens_reconstructed_on_cpu': True,
            'raw_hashes_verified': True, 'official_and_audit_scores_recomputed': True}


def audit(root):
    require(r1.pilot.file_sha(root / RECEIPT) == RECEIPT_SHA, 'Accepted R1 receipt bytes changed')
    source = r1.pilot.read_json(root / RECEIPT)
    config = r1.load_config(root)
    require(source['status'] == 'FORMAL_R1_EXECUTED_REVIEW_REQUIRED' and source['stage'] == 'complete'
            and source['attempted'] == 400 and source['git_head'] == INPUT_COMMIT
            and source['frozen_config_sha256'] == r1.FROZEN_CONFIG_SHA256
            and source['frozen_config'] == config and source['retries'] == 0
            and source['debug_records_reused_as_formal'] is False, 'R1 receipt provenance differs')
    benchmark = r1.pilot.benchmark_module(root)
    cases = r1.build_inputs(root, benchmark, config)
    raw_dir = Path(source['raw_dir']).resolve(strict=True)
    require(raw_dir.is_relative_to((root / 'runs').resolve()), 'Raw run outside runs')
    require(r1.pilot.file_sha(raw_dir / 'inputs.json') == source['input_set_sha256'] == config['input_freeze']['canonical_input_set_sha256']
            and r1.pilot.read_json(raw_dir / 'inputs.json') == cases, 'Frozen full inputs changed')
    require(r1.pilot.file_sha(raw_dir / 'manifest.json') == source['manifest_sha256'], 'R1 manifest changed')
    manifest = r1.pilot.read_json(raw_dir / 'manifest.json')
    expected_versions = dict(line.strip().split('==') for line in
        (root / 'requirements/r0-compat-candidate.txt').read_text(encoding='utf-8').splitlines()
        if line.strip() and not line.startswith('#'))
    require(source['runtime_versions'] == expected_versions, 'Saved runtime versions differ from frozen stack')
    for key in ['git_head', 'run_id', 'frozen_config_sha256', 'input_set_sha256', 'runtime_versions', 'target_runtime']:
        require(manifest[key] == source[key], 'Manifest differs: ' + key)
    require(manifest['config'] == config and manifest['task_id'] == 'R1-5090-001'
            and manifest['run_kind'] == 'formal', 'Manifest condition differs')
    require(manifest['tokenization_patch_sha256'] == r1.pilot.file_sha(root / 'patches/target_chat_tokenization.diff')
            and manifest['requirement_candidate_sha256'] == r1.pilot.file_sha(root / 'requirements/r0-compat-candidate.txt'), 'Patch/requirements changed')
    from transformers import AutoTokenizer
    spec = r1.pilot.local_spec(root, 'target')
    require(spec == source['target_runtime']['model_source'], 'Target source differs')
    tokenizer = AutoTokenizer.from_pretrained(spec['resolved_path'], local_files_only=True, trust_remote_code=False, token=False)
    require(hashlib.sha256(tokenizer.chat_template.encode()).hexdigest() == config['target']['chat_template_sha256'], 'Tokenizer template changed')
    result = audit_cases(root, source, cases, benchmark, config, tokenizer)
    result.update(status='R1_RAW_VERIFIED_WITH_SEPARATE_INVALID_OUTCOMES', source_receipt=RECEIPT,
        source_receipt_sha256=r1.pilot.file_sha(root / RECEIPT), source_commit=SOURCE_COMMIT,
        model_weights_loaded=False, gpu_inference_executed=False, asr_computed=False,
        source_run_id=source['run_id'], manifest_sha256=source['manifest_sha256'])
    return result


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-r1-raw-audit-' + uuid.uuid4().hex[:8]
    folder = ROOT / 'coordination/returns' / run_id
    folder.mkdir(parents=True, exist_ok=False)
    report = {'task_id': 'R2-5090-001', 'operation': 'r1-audit', 'run_id': run_id, 'git_head': r1.pilot.git_head()}
    try:
        report.update(audit(ROOT))
    except Exception as exc:
        report.update(status='FAILED', error_type=type(exc).__name__, error_message=str(exc), traceback=traceback.format_exc(limit=12))
    output = folder / 'r1_audit.json'
    r1.pilot.write_new(output, report)
    print(json.dumps({'return_path': output.relative_to(ROOT).as_posix(), 'status': report['status']}))
    return 2 if report['status'] == 'FAILED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
