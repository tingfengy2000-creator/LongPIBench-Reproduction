"""Record original detector prefix, then shadow-score unseen suffix chunks.

The original predict implementation and its early-exit label are untouched.
Extra suffix forwards support offline aggregators and are separately identified.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from prepare_samples import build, sha


def original_score(softmax, id2label):
    return max((softmax[int(i)] for i, label in id2label.items()
                if str(label).upper() not in {'BENIGN', 'SAFE', 'LABEL_0'}), default=softmax[-1])


def capture(detector, text):
    torch = detector.torch
    encoded = detector.tokenizer(text, add_special_tokens=True, truncation=False)['input_ids']
    chunks = [encoded[i:i+detector.chunk_tokens] for i in range(0, len(encoded), detector.chunk_tokens)]
    outputs = []
    def hook(model, args, kwargs, result):
        ids = kwargs['input_ids'][0].detach().cpu().tolist()
        logits = result.logits[0]
        probabilities = torch.softmax(logits, dim=-1).detach().cpu().tolist()
        index = len(outputs)
        assert ids == chunks[index], 'Observed original chunk differs from documented slicing'
        score = original_score(probabilities, model.config.id2label)
        assert math.isfinite(score) and all(math.isfinite(v) for v in logits.tolist())
        outputs.append({'start_token': index*detector.chunk_tokens,
            'end_token': min((index+1)*detector.chunk_tokens, len(encoded)), 'score': score,
            'logits': logits.detach().cpu().tolist(), 'softmax': probabilities,
            'input_token_sha256': hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
            'first_token_id': ids[0], 'last_token_id': ids[-1]})
    handle = detector.model.register_forward_hook(hook, with_kwargs=True)
    started = time.perf_counter()
    try:
        original_prediction = detector.predict(text)
        original_seconds = time.perf_counter() - started
        prefix = len(outputs)
        shadow_started = time.perf_counter()
        with torch.inference_mode():
            for ids in chunks[prefix:]:
                detector.model(input_ids=torch.tensor([ids], device=detector.device))
        shadow_seconds = time.perf_counter() - shadow_started
    finally:
        handle.remove()
    assert len(outputs) == len(chunks) > 0
    assert int(any(c['score'] >= detector.threshold for c in outputs)) == original_prediction
    for i, row in enumerate(outputs):
        row['evaluation_path'] = 'official_predict_prefix' if i < prefix else 'shadow_suffix_same_forward'
    return {'token_count': len(encoded), 'chunk_count': len(chunks),
        'chunk_scores': [c['score'] for c in outputs], 'chunks': outputs,
        'official_prediction': original_prediction, 'official_threshold': detector.threshold,
        'official_evaluated_chunks': prefix, 'shadow_suffix_chunks': len(chunks)-prefix,
        'official_max_equivalence_verified': True,
        'seconds_original_with_recording': original_seconds, 'seconds_shadow_suffix': shadow_seconds}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--detector', choices=['deberta', 'distilbert', 'prompt-guard'], required=True)
    parser.add_argument('--model-dir', type=Path)
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_IMPLICIT_TOKEN='1')
    import torch
    torch.set_num_threads(args.threads)
    records, cases = build()
    archived = [json.loads(v) for v in (ROOT/'sample_manifest.jsonl').read_text().splitlines()]
    assert records == archived
    module = importlib.import_module('longpibench.detectors')
    meta = json.loads((ROOT/'source_audit'/f'{args.detector}.json').read_text(encoding='utf-8'))
    model_dir = args.model_dir or ROOT/'models'/args.detector
    if not args.model_dir:
        verified = json.loads((ROOT/'source_audit'/f'{args.detector}-download.json').read_text())
        assert verified['revision'] == meta['sha']
        for row in verified['files']:
            assert sha(model_dir/row['filename']) == row['sha256']
    folder = ROOT/'results'/args.detector
    folder.mkdir(parents=True, exist_ok=False)
    manifest = {'status':'STARTED', 'is_formal_paper_experiment':False,
        'run_started_utc':datetime.now(timezone.utc).isoformat(), 'hostname':platform.node(),
        'python':sys.version, 'input_commit':subprocess.check_output(['git','-C',str(ROOT.parent),'rev-parse','HEAD']).decode().strip(),
        'model_repo':meta['id'], 'model_revision':meta['sha'], 'sample_manifest_sha256':sha(ROOT/'sample_manifest.jsonl'),
        'original_detectors_sha256':sha(ROOT.parent/'upstream/LongPIBench/longpibench/detectors.py'),
        'adapter_sha256':sha(__file__), 'threads':args.threads, 'dtype':'original_from_pretrained_default',
        'chunk_tokens':512, 'threshold':0.5, 'suffix_policy':'Separate shadow forwards; do not alter official early exit',
        'runtime':{k:importlib.metadata.version(k) for k in ['torch','transformers','tokenizers','numpy','safetensors','sentencepiece']}}
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    detector = module.TransformerDetector(str(model_dir), threshold=0.5, chunk_tokens=512)
    runtime = {'tokenizer_class':type(detector.tokenizer).__name__, 'tokenizer_model_max_length':detector.tokenizer.model_max_length,
        'architecture_max_position_embeddings':detector.model.config.max_position_embeddings,
        'id2label':detector.model.config.id2label, 'device':str(detector.device),
        'dtype':str(next(detector.model.parameters()).dtype),
        'parameters':sum(p.numel() for p in detector.model.parameters())}
    with (folder/'pilot_real_scores.jsonl').open('x',encoding='utf-8') as stream:
        for i,(record,case) in enumerate(cases,1):
            captured = capture(detector,case['data_prompt'])
            captured.update(record, model_repo=meta['id'], model_revision=meta['sha'], detector=args.detector,
                score_type='max_of_selected_class_softmax_components_not_calibrated_attack_probability')
            stream.write(json.dumps(captured,ensure_ascii=False,allow_nan=False)+'\n'); stream.flush()
            print(json.dumps({'detector':args.detector,'done':i,'sample_id':record['sample_id'],
                'tokens':captured['token_count'],'chunks':captured['chunk_count'],
                'official_prediction':captured['official_prediction']}),flush=True)
    completion = dict(manifest,status='REAL_SCORES_COLLECTED', runtime_model=runtime,
        n_documents=80, n_independent_sources=40,
        scores_sha256=sha(folder/'pilot_real_scores.jsonl'), finished_utc=datetime.now(timezone.utc).isoformat())
    (folder/'completion.json').write_text(json.dumps(completion,indent=2)+'\n')


if __name__ == '__main__':
    main()
