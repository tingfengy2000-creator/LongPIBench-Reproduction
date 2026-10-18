"""Bounded metadata/20-row token-length feasibility only; no detector scoring."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parent
PILOT=ROOT.parent
sys.path.insert(0,str(PILOT))
from prepare_samples import benchmark
from prepare import grams, write


def fetch(url):
    request=urllib.request.Request(url,headers={'User-Agent':'LongPIBench-M1-feasibility/1.0'})
    with urllib.request.urlopen(request,timeout=45) as stream:
        data=stream.read(2_000_001)
        assert len(data)<=2_000_000,'Unexpectedly large metadata response'
        return data,json.loads(data)


def main():
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    from transformers import AutoTokenizer
    tokenizers={name:AutoTokenizer.from_pretrained(str(PILOT/'models'/name),local_files_only=True) for name in ['prompt-guard','deberta','distilbert']}
    api_cache=Path('E:/Caches/longpibench-m1-availability')
    api_cache.mkdir(parents=True,exist_ok=False)
    old=benchmark()
    oldsets=[]
    for domain,goal,pos in [('email','0','last'),('resume','2','footnote')]:
        for i in range(100):oldsets.append(grams(old.prepare_example(domain,i,'no',goal,pos).to_dict()['data_prompt']))
    result={'retrieved_utc':datetime.now(timezone.utc).isoformat(),
        'purpose':'Availability and token-length design only; these 40 inspected rows are excluded from future frozen test',
        'detector_forwards':0,'bulk_download':False,'preview_limit_per_domain':20,'datasets':{}}
    allrows=[]
    for domain,dataset in [('email','corbt/enron-emails'),('resume','ahmedheakl/resume-atlas')]:
        meta_url='https://huggingface.co/api/datasets/'+dataset
        meta_raw,meta=fetch(meta_url)
        rows_url='https://datasets-server.huggingface.co/rows?'+urllib.parse.urlencode({'dataset':dataset,'config':'default','split':'train','offset':0,'length':20})
        rows_raw,preview=fetch(rows_url)
        # Raw contains candidate personal data; retain only local cache, not Git.
        for name,data in [('metadata',meta_raw),('preview',rows_raw)]:
            with (api_cache/f'{domain}-{name}.json').open('xb') as stream:stream.write(data)
        # Viewer endpoint serves current revision; bind with before/after API SHA.
        _,after=fetch(meta_url)
        assert meta['sha']==after['sha']
        rows=[]
        for entry in preview['rows']:
            assert not entry['truncated_cells'],'Length from truncated viewer cell is not admissible'
            row=entry['row']
            text=('Subject: '+row['subject']+'\n'+row['body']) if domain=='email' else row['Text']
            g=grams(text)
            overlap=max((len(g&h)/len(g|h) if g|h else 0.) for h in oldsets)
            counts={name:len(tok(text,add_special_tokens=True,truncation=False)['input_ids']) for name,tok in tokenizers.items()}
            item={'domain':domain,'viewer_row_index':entry['row_idx'],'text_sha256':hashlib.sha256(text.encode()).hexdigest(),
                'token_counts':counts,'max_old200_word5_jaccard':overlap,
                'source_group_hint_sha256':hashlib.sha256((row['from'] if domain=='email' else row['Text']).encode()).hexdigest()}
            rows.append(item);allrows.append(item)
        result['datasets'][domain]={'dataset':dataset,'current_sha_before_after':meta['sha'],
            'metadata_url':meta_url,'viewer_url':rows_url,'viewer_revision_caveat':'Viewer has no immutable revision parameter; before/after repository SHA unchanged, response hash retained',
            'response_sha256':hashlib.sha256(rows_raw).hexdigest(),'metadata_sha256':hashlib.sha256(meta_raw).hexdigest(),
            'n_inspected':len(rows),'license_claim':meta.get('cardData',{}).get('license','not declared'),
            'raw_local_only':str(api_cache/f'{domain}-preview.json'),
            'source_group_hint_distinct':len({r['source_group_hint_sha256'] for r in rows}),
            'token_ranges':{name:[min(r['token_counts'][name] for r in rows),max(r['token_counts'][name] for r in rows)] for name in tokenizers}}
    bands=[(128,255),(256,511),(512,1023),(1024,2047),(2048,4095)]
    result['candidate_common_support_deberta_tokens']=[]
    for lo,hi in bands:
        counts={d:sum(lo<=r['token_counts']['deberta']<=hi for r in allrows if r['domain']==d) for d in ['email','resume']}
        result['candidate_common_support_deberta_tokens'].append({'range':[lo,hi],'observed_documents':counts,'both_domains_observed':all(counts.values())})
    result['inference_limit']='Consecutive first20, not representative or source-independent; author clusters and OCR cleaning differ. Common interval is provisional existence evidence, not enough independent sources for800.'
    write(ROOT/'candidate_availability.json',result)
    write(ROOT/'candidate_length_screen.json',allrows)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
