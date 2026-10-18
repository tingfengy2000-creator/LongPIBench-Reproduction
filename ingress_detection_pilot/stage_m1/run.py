"""M1 real FP32 CPU experiment; independent output, original score and predictor."""
from datetime import datetime, timezone
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
PILOT = ROOT.parent
REPO = PILOT.parent
sys.path.insert(0,str(PILOT))
from collect_scores import capture, original_score
from prepare_samples import benchmark
from prepare import ids_hash, sha, write


def main():
    plan=json.loads((ROOT/'plan.json').read_text(encoding='utf-8'))
    assert sha(ROOT/'sources_and_conditions.jsonl')==plan['sources_sha256']
    assert sha(REPO/'upstream/LongPIBench/longpibench/detectors.py')==plan['official_detector_sha256']
    seal=json.loads((ROOT/'frozen_existing_files.json').read_text(encoding='utf-8'))['file_sha256']
    assert all(sha(REPO/n)==h for n,h in seal.items())
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1')
    import torch
    torch.set_num_threads(plan['threads'])
    torch.manual_seed(plan['seed'])
    bundle=json.loads((PILOT/'source_audit/prompt-guard-download.json').read_text(encoding='utf-8'))
    assert bundle['revision']==plan['revision']
    model_dir=PILOT/'models/prompt-guard'
    for row in bundle['files']:assert sha(model_dir/row['filename'])==row['sha256']
    benchmark()
    module=importlib.import_module('longpibench.detectors')
    out=ROOT/'raw'/plan['run_id']
    out.mkdir(parents=True,exist_ok=False)
    write(out/'start.json',{'started_utc':datetime.now(timezone.utc).isoformat(), 'run_id':plan['run_id'],
        'input_commit':subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD']).decode().strip(),
        'plan_sha256':sha(ROOT/'plan.json'),'runner_sha256':sha(__file__),
        'hostname':platform.node(),'python':sys.version,
        'runtime':{k:importlib.metadata.version(k) for k in ['torch','transformers','tokenizers','numpy','safetensors']}})
    detector=module.TransformerDetector(str(model_dir),threshold=plan['threshold'],chunk_tokens=512)
    assert str(detector.device)=='cpu' and str(next(detector.model.parameters()).dtype)=='torch.float32'
    assert detector.model.config.id2label=={0:'BENIGN',1:'INJECTION',2:'JAILBREAK'}
    rows=[json.loads(x) for x in (ROOT/'sources_and_conditions.jsonl').read_text(encoding='utf-8').splitlines()]
    forwards=0
    def direct(source,condition,ids,position=0):
        nonlocal forwards
        before=time.perf_counter()
        with torch.inference_mode():
            result=detector.model(input_ids=torch.tensor([ids],device=detector.device))
        logits=result.logits[0]
        probabilities=torch.softmax(logits,dim=-1).cpu().tolist()
        score=original_score(probabilities,detector.model.config.id2label)
        assert torch.isfinite(logits).all().item()
        forwards+=1
        return {'source_id':source,'condition':condition,'simulated_global_chunk_index':position,
            'global_position_passed_to_model':False,'input_token_ids':ids,'input_sha256':ids_hash(ids),
            'n_tokens':len(ids),'logits':logits.cpu().tolist(),'softmax':probabilities,
            'risk_score':score,'predicted':int(score>=.5),'seconds':time.perf_counter()-before}
    started=time.perf_counter()
    with (out/'format_observations.jsonl').open('x',encoding='utf-8',newline='\n') as formats, \
         (out/'document_observations.jsonl').open('x',encoding='utf-8',newline='\n') as documents:
        for row in rows:
            observed={}
            for condition,ids in row['variants'].items():
                result=direct(row['source_id'],condition,ids)
                observed[condition]=result
                formats.write(json.dumps(result,allow_nan=False)+'\n')
            for position in [1,7]:
                result=direct(row['source_id'],'position_negative_control',row['variants']['both_special'],position)
                formats.write(json.dumps(result,allow_nan=False)+'\n')
                assert result['input_sha256']==observed['both_special']['input_sha256']
                assert abs(result['risk_score']-observed['both_special']['risk_score'])<=1e-6
            for condition,doc in [('standalone',{'text':row['text'],'input_ids':row['variants']['both_special']}), *row['documents'].items()]:
                encoded=detector.tokenizer(doc['text'],add_special_tokens=True,truncation=False)['input_ids']
                assert encoded==doc['input_ids']
                captured=capture(detector,doc['text'])
                for i,c in enumerate(captured['chunks']):
                    c['input_token_ids']=encoded[i*512:(i+1)*512]
                    c['canonical_input_sha256']=ids_hash(c['input_token_ids'])
                    assert c['end_token']-c['start_token']==len(c['input_token_ids'])
                if condition=='standalone':
                    assert abs(captured['chunks'][0]['score']-observed['both_special']['risk_score'])<=1e-6
                elif condition=='aligned_tail':
                    tail=captured['chunks'][-1]
                    assert tail['input_token_ids']==row['variants']['tail_sep_only']
                    assert abs(tail['score']-observed['tail_sep_only']['risk_score'])<=1e-6
                documents.write(json.dumps({'source_id':row['source_id'],'condition':condition,
                    'text_sha256':__import__('hashlib').sha256(doc['text'].encode()).hexdigest(),
                    'input_sha256':ids_hash(encoded), **captured},allow_nan=False)+'\n')
                forwards+=captured['chunk_count']
            formats.flush(); documents.flush()
            print(json.dumps({'sources_completed':row['source_id'],'forward_calls':forwards,'seconds':time.perf_counter()-started}),flush=True)
    assert all(sha(REPO/n)==h for n,h in seal.items())
    write(out/'completion.json',{'status':'REAL_MECHANISM_PANEL_EXECUTED','finished_utc':datetime.now(timezone.utc).isoformat(),
        'elapsed_seconds':time.perf_counter()-started,'n_sources':len(rows),'forward_calls':forwards,
        'n_format_records':len(rows)*9,'n_document_records':len(rows)*3,'negative_control_tolerance':1e-6,
        'official_predict_equivalence_verified':True,'aligned_tail_identical_core_verified':True,
        'historical_files_unchanged':len(seal),'model_files_verified':len(bundle['files']),
        'id2label':detector.model.config.id2label,'dtype':'float32','device':'cpu',
        'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()}})


if __name__=='__main__':main()
