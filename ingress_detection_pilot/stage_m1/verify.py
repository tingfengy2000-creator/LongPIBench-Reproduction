"""Independent arithmetic/lineage cross-check, without any model forwards."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]


def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def read(p):return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()]


def main():
    plan=json.loads((ROOT/'plan.json').read_text())
    assert sha(ROOT/'sources_and_conditions.jsonl')==plan['sources_sha256']
    results=json.loads((ROOT/'mechanism_results.json').read_text())
    raw=ROOT/'raw'/plan['run_id']
    src=read(ROOT/'sources_and_conditions.jsonl')
    formats=read(raw/'format_observations.jsonl');docs=read(raw/'document_observations.jsonl')
    allchunks=formats+[c for d in docs for c in d['chunks']]
    maxerror=0.
    for r in allchunks:
        ids=r['input_token_ids']
        h=hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest()
        assert h==r.get('canonical_input_sha256',r.get('input_sha256'))
        logits=r['logits'];peak=max(logits)
        ex=[math.exp(v-peak) for v in logits];probs=[v/sum(ex) for v in ex]
        expected=max(probs[1],probs[2]);observed=r.get('risk_score',r.get('score'))
        maxerror=max(maxerror,abs(expected-observed))
        assert abs(expected-observed)<1e-7
        assert abs(max(r['softmax'][1:])-observed)<1e-10
    for s in src:
        sid=s['source_id'];core=s['core_token_ids']
        observed={r['condition']:r for r in formats if r['source_id']==sid and r['condition']!='position_negative_control'}
        assert observed['both_special']['input_token_ids']==[1]+core+[2]
        assert observed['tail_sep_only']['input_token_ids']==core+[2]
        for r in formats:
            if r['source_id']==sid and r['condition']=='position_negative_control':
                assert r['input_token_ids']==observed['both_special']['input_token_ids']
                assert r['logits']==observed['both_special']['logits']
        for condition,doc in s['documents'].items():
            r=next(d for d in docs if d['source_id']==sid and d['condition']==condition)
            concatenated=sum([c['input_token_ids'] for c in r['chunks']],[])
            assert concatenated==doc['input_ids']
            assert concatenated[doc['core_start_token']:doc['core_end_token']]==core
            assert int(any(c['score']>=.5 for c in r['chunks']))==r['official_prediction']
    deltas=list(csv.DictReader((ROOT/'paired_differences.csv').open()))
    for condition,res in results['format_contrasts'].items():
        values=[float(r['delta']) for r in deltas if r['condition']==condition]
        assert len(values)==24 and abs(statistics.median(values)-res['median_delta'])<1e-12
        pos=sum(x>1e-8 for x in values);neg=sum(x< -1e-8 for x in values)
        p=min(1.,2*sum(math.comb(pos+neg,i) for i in range(min(pos,neg)+1))/2**(pos+neg))
        assert abs(p-res['two_sided_sign_p'])<1e-12
    seal=json.loads((ROOT/'frozen_existing_files.json').read_text())['file_sha256']
    assert all(sha(REPO/n)==h for n,h in seal.items())
    output={'status':'PASS','historical_files_unchanged':len(seal),'new_sources':len(src),
        'format_records':len(formats),'document_records':len(docs),'raw_forward_records_checked':len(allchunks),
        'python64_softmax_vs_recorded_fp32_max_error':maxerror,
        'checks':['Input hashes and all token IDs','Fixed core coverage in official text witnesses','Negative-control exact logits',
            'Independent softmax/official risk recomputation','Original document Max >=0.5 equivalence',
            'Independent paired median and exact sign probabilities','All historical tracked hashes'],
        'paper_confirmatory':False}
    with (ROOT/'verification.json').open('x',encoding='utf-8') as f:json.dump(output,f,indent=2);f.write('\n')
    print(json.dumps(output,indent=2))


if __name__=='__main__':main()
