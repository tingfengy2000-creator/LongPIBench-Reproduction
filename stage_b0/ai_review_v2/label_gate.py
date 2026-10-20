"""Exploratory-only gate. No human-signoff fabrication or null-as-benign fallback."""
import hashlib
import json
from pathlib import Path
import sys

BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE))
from review_io import public_cases,validate_records,read_jsonl,validate_metadata


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def second_review_required(rows,cursor,mapping):
    lookup={r['sample_id']:r for r in rows}
    reviews={r['review_id']:r for r in cursor}
    needed={r['review_id'] for r in mapping if r['fixed_second_review_required']}
    for m in mapping:
        review=reviews[m['review_id']]
        if review['ai_label']!=lookup[m['sample_id']]['label'] or review['ambiguity'] or review['confidence']=='low':
            needed.add(m['review_id'])
    return needed


def require_exploratory_label_freeze(pilot,freeze_file):
    pilot=Path(pilot);freeze_file=Path(freeze_file)
    if not freeze_file.is_file():raise RuntimeError('STOP: AI review is authorized but the exploratory label freeze is not complete')
    freeze=json.loads(freeze_file.read_text(encoding='utf8'))
    assert freeze['status']=='EXPLORATORY_AI_LABELS_FROZEN'
    assert freeze['is_formal_paper_experiment'] is False and freeze['human_review_complete'] is False
    assert freeze['dataset_manifest_sha256']==sha(pilot/'dataset_manifest.jsonl')
    assert freeze['policy_sha256']==sha(BASE/'POLICY.md')
    assert freeze['detector_outputs_used_for_labeling'] is False
    packet_lock=json.loads((BASE/'packet_freeze.json').read_text(encoding='utf8'))
    assert packet_lock['candidate_manifest_sha256']==sha(pilot/'dataset_manifest.jsonl')
    assert packet_lock['policy_sha256']==sha(BASE/'POLICY.md')
    assert packet_lock['prompt_sha256']==sha(BASE/'review_prompt.md')
    assert packet_lock['private_mapping_sha256']==sha(BASE/'private_mapping.json')
    for name,digest in packet_lock['packet_file_sha256'].items():
        assert sha(pilot.parent/name)==digest
    # All source files must be within the reviewed checkout, not arbitrary files.
    root=pilot.parent.resolve()
    def source(name):
        path=(root/name).resolve(strict=True)
        assert path.is_relative_to(root)
        assert sha(path)==freeze['review_file_sha256'][name]
        return path
    cursor=read_jsonl(source(freeze['cursor_reviews']))
    validate_records(cursor,public_cases('cursor'))
    validate_metadata(json.loads(source(freeze['cursor_metadata']).read_text(encoding='utf8')),'cursor')
    secondary=read_jsonl(source(freeze['secondary_reviews']))
    validate_metadata(json.loads(source(freeze['secondary_metadata']).read_text(encoding='utf8')),'secondary')
    cases=public_cases('cursor')
    validate_records(secondary,cases,complete=False)
    rows=read_jsonl(pilot/'dataset_manifest.jsonl')
    mapping=json.loads((BASE/'private_mapping.json').read_text(encoding='utf8'))
    assert len(mapping)==400 and len({m['sample_id'] for m in mapping})==400
    assert {m['review_id'] for m in mapping}==set(cases)
    assert {m['sample_id'] for m in mapping}=={r['sample_id'] for r in rows}
    needed=second_review_required(rows,cursor,mapping)
    sec={r['review_id']:r for r in secondary}
    assert needed<=set(sec),'Required second reviews missing'
    first={r['review_id']:r for r in cursor}
    adjudicated=read_jsonl(source(freeze['adjudicated_labels']))
    assert len(adjudicated)==400 and len({r['review_id'] for r in adjudicated})==400
    final={r['review_id']:r for r in adjudicated}
    effective={}
    for m in mapping:
        rid=m['review_id'];a=first[rid];b=sec.get(rid)
        value=a['ai_label']
        status='AI_SINGLE_REVIEW_PROVISIONAL'
        if rid in needed or b:
            if a['ai_label'] is not None and b['ai_label']==a['ai_label']:
                value=a['ai_label'];status='AI_AGREEMENT_PROVISIONAL'
            else:value=None;status='UNRESOLVED'
        assert final[rid]['effective_label']==value and final[rid]['status']==status
        assert final[rid]['text_sha256']==m['text_sha256']
        effective[m['sample_id']]=value
    for r in rows:
        r['proposed_label']=r['label'];r['label']=effective[r['sample_id']]
        r['label_basis']='EXPLORATORY_AI_REVIEW_NOT_HUMAN_GOLD'
    return rows
