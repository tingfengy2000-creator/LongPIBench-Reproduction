"""Reconstruct the G0 historical witnesses and freeze the preregistered26 controls.

CPU/tokenizer only. No weights, inference, new thresholds or source mutation.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repro.archive import json_bytes
from g0_resume_diagnosis.audit_existing import extracted_replay, replay_query, interval_from_offsets

SOURCE = '718c33d8f27e6c11b6552c41a6fccc0cca495541'
PREFIX = 'coordination/returns/20261019T054409Z-g0-visibility-fd1beae5/'
OUT = ROOT / 'g0_resume_diagnosis/history_review_v1'
FROZEN = ROOT / 'g0_resume_diagnosis/frozen_controls_v1'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', SOURCE + ':' + path])


def save(path, value):
    with path.open('xb') as f:
        f.write(json_bytes(value))


def formatted_input(detector_type, formatter, data):
    _, query, processed = replay_query(detector_type, data, 'DGDSGNH')
    return formatter.formatting_func(query) + '\n### Response: ', processed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tokenizer-dir', type=Path, required=True)
    parser.add_argument('--upstream-root', type=Path, required=True)
    args = parser.parse_args()
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_IMPLICIT_TOKEN='1', CUDA_VISIBLE_DEVICES='')
    from transformers import AutoTokenizer
    import importlib.metadata
    receipt = json.loads(blob(PREFIX + 'g0_audit.json'))
    require(receipt['status'] == 'G0_HISTORICAL_VISIBILITY_AUDIT_COMPLETE_REVIEW_REQUIRED', 'G0 receipt not successful')
    require(receipt['audit_script_sha256'] == sha(blob('g0_resume_diagnosis/audit_existing.py')), 'Execution script differs')
    # The tokenizer.json fast backend uses transformers/tokenizers. The local
    # Python3.13 environment has a different, inactive slow SentencePiece package;
    # all400 historical input-ID hashes must still match before any plan is saved.
    for package in ['transformers', 'tokenizers']:
        require(importlib.metadata.version(package) == receipt['model_audit']['runtime_versions_saved_in_R2'][package], 'Tokenizer runtime differs')
    small_files = {'config.json', 'special_tokens_map.json', 'tokenizer.json', 'tokenizer.model', 'tokenizer_config.json'}
    public = json.loads(blob('coordination/returns/20261017T152919Z-public-models-f7e08811/public_models.json'))
    snapshot = next(r for r in public['results'] if r['role'] == 'detector_base')
    for entry in snapshot['files']:
        if entry['filename'] in small_files:
            data = (args.tokenizer_dir / entry['filename']).read_bytes()
            require(len(data) == entry['size_bytes'] and sha(data) == entry['sha256'], 'Fixed tokenizer file differs')
    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer_dir), add_bos_token=True, local_files_only=True, token=False, trust_remote_code=False)
    require(tokenizer.is_fast, 'Slow tokenizer is not permitted for this local compatibility scope')
    tokenizer_runtime = {name: importlib.metadata.version(name) for name in ['transformers', 'tokenizers', 'sentencepiece']}
    detector_type, formatter_type, source_manifest = extracted_replay(args.upstream_root)
    formatter = formatter_type()
    archived = [json.loads(line) for line in blob('audit/prepared_inputs.jsonl').decode().splitlines()]
    inputs = {f"{c['suite']}-{c['item_id']:03d}-{c['attack']}": c for c in archived}
    defense_path = 'coordination/returns/20261018T081658Z-formal-r2-defense-6a4b35b2/r2_stage.json'
    defense = {r['case_id']: r for r in json.loads(blob(defense_path))['cases']}
    rows = []
    for domain in ['email', 'resume']:
        for attack in ['clean', 'attack']:
            data = blob(PREFIX + domain + '_' + attack + '_visibility.jsonl')
            group = [json.loads(line) for line in data.splitlines()]
            require(len(group) == 100, 'G0 group population differs')
            for row in group:
                cid = row['case_id']; case = inputs[cid]
                require(row['raw_sha256'] == defense[cid]['sha256'], 'R2 raw witness differs')
                require(row['original_input_sha256'] == sha(case['data_prompt'].encode()), 'Original content differs')
                prompt, processed = formatted_input(detector_type, formatter, case['data_prompt'])
                encoded = tokenizer(prompt, return_offsets_mapping=True)
                ids = encoded['input_ids']
                require(sha(json_bytes(ids)) == row['actual_input_ids_sha256'] and len(ids) == row['actual_detector_input_tokens'], 'Actual token hash witness not reproduced')
                require(sha(processed.encode()) == row['preprocessed_input_sha256'], 'Preprocessing differs')
                response = tokenizer.decode(ids + row['generated_token_ids'], skip_special_tokens=True).replace(prompt, '')
                require(sha(response.encode()) == row['saved_query_response']['sha256'], 'Historical response witness differs')
                flag, _, _ = replay_query(detector_type, case['data_prompt'], response)
                continuation = tokenizer.decode(row['generated_token_ids'], skip_special_tokens=True)
                continuation_flag, _, _ = replay_query(detector_type, case['data_prompt'], continuation)
                require(flag == continuation_flag == row['binary_flag'] == defense[cid]['detector_flag'], 'Decision differs')
                require(continuation == row['raw_generated_continuation'], 'Continuation differs')
                if case.get('payload'):
                    needle = case['payload'].lower()
                    require(processed.count(needle) == 1, 'Ambiguous payload')
                    offset = prompt.index('### Text: ') + len('### Text: ') + processed.index(needle)
                    span = interval_from_offsets(encoded['offset_mapping'], offset, offset + len(needle))
                    require(span == row['actual_retained_payload_token_span'] == row['formatted_payload_token_span_expected'], 'Payload token witness differs')
                    require(row['payload_complete_in_actual_input'] is True, 'Payload incomplete')
                require(row['token_truncation_observed'] is False and row['input_exceeds_configured_context'] is False, 'Unexpected coverage issue')
                row['review_response_difference'] = 'identical' if response == continuation else 'whitespace_only' if response.strip() == continuation.strip() else 'other'
                rows.append(row)
    require(len(rows) == len({r['case_id'] for r in rows}) == 400, 'Duplicate or incomplete population')
    groups = {}
    for domain in ['email', 'resume']:
        for attack in ['no', 'authority_spoof']:
            selected = [r for r in rows if r['domain'] == domain and r['attack_type'] == attack]
            groups[domain + ':' + attack] = {'n': len(selected), 'flags': dict(Counter(str(r['binary_flag']) for r in selected)),
                'categories': dict(Counter(r['root_category'] for r in selected)),
                'response_difference': dict(Counter(r['review_response_difference'] for r in selected)),
                'unique_generated_sequences': len({tuple(r['generated_token_ids']) for r in selected})}
    OUT.mkdir(parents=True, exist_ok=False)
    save(OUT / 'history_review.json', {'status': 'HISTORICAL_B100_CONFIRMED_MECHANISM_CONTROLS_NEEDED', 'source_commit': SOURCE,
        'token_input_hashes_reconstructed_on_coordinator': 400, 'payload_token_spans_reconstructed_on_coordinator': 200,
        'binary_and_decode_replayed_on_coordinator': 400, 'full_historical_raw_read_on_coordinator': False,
        'groups': groups, 'model_weights_loaded': False, 'new_forward_count': 0,
        'coordinator_tokenizer_runtime': tokenizer_runtime,
        'slow_sentencepiece_difference': 'Local0.2.1 vs historical0.2.0; inactive tokenizer.json fast path, proven by all400 input-ID hash identities. Remote model execution remains original0.2.0.',
        'conclusion': 'No input-token coverage loss or binary/interface decision discrepancy in the100 Resume attacks. B100. Domain, payload semantics and length remain confounded.',
        'needs_controls': True, 'no_algorithm_development': True})
    # Freeze exactly the rules written before seeing any control-model outputs.
    chosen = [(domain, i) for domain in ['email', 'resume'] for i in [0, 50]]
    payloads = {domain: inputs[f'{domain}-000-authority_spoof']['payload'] for domain in ['email', 'resume']}
    body_ids = {}
    for domain, i in chosen:
        clean = inputs[f'{domain}-{i:03d}-no']['data_prompt']
        preprocessed = detector_type().preprocessing(clean)
        body_ids[(domain, i)] = tokenizer(preprocessed, add_special_tokens=False)['input_ids']
    m = min(map(len, body_ids.values()))
    lengths = [64*(m//128), 64*(m//64)]
    require(64 <= lengths[0] < lengths[1], 'Cannot construct predeclared shared lengths; no sample replacement')
    controls = []
    def add(cid, kind, data, domain, source_id, payload_domain=None, body_budget=None):
        prompt, processed = formatted_input(detector_type, formatter, data)
        enc = tokenizer(prompt, return_offsets_mapping=True)
        payload = payloads.get(payload_domain)
        has_payload = payload is not None and payload.lower() in processed
        span = None
        if has_payload:
            offset = prompt.index('### Text: ') + len('### Text: ') + processed.index(payload.lower())
            span = interval_from_offsets(enc['offset_mapping'], offset, offset+len(payload.lower()))
        require(len(enc['input_ids'])+10 <= 32768, 'Control exceeds configured context')
        controls.append({'control_id': cid, 'condition': kind, 'domain': domain, 'source_document_id': source_id,
            'payload_domain': payload_domain, 'payload_sha256': sha(payload.encode()) if payload else None,
            'body_budget': body_budget, 'data': data, 'data_sha256': sha(data.encode()), 'formatted_prompt': prompt,
            'input_token_ids': enc['input_ids'], 'input_token_count': len(enc['input_ids']),
            'input_ids_sha256': sha(json_bytes(enc['input_ids'])), 'payload_present_after_preprocessing': has_payload,
            'payload_token_span': span, 'constructed_format': kind != 'natural_full'})
    for domain, i in chosen:
        row = inputs[f'{domain}-{i:03d}-authority_spoof']
        add(f'natural-{domain}-{i:03d}', 'natural_full', row['data_prompt'], domain, f'{domain}-{i:03d}', domain)
    for domain in ['email', 'resume']:
        add('payload-only-'+domain, 'payload_only', payloads[domain], None, None, domain)
    for domain, i in chosen:
        for length in lengths:
            prefix = tokenizer.decode(body_ids[(domain, i)][:length], skip_special_tokens=True, clean_up_tokenization_spaces=False)
            for payload_domain in ['email', 'resume']:
                add(f'prefix-{domain}-{i:03d}-n{length}-p{payload_domain}', 'crossed_prefix', prefix+'\n\n'+payloads[payload_domain],
                    domain, f'{domain}-{i:03d}', payload_domain, length)
    for domain, i in chosen:
        prefix = tokenizer.decode(body_ids[(domain, i)][:lengths[1]], skip_special_tokens=True, clean_up_tokenization_spaces=False)
        add(f'right-crop-{domain}-{i:03d}', 'intentional_payload_exclusion', prefix, domain, f'{domain}-{i:03d}', None, lengths[1])
    require(len(controls) == len({r['control_id'] for r in controls}) == 26, 'Control selection differs')
    crossed_pairs = []
    for i in [0, 50]:
        for length in lengths:
            for payload_domain in ['email', 'resume']:
                pair = [next(r for r in controls if r['control_id'] == f'prefix-{d}-{i:03d}-n{length}-p{payload_domain}') for d in ['email', 'resume']]
                difference = abs(pair[0]['input_token_count']-pair[1]['input_token_count'])
                crossed_pairs.append({'control_ids': [r['control_id'] for r in pair], 'token_difference': difference, 'length_matched_within8': difference <= 8})
    FROZEN.mkdir(parents=True, exist_ok=False)
    source_config = json.loads(blob('coordination/returns/20261018T081658Z-formal-r2-defense-6a4b35b2/r2_stage.json'))
    plan = {'schema_version': 1, 'task_id': 'G0-5090-002', 'kind': 'mechanism_controls_not_independent_performance_test',
        'source_commit': SOURCE, 'predeclared_protocol_sha256': sha(blob('g0_resume_diagnosis/control_protocol.md')),
        'upstream_sources': source_manifest, 'source_document_count': 4, 'query_count': 26, 'sample_selection': chosen,
        'body_prefix_basis': 'Fixed detector preprocessing of clean source, then no-BOS token prefix; payloads themselves kept verbatim.',
        'minimum_clean_body_tokens': m, 'shared_body_lengths': lengths, 'cross_domain_pairs': crossed_pairs,
        'model_config': source_config['whole_config'], 'saved_generation_defaults': source_config['defense_generation_configs']['whole'],
        'runtime_versions': source_config['runtime_versions'], 'max_new_tokens': 10, 'repetition_penalty': 1.2,
        'logit_observation': 'Read-only forward hook on underlying causal LM; raw last-position logits before generation processors. No generate argument or return-type changes.',
        'controls': controls, 'no_threshold_fit': True, 'no_payload_optimization': True, 'stop_after_G0': True}
    save(FROZEN / 'plan.json', plan)
    save(FROZEN / 'freeze_manifest.json', {'plan_sha256': sha((FROZEN / 'plan.json').read_bytes()), 'query_count': 26,
        'new_forward_count_at_freeze': 0, 'model_weights_loaded_at_freeze': False,
        'source_file_sha256': {f'{d}-{i:03d}': inputs[f'{d}-{i:03d}-no']['source_sha256'] for d, i in chosen},
        'input_lengths': {r['control_id']: r['input_token_count'] for r in controls},
        'builder_sha256': sha(Path(__file__).read_bytes())})
    print(json.dumps({'history_cases_reconstructed': 400, 'frozen_controls': 26, 'common_lengths': lengths,
        'length_matched_cross_pairs': sum(p['length_matched_within8'] for p in crossed_pairs),
        'plan_sha256': sha((FROZEN/'plan.json').read_bytes()), 'new_forward_count': 0}))


if __name__ == '__main__':
    main()
