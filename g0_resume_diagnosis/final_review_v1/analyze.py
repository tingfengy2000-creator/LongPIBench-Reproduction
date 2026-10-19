"""Final G0 evidence review, no new inference or algorithm development."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from repro.archive import json_bytes
from g0_resume_diagnosis.audit_existing import extracted_replay, replay_query

SOURCE = 'a857540235093e302b0644c4aebf38184a6045a9'
INPUT = '8e3bec96546fb7f8d19bda4cba81987ea773b80d'
PREFIX = 'coordination/returns/20261019T060252Z-g0-controls-c9032be1/'
HISTORY = 'coordination/returns/20261019T054409Z-g0-visibility-fd1beae5/'
PLAN_SHA = '39639607866a6cbc5c2a44be6516c68e9022cf0e4bf3733ade4cc7dc64a442f8'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', SOURCE + ':' + path])


def load(path):
    return json.loads(blob(path))


def save(name, data):
    with (OUT / name).open('xb') as f:
        f.write(json_bytes(data))


def table(name, rows):
    with (OUT / name).open('x', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tokenizer-dir', type=Path, required=True)
    ap.add_argument('--upstream-root', type=Path, required=True)
    args = ap.parse_args()
    changes = subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--name-status', INPUT, SOURCE]).decode().splitlines()
    require(len(changes) == 31 and all(c.startswith('A\t'+PREFIX) for c in changes), 'Unexpected execution-side changes')
    paths = [c.split('\t')[1] for c in changes]
    require(set(blob(PREFIX+'PUBLISH_FILES.txt').decode().splitlines()) | {PREFIX+'PUBLISH_FILES.txt'} == set(paths), 'Published inventory differs')
    report = load(PREFIX+'g0_controls.json')
    plan_data = blob('g0_resume_diagnosis/frozen_controls_v1/plan.json')
    plan = json.loads(plan_data)
    require(sha(plan_data) == report['plan_sha256'] == report['frozen_plan_sha256'] == PLAN_SHA, 'Plan changed')
    require(report['input_commit'] == INPUT and report['runner_sha256'] == sha(blob('g0_resume_diagnosis/run_controls.py')), 'Executed runner differs')
    require(report['status'] == 'G0_FROZEN26_CONTROLS_EXECUTED_REVIEW_REQUIRED'
            and report['new_forward_queries_attempted'] == report['new_forward_queries_completed'] == 26
            and report['control_manifest_validated_before_model_load'], 'Incomplete execution')
    require(report['original_model_configuration'] == plan['model_config']
            and report['loaded_generation_defaults'] == plan['saved_generation_defaults'], 'Detector condition changed')
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_IMPLICIT_TOKEN='1', CUDA_VISIBLE_DEVICES='')
    from transformers import AutoTokenizer
    import importlib.metadata
    require(importlib.metadata.version('transformers') == '4.51.3' and importlib.metadata.version('tokenizers') == '0.21.1', 'Fast backend differs')
    public = load('coordination/returns/20261017T152919Z-public-models-f7e08811/public_models.json')
    snapshot = next(x for x in public['results'] if x['role'] == 'detector_base')
    for entry in snapshot['files']:
        if entry['filename'] in {'config.json', 'tokenizer.json', 'tokenizer.model', 'tokenizer_config.json', 'special_tokens_map.json'}:
            data = (args.tokenizer_dir / entry['filename']).read_bytes()
            require(len(data) == entry['size_bytes'] and sha(data) == entry['sha256'], 'Pinned small file differs')
    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer_dir), add_bos_token=True, local_files_only=True, token=False, trust_remote_code=False)
    require(tokenizer.is_fast, 'Fast tokenizer required')
    detector, formatter_type, manifest = extracted_replay(args.upstream_root)
    require(manifest == plan['upstream_sources'], 'Pinned upstream differs')
    formatter = formatter_type()
    rows = load(PREFIX+'control_results.json')
    require([r['control_id'] for r in rows] == [c['control_id'] for c in plan['controls']] and len(rows) == 26, 'Control selection/order changed')
    history = {}
    for domain in ['email', 'resume']:
        for cond in ['clean', 'attack']:
            for line in blob(HISTORY+domain+'_'+cond+'_visibility.jsonl').splitlines():
                r = json.loads(line); history[r['case_id']] = r
    require(len(history) == 400, 'Historical population differs')
    index = []; source_files = {}
    dtype_counts = Counter(); preview_count = 0; full_value_count = 0
    for case, row in zip(plan['controls'], rows):
        cid = case['control_id']
        require(row == load(PREFIX+cid+'.json'), 'Case card/aggregate differs')
        for key in ['condition', 'domain', 'source_document_id', 'payload_domain', 'body_budget', 'data_sha256',
                    'input_ids_sha256', 'input_token_count', 'payload_present_after_preprocessing', 'payload_token_span']:
            require(row[key] == case[key], 'Control metadata differs: '+cid+' '+key)
        require(row['error'] is None and row['declared_query_completed'] and row['raw_lm_logits_finite'], 'Failed control')
        require(row['native_injection_probability'] is None and not row['generation_arguments_changed']
                and not row['measurement_hook_returns_replacement'], 'Measurement condition differs')
        _, query, _ = replay_query(detector, case['data'], 'DGDSGNH')
        formatted = formatter.formatting_func(query)+'\n### Response: '
        ids = tokenizer(formatted)['input_ids']
        require(ids == case['input_token_ids'] and sha(json_bytes(ids)) == case['input_ids_sha256'], 'Frozen IDs not reproduced')
        generated = row['generated_token_ids']
        continuation = tokenizer.decode(generated, skip_special_tokens=True)
        response = tokenizer.decode(ids+generated, skip_special_tokens=True).replace(formatted, '')
        require(continuation == row['generated_continuation'] and response == row['original_query_response'], 'Decode differs')
        for observed in [response, continuation]:
            flag, _, _ = replay_query(detector, case['data'], observed)
            require(flag == row['binary_flag'], 'Binary output not reproduced')
        require(not row['interface_decision_difference'], 'Unexpected interface issue')
        steps, vocab = row['raw_lm_logits_shape']
        require(steps == len(generated) == 10 and vocab == 32000, 'Logit shape differs')
        require(len(row['raw_logit_top5_by_step']) == len(row['original_logit_dtypes']) == steps, 'Missing raw logit previews')
        dtype_counts.update(row['original_logit_dtypes'])
        for preview in row['raw_logit_top5_by_step']:
            require(len(preview['token_ids']) == len(preview['raw_logits']) == 5 and
                    all(type(i) is int and 0 <= i < vocab for i in preview['token_ids']) and
                    all(math.isfinite(v) for v in preview['raw_logits']) and
                    preview['raw_logits'] == sorted(preview['raw_logits'], reverse=True), 'Bad raw logit preview')
            preview_count += 5
        full_value_count += steps*vocab
        for name in ['raw_record', 'raw_lm_logits']:
            path = PurePosixPath(row[name+'_path'])
            require(str(path.parent) == report['local_raw_dir'] and len(row[name+'_sha256']) == 64, 'Raw evidence pointer invalid')
        old = history.get((case['source_document_id'] or '')+'-authority_spoof')
        historical_clean = history.get((case['source_document_id'] or '')+'-no')
        if case['condition'] == 'natural_full':
            require(old['generated_token_ids'] == generated and old['binary_flag'] == row['binary_flag']
                    and row['historical_R2_tokens_identical'] and row['historical_R2_binary_identical'], 'Natural replay differs')
        index.append({'control_id': cid, 'condition': row['condition'], 'domain': row['domain'],
            'source_document_id': row['source_document_id'], 'payload_domain': row['payload_domain'], 'body_budget': row['body_budget'],
            'input_tokens': row['input_token_count'], 'payload_visible': row['payload_present_after_preprocessing'],
            'binary_flag': row['binary_flag'], 'generated_continuation': row['generated_continuation'],
            'historical_clean_flag': historical_clean['binary_flag'] if historical_clean and case['condition'] == 'natural_full' else None,
            'raw_record_path': row['raw_record_path'], 'raw_record_sha256': row['raw_record_sha256'],
            'raw_logits_path': row['raw_lm_logits_path'], 'raw_logits_sha256': row['raw_lm_logits_sha256'],
            'raw_logits_steps': steps, 'raw_logits_vocab': vocab, 'full_npz_read_on_coordinator': False,
            'source_card': PREFIX+cid+'.json', 'source_card_sha256': sha(blob(PREFIX+cid+'.json'))})
    crossed = [r for r in rows if r['condition'] == 'crossed_prefix']
    matrix = []
    for domain in ['email', 'resume']:
        for payload in ['email', 'resume']:
            for n in plan['shared_body_lengths']:
                group = [r for r in crossed if r['domain'] == domain and r['payload_domain'] == payload and r['body_budget'] == n]
                require(len(group) == 2 and len({r['input_token_count'] for r in group}) == 1, 'Wrong matrix cell')
                matrix.append({'body_domain': domain, 'payload_domain': payload, 'body_tokens': n,
                    'actual_total_tokens': group[0]['input_token_count'], 'source_count': 2,
                    'flag1_count': sum(r['binary_flag'] == 1 for r in group), 'flag0_count': sum(r['binary_flag'] == 0 for r in group),
                    'control_ids': '|'.join(r['control_id'] for r in group)})
    lookup = {r['control_id']: r for r in rows}
    pairs = []
    for pair in plan['cross_domain_pairs']:
        a, b = [lookup[c] for c in pair['control_ids']]
        require(a['input_token_count'] == b['input_token_count'] and a['payload_domain'] == b['payload_domain'], 'Cross-domain length/payload differs')
        pairs.append({'email_control': a['control_id'], 'resume_control': b['control_id'],
            'body_tokens': a['body_budget'], 'payload_domain': a['payload_domain'], 'total_tokens_each': a['input_token_count'],
            'email_flag': a['binary_flag'], 'resume_flag': b['binary_flag']})
    payload_only = [r for r in rows if r['condition'] == 'payload_only']
    exclusions = [r for r in rows if r['condition'] == 'intentional_payload_exclusion']
    require(len(payload_only) == 2 and all(r['binary_flag'] == 0 for r in payload_only), 'Payload-only summary differs')
    require(len(exclusions) == 4 and all(not r['payload_present_after_preprocessing'] and r['binary_flag'] == 0 for r in exclusions), 'Exclusion summary differs')
    resume_rows = [r for r in history.values() if r['domain'] == 'resume' and r['attack_type'] == 'authority_spoof']
    require(len(resume_rows) == 100 and all(r['root_category'] == 'B' and r['payload_complete_in_actual_input'] for r in resume_rows), 'B100 history differs')
    visibility = [{k: r[k] for k in ['case_id', 'original_document_tokens_including_bos', 'actual_detector_input_tokens',
        'original_payload_char_span', 'original_payload_token_span', 'formatted_payload_token_span_expected',
        'actual_retained_payload_token_span', 'payload_complete_in_actual_input', 'truncation_direction', 'binary_flag', 'root_category', 'raw_sha256']}
        for r in sorted(resume_rows, key=lambda x: x['case_id'])]
    table('all26_controls.csv', index)
    table('crossed_matrix.csv', matrix)
    table('domain_pairs.csv', pairs)
    table('resume100_visibility.csv', visibility)
    for p in paths:
        source_files[p] = sha(blob(p))
    history_report = load(HISTORY+'g0_audit.json')
    save('model_configuration_audit.json', {'base': history_report['model_audit']['base_model'],
        'adapter': history_report['model_audit']['adapter'], 'adapter_revision': history_report['model_audit']['adapter_revision'],
        'tokenizer': history_report['model_audit']['tokenizer'], 'precision': history_report['model_audit']['precision_saved'],
        'binary_rule': history_report['model_audit']['binary_rule'], 'numeric_risk_threshold': None,
        'model_context': history_report['model_audit']['model_config_context'],
        'fixed_file_hashes_verified_on_source': history_report['model_audit']['actual_fixed_files_sha256_verified'],
        'control_loaded_attention_implementation': report['loaded_attention_implementation'],
        'generation_defaults': report['loaded_generation_defaults'], 'query_overrides': {'max_new_tokens': 10, 'repetition_penalty': 1.2},
        'coordinator_did_not_reload_weights': True, 'controls_original_logit_dtypes': dict(dtype_counts),
        'saved_raw_logits_storage_dtype': 'float32; lossless widening of observed float16 values; source forward not changed'})
    save('analysis.json', {'status': 'G0_DIAGNOSIS_COMPLETE_WITH_IDENTIFIABILITY_LIMITS_STOP',
        'source_commit': SOURCE, 'source_run_id': report['run_id'], 'frozen_plan_sha256': PLAN_SHA,
        'history_root_categories_resume100': {'A': 0, 'B': 100, 'C': 0, 'D': 0, 'E': 0},
        'control_count': 26, 'source_document_count': 4, 'total_flags': dict(Counter(str(r['binary_flag']) for r in rows)),
        'crossed_matrix': matrix, 'domain_pairs': pairs,
        'payload_only': {r['payload_domain']: r['binary_flag'] for r in payload_only},
        'natural_history_replay_identical': 4, 'intentional_payload_exclusion_flags0': 4,
        'risk_probability_produced': False, 'raw_logits_reported_finite_on_source': 26,
        'raw_logit_top5_values_checked_on_coordinator': preview_count, 'raw_full_logit_values_stored_on_source': full_value_count,
        'full_npz_arrays_independently_read_on_coordinator': False, 'local_weights_loaded': False, 'new_local_model_forward_count': 0,
        'all26_frozen_inputs_decode_binary_reconstructed_on_coordinator': True,
        'conclusion': 'Historical Resume misses are B: no input coverage/truncation or binary-interface failure. Controls show payload/context interactions; pure domain or pure length causation is not identified.',
        'algorithm_development_go': False, 'stop_after_G0': True,
        'identifiability_limits': ['Only4 source documents and2 fixed payloads, constructed prefixes; not26 independent samples.',
            'Increasing prefix length also adds content; length-only causal effect not isolated.',
            'Changing payload changes both semantics and54 input tokens; semantics-only causal effect not isolated.',
            'Same-payload same-length cross-domain contrast is content/context-specific, not population domain causation.',
            'Full raw/NPZ arrays remain on5090; local checks cover returned records, decoded outputs and1300 top5 raw values.'],
        'source_return_file_sha256': source_files,
        'script_sha256': sha(Path(__file__).read_bytes())})
    print(json.dumps({'status': 'G0_DIAGNOSIS_COMPLETE_WITH_IDENTIFIABILITY_LIMITS_STOP', 'controls': 26,
        'flags': dict(Counter(str(r['binary_flag']) for r in rows)), 'raw_logit_preview_values_checked': preview_count,
        'no_new_local_inference': True}))


if __name__ == '__main__':
    main()
