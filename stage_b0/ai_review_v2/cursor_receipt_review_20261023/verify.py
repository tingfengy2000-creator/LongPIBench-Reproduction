"""Read-only checks of the actual Cursor annotation receipt, not model accuracy."""
import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent;ROOT=BASE.parents[1]
sys.path.insert(0,str(BASE))
from review_io import validate_records,public_cases,validate_metadata
from label_gate import second_review_required

COMMIT='2ed81a2cc5fb2caebf1659ab89e78811ee7940e1'
FOLDER='coordination/returns/20261020T153853Z-b0-cursor-label-review-83657036'


def check():
    def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
    assert git('rev-parse',COMMIT+'^').decode().strip()=='0f85b4f6316a8e33c3f7250e866a4e49c3cc6d5f'
    paths=sorted(f'{FOLDER}/{n}' for n in ['reviews.jsonl','reviewer_metadata.json','REPORT.md'])
    changes=git('diff','--name-status',COMMIT+'^',COMMIT).decode().splitlines()
    assert sorted(changes)==sorted('A\t'+p for p in paths)
    blobs={name:git('show',COMMIT+':'+name) for name in paths}
    for name,blob in blobs.items():assert (ROOT/name).read_bytes().replace(b'\r\n',b'\n')==blob.replace(b'\r\n',b'\n')
    reviews=[json.loads(l) for l in blobs[FOLDER+'/reviews.jsonl'].decode().splitlines() if l.strip()]
    meta=json.loads(blobs[FOLDER+'/reviewer_metadata.json'])
    structural=validate_records(reviews,public_cases('cursor'))
    declared_meta=validate_metadata(meta,'cursor')
    rows=[json.loads(l) for l in (ROOT/'stage_b0/dataset_manifest.jsonl').read_text(encoding='utf8').splitlines() if l.strip()]
    mapping=json.loads((BASE/'private_mapping.json').read_text(encoding='utf8'))
    proposed={r['sample_id']:r['label'] for r in rows}
    by_id={r['review_id']:r for r in reviews}
    agreement=sum(by_id[m['review_id']]['ai_label']==proposed[m['sample_id']] for m in mapping)
    needed=second_review_required(rows,reviews,mapping)
    assert len(needed)==120
    return {'status':'CURSOR_FIRST_REVIEW_RECEIPT_ACCEPTED_STRUCTURE_ONLY_SECOND_REVIEW_PENDING',
            'source_commit':COMMIT,'source_run_id':'20261020T153853Z-b0-cursor-label-review-83657036',
            'source_blob_sha256':{n:hashlib.sha256(b).hexdigest() for n,b in blobs.items()},
            'source_only_three_additions':True,'coverage':structural,
            'label_counts':{str(k):v for k,v in Counter(r['ai_label'] for r in reviews).items()},
            'role_counts':dict(Counter(r['role'] for r in reviews)),
            'confidence_counts':dict(Counter(r['confidence'] for r in reviews)),
            'nonempty_literal_evidence_checked':sum(bool(r['evidence']) for r in reviews),
            'proposed_label_agreement':agreement,'agreement_denominator':400,
            'agreement_is_accuracy':False,'second_review_required':len(needed),'second_review_received':0,
            'reviewer_declared_model':meta['model_name'],'reviewer_declared_version':meta['model_version'],
            'model_identity_evidence':meta['model_version_evidence'],
            'independent_model_build_verified':False,'blindness_declared_not_independently_proven':declared_meta['blindness_declared'],
            'independent_human_review':False,'coordinator_independent_semantic_review_of_all400':False,
            'B0_detector_scores_computed_in_this_review':0,'labels_frozen_for_scoring':False,
            'next_fixed_secondary_entrypoint':'Gemini per user selection 2026-10-23'}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--check-only',action='store_true');args=ap.parse_args()
    result=check();path=HERE/'verification.json'
    if args.check_only:assert json.loads(path.read_text(encoding='utf8'))==result
    else:
        with path.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(result['status']);print('400 unique records; same 120 mandatory second reviews; no detector evaluation.')


if __name__=='__main__':main()
