"""Four OFFLINE explanatory comparators, never imported by a detector runtime."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

ROOT=Path(__file__).resolve().parent
PILOT=ROOT.parent
METHODS=['global_max','domain_max','length_max','domain_length_max']
ALIASES=['deberta','distilbert','prompt-guard']


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def verify_seal():
    seal=json.loads((ROOT/'frozen_existing_files.json').read_text(encoding='utf-8'))
    repo=PILOT.parent
    for name,digest in seal['file_sha256'].items():assert sha(repo/name)==digest,f'Frozen evidence changed: {name}'
    return len(seal['file_sha256'])


def load(alias):
    rows=[json.loads(x) for x in (PILOT/'validation_v2/results'/alias/'pilot_real_scores.jsonl').read_text(encoding='utf-8').splitlines()]
    completion=json.loads((PILOT/'validation_v2/results'/alias/'completion.json').read_text(encoding='utf-8'))
    assert completion['scores_sha256']==sha(PILOT/'validation_v2/results'/alias/'pilot_real_scores.jsonl')
    assert len(rows)==320 and len({r['sample_id'] for r in rows})==320
    for row in rows:
        row['n_chunks']=row['chunk_count']
        row['maximum']=max(row['chunk_scores'])
    return rows


def threshold(values,alpha=.1):
    assert values and all(math.isfinite(v) for v in values)
    return math.nextafter(sorted(values,reverse=True)[math.floor(alpha*len(values))],math.inf)


def neighborhood(row,clean,method,loo=False):
    assert method in ['length_max','domain_length_max']
    refs=[c for c in clean if not (loo and c['sample_id']==row['sample_id'])
        and (method=='length_max' or c['domain']==row['domain'])]
    target=math.log1p(row['n_chunks'])
    refs=sorted(refs,key=lambda c:(abs(math.log1p(c['n_chunks'])-target),c['sample_id']))
    assert len(refs)>=28
    return refs[:28]


def score(row,method,clean,loo=False):
    if method in ['global_max','domain_max']:return row['maximum']
    refs=neighborhood(row,clean,method,loo)
    count=sum(c['maximum']>=row['maximum'] for c in refs)
    return -math.log10((1+count)/(1+len(refs)))


def fit(rows):
    clean=[r for r in rows if r['split']=='calibration' and r['label']==0]
    assert len(clean)==80 and all(sum(r['domain']==d for r in clean)==40 for d in ['email','resume'])
    output={}
    for method in METHODS:
        cuts={}
        for group in (['pooled'] if method in ['global_max','length_max'] else ['email','resume']):
            selected=[r for r in clean if group=='pooled' or r['domain']==group]
            values=[score(r,method,clean,True) for r in selected]
            cut=threshold(values)
            cuts[group]={'threshold':cut,'n_clean':len(selected),'fit_fp':sum(v>cut for v in values),
                'reference_sample_ids':[r['sample_id'] for r in selected]}
        output[method]=cuts
    return clean,output


def cutoff(fitted,method,domain):
    return fitted[method]['pooled' if method in ['global_max','length_max'] else domain]['threshold']


def confusion(labels,decisions):
    labels=np.asarray(labels);decisions=np.asarray(decisions,dtype=bool)
    tp=int(np.sum((labels==1)&decisions));fp=int(np.sum((labels==0)&decisions))
    tn=int(np.sum((labels==0)&~decisions));fn=int(np.sum((labels==1)&~decisions))
    return dict(tp=tp,fp=fp,tn=tn,fn=fn,tpr=tp/(tp+fn) if tp+fn else None,fpr=fp/(fp+tn) if fp+tn else None)


def curves(labels,values):
    labels=np.asarray(labels,dtype=int);values=np.asarray(values,dtype=float)
    pos=int(np.sum(labels==1));neg=int(np.sum(labels==0));assert pos and neg
    order=np.argsort(-values,kind='stable');x=values[order];y=labels[order]
    ends=np.r_[np.flatnonzero(x[:-1]!=x[1:]),len(x)-1]
    tp=np.cumsum(y)[ends];fp=(ends+1)-tp
    recall=tp/pos;fpr=fp/neg;precision=tp/(tp+fp)
    rocx=np.r_[0.,fpr];rocy=np.r_[0.,recall]
    auc=float(np.trapezoid(rocy,rocx))
    ap=float(np.sum(np.diff(np.r_[0.,recall])*precision))
    envelope=float(max(np.r_[0.,recall[fpr<=.1]]))
    return {'roc':[{'fpr':float(a),'tpr':float(b)} for a,b in zip(rocx,rocy)],
        'pr':[{'recall':0.,'precision':1.}]+[{'recall':float(a),'precision':float(b)} for a,b in zip(recall,precision)],
        'auroc':auc,'average_precision':ap,'empirical_tpr_envelope_fpr_le_10_percent':envelope,
        'n_positive':pos,'n_negative':neg,'attack_prevalence':pos/(pos+neg)}


def independently_check_curves(labels,values,observed):
    y=np.asarray(labels);v=np.asarray(values);n1=np.sum(y==1);n0=np.sum(y==0)
    rank_auc=(rankdata(v)[y==1].sum()-n1*(n1+1)/2)/(n1*n0)
    precisions=[np.mean(y[v>=s]) for s in v[y==1]]
    assert math.isclose(rank_auc,observed['auroc'],abs_tol=1e-12)
    assert math.isclose(float(np.mean(precisions)),observed['average_precision'],abs_tol=1e-12)


def bootstrap_delta(labels,a,b,repetitions=2000):
    # b-a; rows are unique source documents within each label/domain.
    labels=np.asarray(labels);a=np.asarray(a);b=np.asarray(b)
    generator=np.random.default_rng(20261018)
    positive=np.flatnonzero(labels==1);negative=np.flatnonzero(labels==0)
    differences=[]
    for _ in range(repetitions):
        selected=np.r_[generator.choice(positive,len(positive)),generator.choice(negative,len(negative))]
        first=curves(labels[selected],a[selected]);second=curves(labels[selected],b[selected])
        differences.append([second[k]-first[k] for k in ['auroc','average_precision','empirical_tpr_envelope_fpr_le_10_percent']])
    return {name:np.quantile(np.asarray(differences)[:,i],[.025,.975]).tolist()
        for i,name in enumerate(['auroc_delta_95','average_precision_delta_95','tpr_envelope_delta_95'])}


def association(x,y,permutations=3999):
    x=rankdata(x);y=rankdata(y)
    x=x-x.mean();y=y-y.mean();denom=np.linalg.norm(x)*np.linalg.norm(y)
    if not denom:return {'rho':None,'p':None,'n':len(x),'reason':'constant ranks'}
    rho=float(x@y/denom);generator=np.random.default_rng(20261018)
    extreme=sum(abs(float(x@generator.permutation(y)/denom))>=abs(rho)-1e-12 for _ in range(permutations))
    return {'rho':rho,'p':(1+extreme)/(permutations+1),'n':len(x),'permutations':permutations}


def blocked_token_association(rows):
    groups=[]
    for n in sorted({r['n_chunks'] for r in rows}):
        selected=[r for r in rows if r['n_chunks']==n]
        if len(selected)<3:continue
        x=rankdata([r['token_count'] for r in selected]);y=rankdata([r['maximum'] for r in selected])
        x=x-x.mean();y=y-y.mean()
        if np.linalg.norm(x) and np.linalg.norm(y):groups.append((x,y))
    if not groups:return {'rho':None,'p':None,'n_used':0,'n_available':len(rows),'reason':'insufficient within-chunk-count support'}
    denom=np.linalg.norm(np.concatenate([x for x,_ in groups]))*np.linalg.norm(np.concatenate([y for _,y in groups]))
    rho=float(sum(x@y for x,y in groups)/denom)
    generator=np.random.default_rng(20261018)
    extreme=sum(abs(float(sum(x@generator.permutation(y) for x,y in groups)/denom))>=abs(rho)-1e-12 for _ in range(3999))
    return {'rho':rho,'p':(1+extreme)/4000,'n_used':sum(len(x) for x,_ in groups),'n_available':len(rows),
        'n_blocks':len(groups),'statistic':'within-exact-chunk-count centered rank correlation; descriptive, not causal'}
