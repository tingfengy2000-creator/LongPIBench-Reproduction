"""Frozen exploratory collection contract. Imports no model or network runtime."""
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'stage_b0'))
from ai_review_v2.label_gate import require_exploratory_label_freeze
from evaluation import native_windows, validate_rows

PLAN = ROOT/'stage_b0/scoring_v2/execution_plan.json'


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def save(path, value):
    with Path(path).open('x', encoding='utf8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n')


def token_hash(ids):
    return hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest()


def load_inputs():
    plan = json.loads(PLAN.read_text(encoding='utf8'))
    for name, digest in plan['file_sha256'].items():
        assert sha(ROOT/name) == digest, 'Frozen input/code differs: '+name
    assert plan['status'] == 'FROZEN_EXPLORATORY_COLLECTION_NOT_STARTED'
    rows = require_exploratory_label_freeze(ROOT/'stage_b0', ROOT/plan['label_freeze'])
    # Validate the source grouping without silently converting unknown labels.
    if all(r['label'] in (0, 1) for r in rows):
        validate_rows(rows)
    assert len(rows) == 400 and len({r['source_document_id'] for r in rows}) == 80
    return plan, sorted(rows, key=lambda r: r['sample_id'])


def parse_llm(text, document, ended_with_eos):
    """Strict JSON only; no fences, substring extraction, repairs or guesses."""
    if not ended_with_eos:
        return None, 'INVALID_GENERATION_LIMIT'
    def unique_keys(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError('Duplicate JSON key')
            obj[key] = value
        return obj
    try:
        obj = json.loads(text, object_pairs_hook=unique_keys)
    except (ValueError, TypeError):
        return None, 'INVALID_JSON'
    if not isinstance(obj, dict) or set(obj) != {'label', 'role', 'evidence'}:
        return None, 'INVALID_SCHEMA'
    if type(obj['label']) is not int or obj['label'] not in (0, 1):
        return None, 'INVALID_LABEL'
    if (obj['label'] == 1 and obj['role'] != 'attack') or (obj['label'] == 0 and obj['role'] not in ['data', 'quotation']):
        return None, 'INVALID_ROLE'
    if not isinstance(obj['evidence'], str) or obj['evidence'] not in document:
        return None, 'INVALID_EVIDENCE'
    if obj['role'] != 'data' and not obj['evidence']:
        return None, 'INVALID_EMPTY_EVIDENCE'
    return obj, 'VALID'


def document_fields(row):
    result = {k: row[k] for k in ['sample_id', 'source_document_id', 'domain', 'split', 'variant', 'text_sha256', 'label']}
    result['label_basis'] = 'EXPLORATORY_AI_REVIEW_NOT_HUMAN_GOLD'
    return result


def classifier_score(probabilities):
    assert len(probabilities) in (2, 3) and all(math.isfinite(p) for p in probabilities)
    return max(probabilities[1:])


def eos_ids(config):
    value = config.eos_token_id
    return set(value if isinstance(value, (list, tuple)) else [value])
