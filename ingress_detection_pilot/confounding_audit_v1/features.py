"""Reconstruct cached chunk inputs using tokenizers, never call a model."""
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parent
PILOT=ROOT.parent
sys.path.insert(0,str(PILOT/'validation_v2'))
from prepare import build


def main():
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1')
    from transformers import AutoTokenizer
    _,cases=build()
    texts={r['sample_id']:case['data_prompt'] for r,case in cases}
    plan=json.loads((ROOT/'plan.json').read_text(encoding='utf-8'))
    pattern=re.compile(plan['lexical_indicator_regex'],re.I)
    output=[]
    verified=0
    for alias in ['deberta','distilbert','prompt-guard']:
        tokenizer=AutoTokenizer.from_pretrained(str(PILOT/'models'/alias),local_files_only=True)
        rows=[json.loads(x) for x in (PILOT/'validation_v2/results'/alias/'pilot_real_scores.jsonl').read_text(encoding='utf-8').splitlines()]
        for row in rows:
            encoded=tokenizer(texts[row['sample_id']],add_special_tokens=True,truncation=False)['input_ids']
            assert len(encoded)==row['token_count']
            for i,chunk in enumerate(row['chunks']):
                ids=encoded[chunk['start_token']:chunk['end_token']]
                digest=hashlib.sha256(json.dumps(ids).encode()).hexdigest()
                assert digest==chunk['input_token_sha256']
                assert ids[0]==chunk['first_token_id'] and ids[-1]==chunk['last_token_id']
                decoded=tokenizer.decode(ids,skip_special_tokens=False)
                keywords=pattern.findall(decoded)
                role='single' if row['chunk_count']==1 else 'first' if i==0 else 'tail' if i==row['chunk_count']-1 else 'interior'
                output.append({'detector':alias,'sample_id':row['sample_id'],'source_document_id':row['source_document_id'],
                    'domain':row['domain'],'label':row['label'],'split':row['split'],
                    'doc_tokens':row['token_count'],'chunk_count':row['chunk_count'],'chunk_index':i,
                    'position_role':role,'relative_position':i/max(1,row['chunk_count']-1),
                    'chunk_tokens':len(ids),'score':chunk['score'],'input_token_sha256':digest,
                    'starts_cls':int(ids[0]==tokenizer.cls_token_id),'starts_bos':int(ids[0]==tokenizer.bos_token_id),
                    'ends_sep':int(ids[-1]==tokenizer.sep_token_id),'ends_eos':int(ids[-1]==tokenizer.eos_token_id),
                    'starts_special':int(ids[0] in tokenizer.all_special_ids),'ends_special':int(ids[-1] in tokenizer.all_special_ids),
                    'keyword_count':len(keywords),'keyword_types':'|'.join(sorted({v.lower() for v in keywords})),
                    'decoded_chars':len(decoded),'digit_fraction':sum(c.isdigit() for c in decoded)/max(1,len(decoded)),
                    'punctuation_fraction':sum(not c.isalnum() and not c.isspace() for c in decoded)/max(1,len(decoded)),
                    'decoded_text_sha256':hashlib.sha256(decoded.encode()).hexdigest()})
                verified+=1
        print(json.dumps({'detector':alias,'tokenized_documents':len(rows)}),flush=True)
    with (ROOT/'chunk_features.csv').open('x',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(output[0]));writer.writeheader();writer.writerows(output)
    receipt={'status':'EXACT_CACHED_CHUNK_INPUTS_RECONSTRUCTED','n_documents':960,'n_chunks':verified,
        'all_input_token_hashes_match':True,'new_model_forward_calls':0,'content_text_in_git':False,
        'lexical_indicator_warning':'Predefined keyword counts are descriptive; not maliciousness labels or causal content controls',
        'chunk_features_sha256':hashlib.sha256((ROOT/'chunk_features.csv').read_bytes()).hexdigest()}
    with (ROOT/'feature_receipt.json').open('x',encoding='utf-8') as stream:json.dump(receipt,stream,indent=2)
    print(json.dumps(receipt))


if __name__=='__main__':main()
