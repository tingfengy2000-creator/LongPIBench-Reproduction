"""Validate visible AI review records against blind public packets, without gold labels."""
import argparse
import hashlib
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]


def read_jsonl(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf8').splitlines() if s.strip()]


def public_cases(channel):
    manifest=json.loads((BASE/f'packets/{channel}/packet_manifest.json').read_text(encoding='utf8'))
    output={}
    for batch in manifest['batches']:
        path=ROOT/batch['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==batch['sha256']
        for r in read_jsonl(path):
            assert r['review_id'] not in output
            output[r['review_id']]=r
    assert len(output)==manifest['n']
    return output


def validate_records(records,cases,complete=True):
    ids=[r['review_id'] for r in records]
    assert len(set(ids))==len(ids),'Duplicate review ID'
    assert set(ids)<=set(cases),'Unknown review ID'
    if complete:assert set(ids)==set(cases),'Missing review IDs'
    for r in records:
        c=cases[r['review_id']]
        assert r['text_sha256']==c['text_sha256'],'Text hash mismatch'
        assert r['ai_label'] is None or type(r['ai_label']) is int and r['ai_label'] in (0,1)
        assert r['role'] in ['data','quotation','attack','uncertain']
        assert type(r['ambiguity']) is bool
        assert r['confidence'] in ['high','medium','low']
        assert isinstance(r['reason'],str) and 12<=len(r['reason'])<=1500,'Need concise case-specific visible rationale'
        quote=r['evidence'];assert isinstance(quote,str) and len(quote)<=600
        assert quote in c['untrusted_document'],'Evidence must be an exact substring'
        if r['role']!='data':assert quote,'Need evidence for quotation, attack or uncertain'
        if r['ai_label'] is None:assert r['role']=='uncertain' and r['ambiguity'] is True
        elif r['ai_label']==1:assert r['role']=='attack'
        else:assert r['role'] in ['data','quotation']
    return {'n':len(records),'n_uncertain':sum(r['ai_label'] is None for r in records),
            'n_ambiguous':sum(r['ambiguity'] for r in records),'complete':set(ids)==set(cases)}


def validate_metadata(meta,channel):
    assert meta['channel']==channel
    assert meta['annotation_type']=='AI_NOT_HUMAN'
    for key in ['reviewer_entrypoint','model_name','model_version','model_version_evidence','execution_mode']:
        assert isinstance(meta[key],str) and meta[key].strip(),key
    assert meta['detector_scores_seen'] is False,'Do not use baseline predictions to determine labels'
    for key in ['proposed_labels_seen','other_reviewer_labels_seen']:
        assert type(meta[key]) is bool,key
    assert meta['human_review_performed'] is False
    return {'blindness_declared':not(meta['proposed_labels_seen'] or meta['other_reviewer_labels_seen']),
            'exact_model_known':meta['model_name']!='unknown' and meta['model_version']!='unknown'}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--channel',choices=['cursor','secondary'],required=True)
    ap.add_argument('--reviews',type=Path,required=True)
    ap.add_argument('--metadata',type=Path,required=True)
    ap.add_argument('--allow-partial',action='store_true')
    args=ap.parse_args()
    result=validate_records(read_jsonl(args.reviews),public_cases(args.channel),not args.allow_partial)
    result.update(validate_metadata(json.loads(args.metadata.read_text(encoding='utf8')),args.channel))
    result['status']='AI_REVIEW_SCHEMA_AND_COVERAGE_VALID_NOT_LABEL_TRUTH_VALIDATION'
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
