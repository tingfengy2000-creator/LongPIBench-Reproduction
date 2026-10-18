"""Independent M2 numerical/input verification without new detector inference."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(ROOT))
from prepare import sha,ih,write


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['smoke','full'],required=True);args=ap.parse_args()
    plan=json.loads((ROOT/'plan.json').read_text())
    receipt=json.loads((ROOT/(args.phase+'_receipt.json')).read_text())
    raw=Path(receipt['observations_path'])
    assert sha(raw)==receipt['observations_sha256']
    inputs=[json.loads(x) for x in (REPO/plan['frozen_inputs_path']).read_text().splitlines()]
    indexed={(r['source_id'],r['label']):r for r in inputs}
    observations=[json.loads(x) for x in raw.read_text().splitlines()]
    assert len(observations)==receipt['n_variants']
    seen=set();maxerror=0.;n=0;negative=0
    for r in observations:
        key=r['source_id'],r['label'];assert key not in seen;seen.add(key);inp=indexed[key]
        allforward=[]
        for cond,d in r['official'].items():
            full=[1]+inp['core_token_ids']+[2] if cond=='core_reference' else inp['documents'][cond]['input_ids']
            assert sum([c['input_token_ids'] for c in d['chunks']],[])==full
            assert d['input_sha256']==ih(full)
            assert int(any(c['risk_score']>=.5 for c in d['chunks']))==d['official_prediction']==d['prediction']
            assert d['risk_score']==max(c['risk_score'] for c in d['chunks'])
            if cond!='core_reference':assert len(full)==1024 and all(len(c['input_token_ids'])==512 for c in d['chunks'])
            lo,hi=d['core_token_range'];assert full[lo:hi]==inp['core_token_ids']
            allforward+=d['chunks']
        shadow=r['shadow'];full=inp['documents']['B_cross']['input_ids']
        assert shadow['whole_input_sha256']==ih(full)
        assert sum([c['input_token_ids'] for c in shadow['chunks']],[])==full
        assert [len(c['input_token_ids']) for c in shadow['chunks']]==[256,512,256]
        assert shadow['prediction']==int(max(c['risk_score'] for c in shadow['chunks'])>=.5)
        allforward+=shadow['chunks']
        for cond,d in r['recovery'].items():
            assert d['input_token_ids']==inp['recovery_inputs'][cond]
            if cond.startswith('matched512'):assert len(d['input_token_ids'])==512
            allforward.append(d)
        # Matched512 keeps the shared truncated suffix at the EXACT same local
        # indices, not only the same total length and CLS/SEP layout.
        suffix_len=len(inp['core_token_ids'])-inp['core_cut']+1
        for c in ['matched512_partial16','matched512_full']:
            assert r['recovery'][c]['input_token_ids'][-suffix_len:]==r['recovery']['matched512_truncated']['input_token_ids'][-suffix_len:]
        for cond,d in r['controls'].items():
            if cond.startswith('global'):
                ref=r['official']['core_reference']['chunks'][0]
                assert d['input_token_ids']==ref['input_token_ids'] and d['logits']==ref['logits'];negative+=1
            else:assert d['input_token_ids']==inp['control_inputs'][cond]
            allforward.append(d)
        assert Counter(r['controls']['local16']['input_token_ids'])==Counter(r['controls']['local192']['input_token_ids'])
        # Equal-length replacement changes exactly one token, preserving core index.
        for condition,index in [('replace_cls',0),('replace_sep',511)]:
            a=r['controls']['local16']['input_token_ids'];b=r['controls'][condition]['input_token_ids']
            assert len(a)==len(b)==512 and [i for i,(x,y) in enumerate(zip(a,b)) if x!=y]==[index]
        for d in allforward:
            ids=d['input_token_ids'];assert len(ids)<=512 and d['input_sha256']==ih(ids)
            logits=d['logits'];z=[math.exp(x-max(logits)) for x in logits];p=[x/sum(z) for x in z]
            value=max(p[1:]);error=abs(value-d['risk_score']);maxerror=max(maxerror,error)
            assert error<2e-7 and int(d['risk_score']>=.5)==d['prediction']
            assert abs(max(d['softmax'][1:])-d['risk_score'])<1e-10
            n+=1
    assert n==receipt['forward_calls']
    assert {s for s,_ in seen}==set(plan['smoke_sources']) if args.phase=='smoke' else len(seen)==80
    numerical=[]
    if args.phase=='full':
        import csv
        summary=json.loads((ROOT/'analysis_summary.json').read_text())
        for m in summary['official_overall']:
            records=[r for r in observations]
            preds=[(r['label'],r['official'][m['condition']]['prediction']) for r in records]
            expected={'tp':sum(l==1 and p==1 for l,p in preds),'fp':sum(l==0 and p==1 for l,p in preds),
                'tn':sum(l==0 and p==0 for l,p in preds),'fn':sum(l==1 and p==0 for l,p in preds)}
            assert all(m[k]==v for k,v in expected.items())
        comps=json.loads((ROOT/'paired_comparisons.json').read_text())
        for c in comps:
            k=c['negative_to_positive'];j=c['positive_to_negative'];discordant=k+j
            p=min(1.,2*sum(math.comb(discordant,i) for i in range(min(k,j)+1))/2**discordant) if discordant else 1.
            assert abs(p-c['mcnemar_exact_p'])<1e-12
        for name in ['03_official_chunk_results.csv','04_shadow_chunk_results.csv','05_context_recovery_results.csv']:
            with (ROOT/name).open() as f:count=sum(1 for _ in csv.DictReader(f))
            numerical.append({'file':name,'rows':count})
        assert numerical[0]['rows']==320 and numerical[1]['rows']==160 and numerical[2]['rows']==480
    seal=json.loads((ROOT/'frozen_existing_files.json').read_text())['file_sha256']
    assert all(sha(REPO/name)==h for name,h in seal.items())
    out={'status':'PASS','verified_utc':datetime.now(timezone.utc).isoformat(),'phase':args.phase,
        'n_sources':len({r['source_id'] for r in observations}),'variants':len(observations),'forward_records':n,
        'max_python64_vs_fp32_risk_error':maxerror,'exact_negative_control_reexecutes':negative,
        'matched512_shared_suffix_positions_identical':True,
        'history_hashes_unchanged':len(seal),'table_counts':numerical,'raw_sha256':sha(raw),
        'checks':['Raw input IDs/hash and <=512 limit','Complete ordered fixed-token shadow coverage',
            'Official Max/early-exit equivalence','Source-paired input labels and frozen core coverage',
            '512-length controls with one token change only','Exact negative-control logits',
            'Independent softmax risk and confusion counts','Combinatorial exact McNemar','Historical hashes']}
    write(ROOT/('verification_'+args.phase+'.json'),out)
    print(json.dumps(out,indent=2))


if __name__=='__main__':main()
