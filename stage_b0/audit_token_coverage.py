"""Tokenization-only checks on candidates; no model loads or model scores."""
import json
from pathlib import Path
from collections import Counter
from evaluation import native_windows,file_sha

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'stage_b0'


def main():
    from transformers import AutoTokenizer
    rows=[json.loads(l) for l in (BASE/'dataset_manifest.jsonl').read_text(encoding='utf8').splitlines()]
    records=[];summary={}
    for role in ['prompt_guard_1','piguard']:
        probe=json.loads((BASE/f'source_audit/{role}_load_probe.json').read_text(encoding='utf8'))
        tok=AutoTokenizer.from_pretrained(probe['model_directory'],local_files_only=True,trust_remote_code=False)
        for r in rows:
            ids,windows=native_windows(tok,r['text'],512)
            assert windows[0]['start_token']==0 and windows[-1]['end_token']==len(ids)
            assert all(a['end_token']==b['start_token'] for a,b in zip(windows,windows[1:]))
            for w in windows:assert len(w['input_ids'])==len(w['source_token_ids'])+2
            if len(windows)==1:assert windows[0]['input_ids']==tok(r['text'],truncation=False)['input_ids']
            records.append({'sample_id':r['sample_id'],'model_role':role,'text_sha256':r['text_sha256'],
                            'token_count_without_specials':len(ids),'chunk_count':len(windows),
                            'ranges':[[w['start_token'],w['end_token']] for w in windows],
                            'model_input_lengths':[len(w['input_ids']) for w in windows]})
        subset=[r for r in records if r['model_role']==role]
        summary[role]={'n':len(subset),'token_min':min(r['token_count_without_specials'] for r in subset),
                       'token_max':max(r['token_count_without_specials'] for r in subset),
                       'chunks_distribution':dict(Counter(r['chunk_count'] for r in subset))}
    with (BASE/'token_coverage_plan.jsonl').open('x',encoding='utf8') as f:
        for r in records:f.write(json.dumps(r)+'\n')
    result={'status':'TOKENIZATION_ONLY_FULL_COVERAGE_VERIFIED_NOT_SCORED','n_records':800,
            'candidate_model_forwards':0,'human_labels_still_pending':True,
            'dataset_sha256':file_sha(BASE/'dataset_manifest.jsonl'),'summary':summary}
    with (BASE/'token_coverage_validation.json').open('x',encoding='utf8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
