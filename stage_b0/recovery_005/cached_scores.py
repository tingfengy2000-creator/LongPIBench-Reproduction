"""Machine checks of existing800 raw scores; no forwards, metrics or fitting."""
import json
import math
import os
from pathlib import Path, PurePosixPath
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'stage_b0/scoring_v2'))
from common import document_fields, native_windows, sha, token_hash
from review_004 import RECEIPT


def check_chunk(chunk, labels):
    logits = chunk['raw_logits']; probs = chunk['class_softmax']
    assert len(logits) == len(probs) == len(labels)
    assert all(math.isfinite(v) for v in logits+probs)
    total = sum(math.exp(v-max(logits)) for v in logits)
    reconstructed = [math.exp(v-max(logits))/total for v in logits]
    assert all(abs(a-b) <= 1e-6 for a, b in zip(reconstructed, probs)), 'Softmax/logit mismatch'
    assert chunk['score'] == max(probs[1:]), 'Risk score differs from frozen Max rule'
    assert chunk['native_argmax_label'] == labels[max(range(len(logits)), key=lambda i: logits[i])]


def safe_file(root, relative):
    path = (root/relative).resolve(strict=True)
    assert path.is_relative_to(root.resolve()), 'Raw manifest path escapes source directory'
    return path


def allowed_model_target(path):
    physical = PurePosixPath(str(path))
    return physical.is_absolute() and '..' not in physical.parts and any(physical.is_relative_to(PurePosixPath(d)) for d in ['/mnt/e', '/mnt/d'])


def model_file(root, name):
    assert PurePosixPath(name).name == name, 'Expected pinned single-file model name'
    # HF snapshot symlinks legitimately resolve to sibling hub/blobs, not inside snapshot.
    target = (root/name).resolve(strict=True)
    assert allowed_model_target(target), 'Model link resolves outside D/E'
    return target


def verify_cached(rows, plan):
    state = json.loads((RECEIPT/'collection_run.json').read_text(encoding='utf8'))
    old_job = Path(state['raw_directory']).resolve(strict=True)
    assert old_job.is_relative_to(Path('/mnt/e')) or old_job.is_relative_to(Path('/mnt/d'))
    # Verify all source-manifest bytes, not merely filenames or receipt counts.
    for name, digest in state['raw_manifest_sha256'].items():
        assert sha(safe_file(old_job, name)) == digest, 'Previous raw changed: '+name
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    from transformers import AutoTokenizer
    checked = {}
    for role in ['piguard', 'prompt_guard_1']:
        manifest = json.loads((RECEIPT/(role+'_collection.json')).read_text(encoding='utf8'))
        model_dir = Path(manifest['model_directory']).resolve(strict=True)
        assert model_dir.is_relative_to(Path('/mnt/e')) or model_dir.is_relative_to(Path('/mnt/d'))
        for f in plan['classifiers'][role]['files']:
            p = model_file(model_dir, f['name'])
            assert p.stat().st_size == f['bytes'] and sha(p) == f['sha256']
        tok = AutoTokenizer.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False, token=False)
        labels = ['BENIGN', 'INJECTION', 'JAILBREAK'] if role == 'prompt_guard_1' else ['benign', 'injection']
        n = 0
        for row in rows:
            name = row['sample_id']+'-'+role+'.json'
            path = safe_file(old_job/role, name)
            assert sha(path) == manifest['raw_file_sha256'][name]
            record = json.loads(path.read_text(encoding='utf8'))
            assert all(record[k] == v for k, v in document_fields(row).items())
            assert record['role'] == role and record['validity'] == 'VALID'
            ids, windows = native_windows(tok, row['text'])
            assert record['token_count'] == len(ids) and record['chunk_count'] == len(windows) == len(record['chunks'])
            for w, chunk in zip(windows, record['chunks']):
                assert [chunk['start_token'], chunk['end_token']] == [w['start_token'], w['end_token']]
                assert chunk['input_token_ids'] == w['input_ids'] and chunk['attention_mask'] == w['attention_mask']
                assert chunk['input_sha256'] == token_hash(w['input_ids'])
                check_chunk(chunk, labels)
            assert record['score'] == max(c['score'] for c in record['chunks'])
            assert record['default_prediction'] == int(record['score'] >= .5)
            n += 1
        assert n == 400
        checked[role] = {'records': n, 'source_completion_sha256': sha(RECEIPT/(role+'_collection.json')),
                         'hash_input_token_coverage_and_score_arithmetic_checked': True}
    return {'status': 'CACHED800_RAW_MACHINE_VERIFIED_NO_RERUN', 'source_job': str(old_job), 'roles': checked,
            'n': 800, 'model_forward_calls': 0, 'thresholds_fitted': False, 'holdout_metrics_computed': False,
            'scope': 'Machine-only integrity/token/score-arithmetic checks, including holdout raw; no label-associated performance summaries displayed'}
