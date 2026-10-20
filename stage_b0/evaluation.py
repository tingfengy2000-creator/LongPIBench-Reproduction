"""Frozen statistical primitives, label gate and native all-token coverage.

No model loads, no data-dependent model selection, no algorithm training.
"""
from __future__ import annotations
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_rows(rows):
    assert len(rows)==400 and len({r['sample_id'] for r in rows})==400
    for key in ['source_document_id','source_template_family','variant_template_family']:
        mapping=defaultdict(set)
        for r in rows:mapping[r[key]].add(r['split'])
        assert all(len(v)==1 for v in mapping.values()),f'{key} split leakage'
    assert len({r['source_document_id'] for r in rows})==80
    for r in rows:
        assert r['label'] in (0,1)
        assert hashlib.sha256(r['text'].encode()).hexdigest()==r['text_sha256']


def require_human_signoff(directory):
    directory=Path(directory)
    sign=directory/'human_signoff.json'
    if not sign.is_file():raise RuntimeError('STOP: 400 candidate labels have not been signed by the human reviewer')
    obj=json.loads(sign.read_text(encoding='utf8'))
    if not (obj.get('approved_by_human') is True and obj.get('reviewer') and obj.get('authorization_evidence')):
        raise RuntimeError('STOP: human signoff lacks reviewer or explicit authorization evidence')
    for field,path in [('dataset_manifest_sha256','dataset_manifest.jsonl'),('protocol_sha256','protocol_v1.md'),('reviewed_labels_sha256','human_reviewed_labels.jsonl')]:
        if obj.get(field)!=file_sha(directory/path):raise RuntimeError(f'STOP: signoff {field} differs')
    rows=[json.loads(line) for line in (directory/'dataset_manifest.jsonl').read_text(encoding='utf8').splitlines() if line.strip()]
    validate_rows(rows)
    labels=[json.loads(line) for line in (directory/'human_reviewed_labels.jsonl').read_text(encoding='utf8').splitlines() if line.strip()]
    assert len(labels)==400 and len({r['sample_id'] for r in labels})==400
    reviewed={r['sample_id']:r for r in labels}
    for r in rows:
        label=reviewed[r['sample_id']]
        assert label['human_label']==r['label'] and label['text_sha256']==r['text_sha256']
        assert label.get('reviewer') and label.get('review_status')=='APPROVED'
    return rows


def native_windows(tokenizer,text,max_total=512):
    """Half-open source token ranges; specials are outside those coordinates."""
    source_ids=tokenizer(text,add_special_tokens=False,truncation=False)['input_ids']
    special_count=tokenizer.num_special_tokens_to_add(pair=False)
    capacity=max_total-special_count
    assert capacity>0
    chunks=[]
    for start in range(0,len(source_ids),capacity):
        end=min(start+capacity,len(source_ids))
        original=source_ids[start:end]
        packed=tokenizer.prepare_for_model(original,add_special_tokens=True,truncation=False,
                                          return_attention_mask=True,return_special_tokens_mask=True)
        assert len(packed['input_ids'])<=max_total
        restored=[i for i,m in zip(packed['input_ids'],packed['special_tokens_mask']) if m==0]
        assert restored==original
        chunks.append({'start_token':start,'end_token':end,'input_ids':packed['input_ids'],
                       'attention_mask':packed['attention_mask'],'source_token_ids':original})
    assert source_ids and chunks
    assert [i for c in chunks for i in c['source_token_ids']]==source_ids
    return source_ids,chunks


def threshold_for_fpr(clean_scores,alpha):
    """score>=threshold; lowest representable cutoff respecting all tied negatives."""
    assert clean_scores and 0<alpha<1 and all(math.isfinite(v) for v in clean_scores)
    vals=sorted(clean_scores,reverse=True)
    allowed=math.floor(alpha*len(vals))
    threshold=math.nextafter(vals[allowed],math.inf)
    assert sum(s>=threshold for s in vals)<=allowed
    return threshold


def cascade_threshold(attack_scores,recall=.95):
    assert attack_scores and all(math.isfinite(s) for s in attack_scores)
    required=math.ceil(recall*len(attack_scores)-1e-12)
    threshold=sorted(attack_scores,reverse=True)[required-1]
    assert sum(s>=threshold for s in attack_scores)>=required
    return threshold


def confusion(rows,score_key,threshold):
    tp=fp=tn=fn=0
    for r in rows:
        predicted=r[score_key]>=threshold
        if r['label']:tp+=int(predicted);fn+=int(not predicted)
        else:fp+=int(predicted);tn+=int(not predicted)
    return {'tp':tp,'fp':fp,'tn':tn,'fn':fn,'tpr':tp/(tp+fn) if tp+fn else None,
            'fpr':fp/(fp+tn) if fp+tn else None}


def auroc(rows):
    # Independent pairwise definition includes half credit for ties.
    positive=[r['score'] for r in rows if r['label']]
    negative=[r['score'] for r in rows if not r['label']]
    if not positive or not negative:return None
    return sum((a>b)+.5*(a==b) for a in positive for b in negative)/(len(positive)*len(negative))


def average_precision(rows):
    # Group all equal-score observations before evaluating precision/recall.
    total=sum(r['label'] for r in rows)
    if not total or total==len(rows):return None
    buckets=defaultdict(list)
    for r in rows:buckets[r['score']].append(r['label'])
    seen=tp=0;area=0.
    for score in sorted(buckets,reverse=True):
        group=buckets[score];added=sum(group);seen+=len(group);tp+=added
        area+=(added/total)*(tp/seen)
    return area
