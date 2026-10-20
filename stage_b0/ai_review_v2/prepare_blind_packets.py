"""Create score-blind, label-blind packets for two external AI reviewers."""
import hashlib
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent
PILOT=BASE.parent


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def key(s):return hashlib.sha256(('b0-ai-review-v2-fixed-order:'+s).encode()).hexdigest()
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')


def main():
    rows=[json.loads(l) for l in (PILOT/'dataset_manifest.jsonl').read_text(encoding='utf8').splitlines()]
    assert len(rows)==400
    fixed_secondary={r['sample_id'] for r in rows if r['variant']=='hard_benign'}
    for domain in ['email','resume']:
        for variant in ['ordinary','authority_spoof','output_manipulation','private_context_exfiltration']:
            for split,n in [('development',2),('exploratory_holdout',3)]:
                pool=sorted([r for r in rows if r['domain']==domain and r['variant']==variant and r['split']==split],key=lambda r:key(r['sample_id']))
                fixed_secondary.update(r['sample_id'] for r in pool[:n])
    assert len(fixed_secondary)==120
    mapping=[];public=[]
    for r in rows:
        review_id='item-'+key(r['sample_id'])[:20]
        packet={'review_id':review_id,'trusted_task':r['trusted_task'],'untrusted_document':r['text'],'text_sha256':r['text_sha256']}
        assert not any(k in packet for k in ['label','variant','split','sample_id','domain'])
        public.append(packet)
        mapping.append({'review_id':review_id,'sample_id':r['sample_id'],'text_sha256':r['text_sha256'],
                        'fixed_second_review_required':r['sample_id'] in fixed_secondary})
    assert len({r['review_id'] for r in public})==400
    secondary_ids={r['review_id'] for r in mapping if r['fixed_second_review_required']}
    files={}
    for channel,records in [('cursor',public),('secondary',[r for r in public if r['review_id'] in secondary_ids])]:
        ordered=sorted(records,key=lambda r:key(r['review_id']))
        entries=[]
        for i in range(0,len(ordered),20):
            path=BASE/f'packets/{channel}/batch-{i//20+1:03d}.jsonl'
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('x',encoding='utf8') as f:
                for row in ordered[i:i+20]:f.write(json.dumps(row,ensure_ascii=False)+'\n')
            files[path.relative_to(PILOT.parent).as_posix()]=sha(path)
            entries.append({'path':path.relative_to(PILOT.parent).as_posix(),'sha256':sha(path),'n':len(ordered[i:i+20])})
        write(BASE/f'packets/{channel}/packet_manifest.json',{'channel':channel,'n':len(ordered),'batches':entries,'blindness':'No proposed labels, variants, split or rationale provided. Process restriction, not access security.'})
    write(BASE/'private_mapping.json',mapping)
    write(BASE/'packet_freeze.json',{'status':'BLIND_PACKETS_FROZEN_NO_AI_REVIEWS_YET','candidate_manifest_sha256':sha(PILOT/'dataset_manifest.jsonl'),
              'policy_sha256':sha(BASE/'POLICY.md'),'prompt_sha256':sha(BASE/'review_prompt.md'),'private_mapping_sha256':sha(BASE/'private_mapping.json'),
              'cursor_n':400,'fixed_secondary_n':120,'packet_file_sha256':files,'human_review_complete':False,'model_predictions_used':False})
    print('Created 20 Cursor batches /400 cases; 6 secondary batches /120 cases; no model scores.')


if __name__=='__main__':main()
