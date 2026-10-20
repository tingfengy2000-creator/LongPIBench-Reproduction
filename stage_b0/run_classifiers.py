"""Full-coverage classifier collection. Refuses unsigned candidate labels.

No metrics or threshold selection here. Each new run writes exclusively and
records all native windows, raw logits and scores. GPU final runs only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import subprocess
import time
from datetime import datetime,timezone
from pathlib import Path
from evaluation import require_human_signoff,native_windows,file_sha

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--role',choices=['prompt_guard_1','piguard'],required=True)
    ap.add_argument('--model-dir',type=Path,required=True)
    ap.add_argument('--output-dir',type=Path,required=True)
    args=ap.parse_args()
    # Must run before importing torch, fetching a model, or touching a score file.
    rows=require_human_signoff(ROOT/'stage_b0')
    assert platform.system()=='Linux' and platform.node().casefold()=='desktop-b5pnbnc'
    assert args.model_dir.resolve().is_relative_to(Path('/mnt/e')) or args.model_dir.resolve().is_relative_to(Path('/mnt/d'))
    assert args.output_dir.resolve().is_relative_to((ROOT/'runs').resolve())
    meta=json.loads((ROOT/'stage_b0/source_audit/model_metadata.json').read_text(encoding='utf8'))
    spec=next(m for m in meta['models'] if m['role']==args.role)
    assert file_sha(args.model_dir/'model.safetensors')==next(f['lfs_sha256'] for f in spec['files'] if f['name']=='model.safetensors')
    for file in spec['files']:
        if file.get('observed_sha256') and file['name'] in ['config.json','tokenizer_config.json','special_tokens_map.json','modeling_piguard.py']:
            assert file_sha(args.model_dir/file['name'])==file['observed_sha256']
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    os.environ['HF_MODULES_CACHE']=str(args.output_dir.parent/'b0-modules')
    import torch
    import transformers
    from transformers import AutoTokenizer,AutoModelForSequenceClassification
    assert torch.cuda.is_available() and '5090' in torch.cuda.get_device_name(0)
    assert torch.cuda.mem_get_info()[0]>=4*1024**3
    torch.manual_seed(42)
    tok=AutoTokenizer.from_pretrained(args.model_dir,trust_remote_code=False,local_files_only=True)
    start=time.perf_counter()
    model=AutoModelForSequenceClassification.from_pretrained(args.model_dir,trust_remote_code=args.role=='piguard',
               local_files_only=True,use_safetensors=True,torch_dtype=torch.float32).to('cuda').eval()
    torch.cuda.synchronize();load_seconds=time.perf_counter()-start
    expected={0:'BENIGN',1:'INJECTION',2:'JAILBREAK'} if args.role=='prompt_guard_1' else {0:'benign',1:'injection'}
    assert model.config.id2label==expected and model.config.max_position_embeddings==512
    assert next(model.parameters()).dtype==torch.float32
    # Warm-up is completely independent from the candidate set.
    warm='The equipment arrived on Wednesday. The clerk recorded the delivery.'
    for _ in range(3):
        with torch.inference_mode():model(**tok(warm,return_tensors='pt').to('cuda'))
    torch.cuda.synchronize()
    args.output_dir.mkdir(parents=True,exist_ok=False)
    config={'status':'STARTED','role':args.role,'repo_id':spec['repo_id'],'revision':spec['revision'],
            'dataset_sha256':file_sha(ROOT/'stage_b0/dataset_manifest.jsonl'),
            'protocol_sha256':file_sha(ROOT/'stage_b0/protocol_v1.md'),
            'signoff_sha256':file_sha(ROOT/'stage_b0/human_signoff.json'),
            'input_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'torch':torch.__version__,'transformers':transformers.__version__,
            'device':torch.cuda.get_device_name(0),'dtype':'float32','load_seconds':load_seconds,
            'start_utc':datetime.now(timezone.utc).isoformat(),'aggregation':'max(class_softmax[1:]) over all native packed chunks',
            'warmup_excluded':3,'paper_confirmatory':False}
    with (args.output_dir/'run_manifest.json').open('x',encoding='utf8') as f:json.dump(config,f,indent=2);f.write('\n')
    with (args.output_dir/'raw_scores.jsonl').open('x',encoding='utf8') as f:
        for r in sorted(rows,key=lambda x:x['sample_id']):
            start=time.perf_counter();ids,windows=native_windows(tok,r['text'],512)
            chunks=[];forward=0.;torch.cuda.reset_peak_memory_stats()
            for w in windows:
                inputs={'input_ids':torch.tensor([w['input_ids']],device='cuda'),
                        'attention_mask':torch.tensor([w['attention_mask']],device='cuda')}
                torch.cuda.synchronize();t=time.perf_counter()
                with torch.inference_mode():logits=model(**inputs).logits
                torch.cuda.synchronize();seconds=time.perf_counter()-t;forward+=seconds
                assert torch.isfinite(logits).all(),'Non-finite logits; preserve partial run and stop'
                probs=logits.softmax(-1)[0].tolist()
                chunks.append({'start_token':w['start_token'],'end_token':w['end_token'],'input_token_ids':w['input_ids'],
                               'input_sha256':hashlib.sha256(json.dumps(w['input_ids'],separators=(',',':')).encode()).hexdigest(),
                               'raw_logits':logits[0].tolist(),'class_softmax':probs,'score':max(probs[1:]),'forward_seconds':seconds})
            row={k:r[k] for k in ['sample_id','source_document_id','domain','split','variant','label','text_sha256']}
            row.update(token_count=len(ids),chunk_count=len(chunks),chunks=chunks,
                       score=max(c['score'] for c in chunks),forward_seconds=forward,
                       seconds=time.perf_counter()-start,peak_allocated_bytes=torch.cuda.max_memory_allocated(),validity='VALID')
            f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush()
    with (args.output_dir/'completion.json').open('x',encoding='utf8') as f:
        json.dump({'status':'CLASSIFIER_SCORES_RECORDED_REVIEW_REQUIRED','n':400,'raw_scores_sha256':file_sha(args.output_dir/'raw_scores.jsonl')},f,indent=2);f.write('\n')


if __name__=='__main__':main()
