"""Frozen M2 experiment engine, smoke gate then fresh full run; no algorithm."""
import argparse
from datetime import datetime,timezone
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
import uuid

ROOT=Path(__file__).resolve().parent
PILOT=ROOT.parent
REPO=PILOT.parent
sys.path.insert(0,str(PILOT))
from collect_scores import capture,original_score
from prepare_samples import benchmark
from prepare import sha,ih,write


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['smoke','full'],required=True);args=ap.parse_args()
    plan=json.loads((ROOT/'plan.json').read_text())
    inputs=REPO/plan['frozen_inputs_path']
    assert sha(inputs)==plan['frozen_inputs_sha256']
    assert sha(ROOT/'02_data_manifest.jsonl')==plan['data_manifest_sha256']
    assert sha(ROOT/'sources.json')==plan['sources_sha256']
    seal=json.loads((ROOT/'frozen_existing_files.json').read_text())['file_sha256']
    assert all(sha(REPO/n)==h for n,h in seal.items())
    if args.phase=='full':
        gate=json.loads((ROOT/'smoke_receipt.json').read_text())
        assert gate['status']=='SMOKE_ENGINEERING_PASS' and gate['runner_sha256']==sha(__file__)
        assert sha(Path(gate['completion_path']))==gate['completion_sha256']
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1')
    import torch
    torch.set_num_threads(plan['threads']);torch.manual_seed(plan['seed'])
    bundle=json.loads((PILOT/'source_audit/prompt-guard-download.json').read_text())
    assert bundle['revision']==plan['model_revision']
    modeldir=PILOT/'models/prompt-guard'
    for r in bundle['files']:assert sha(modeldir/r['filename'])==r['sha256']
    assert sha(REPO/'upstream/LongPIBench/longpibench/detectors.py')==plan['official_detector_sha256']
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-m2-'+args.phase+'-'+uuid.uuid4().hex[:8]
    out=REPO/'runs'/run_id;out.mkdir(exist_ok=False)
    gpu=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv'],capture_output=True,text=True)
    write(out/'start.json',{'run_id':run_id,'phase':args.phase,'started_utc':datetime.now(timezone.utc).isoformat(),
        'input_commit':subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),
        'hostname':platform.node(),'python':sys.version,'torch_cuda':torch.version.cuda,'cuda_available':torch.cuda.is_available(),
        'gpu_inventory':gpu.stdout.strip(),'inference_device':'cpu','dtype':'float32','threads':plan['threads'],
        'runtime':{k:importlib.metadata.version(k) for k in ['torch','transformers','tokenizers','numpy','safetensors']},
        'plan_sha256':sha(ROOT/'plan.json'),'inputs_sha256':sha(inputs),'runner_sha256':sha(__file__)})
    log=(out/'runtime.log').open('x',encoding='utf-8',newline='\n')
    def event(obj):
        line=json.dumps(obj);print(line,flush=True);log.write(line+'\n');log.flush()
    try:
        benchmark();module=importlib.import_module('longpibench.detectors')
        detector=module.TransformerDetector(str(modeldir),threshold=.5,chunk_tokens=512)
        assert str(detector.device)=='cpu' and str(next(detector.model.parameters()).dtype)=='torch.float32'
        assert detector.model.config.id2label=={0:'BENIGN',1:'INJECTION',2:'JAILBREAK'}
        forwards=0
        def count(*args,**kwargs):
            nonlocal forwards
            forwards+=1
        handle=detector.model.register_forward_pre_hook(count)
        def direct(ids,start=None,end=None):
            assert 0<len(ids)<=512
            with torch.inference_mode():result=detector.model(input_ids=torch.tensor([ids],device=detector.device))
            logits=result.logits[0];probs=torch.softmax(logits,dim=-1).cpu().tolist()
            assert torch.isfinite(logits).all().item()
            score=original_score(probs,detector.model.config.id2label)
            return {'input_token_ids':ids,'input_sha256':ih(ids),'n_tokens':len(ids),'start_token':start,'end_token':end,
                'logits':logits.cpu().tolist(),'softmax':probs,'risk_score':score,'prediction':int(score>=.5),
                'special_token_positions':[[i,t] for i,t in enumerate(ids) if t in detector.tokenizer.all_special_ids]}
        rows=[json.loads(x) for x in inputs.read_text(encoding='utf-8').splitlines()]
        if args.phase=='smoke':rows=[r for r in rows if r['source_id'] in plan['smoke_sources']]
        started=time.perf_counter();completed=0
        with (out/'observations.jsonl').open('x',encoding='utf-8',newline='\n') as stream:
            for row in rows:
                before=time.perf_counter();official={}
                core=row['core_token_ids']
                for condition,doc in [('core_reference',{'text':row['core_text'],'input_ids':[1]+core+[2],
                    'core_token_range':[1,len(core)+1],'target_token_range':[x+1 for x in row['core_target_range']],
                    'attack_span':[x+1 for x in row['core_target_range']] if row['label'] else None}),*row['documents'].items()]:
                    ids=detector.tokenizer(doc['text'],add_special_tokens=True,truncation=False)['input_ids']
                    assert ids==doc['input_ids']
                    result=capture(detector,doc['text'])
                    for i,c in enumerate(result['chunks']):
                        c['input_token_ids']=ids[i*512:(i+1)*512];c['input_sha256']=ih(c['input_token_ids'])
                        c['risk_score']=c['score'];c['prediction']=int(c['score']>=.5)
                        c['special_token_positions']=[[j,t] for j,t in enumerate(c['input_token_ids']) if t in detector.tokenizer.all_special_ids]
                    result.update({'input_sha256':ih(ids),'core_token_range':doc['core_token_range'],
                        'target_token_range':doc['target_token_range'],'attack_span':doc['attack_span'],
                        'risk_score':max(result['chunk_scores']),'prediction':result['official_prediction']})
                    official[condition]=result
                base=row['documents']['B_cross']['input_ids']
                cuts=row['shadow']['cuts'];chunks=[direct(base[a:b],a,b) for a,b in zip(cuts,cuts[1:])]
                assert sum([c['input_token_ids'] for c in chunks],[])==base
                shadow={'whole_input_sha256':ih(base),'offset':256,'cuts':cuts,'chunks':chunks,
                    'risk_score':max(c['risk_score'] for c in chunks),'prediction':int(any(c['prediction'] for c in chunks)),
                    'is_official':False,'offset0_provenance':'Reuse this record official.B_cross; no new forward'}
                recovery={c:direct(ids) for c,ids in row['recovery_inputs'].items()}
                controls={c:direct(ids) for c,ids in row['control_inputs'].items()}
                ref=official['core_reference']['chunks'][0]
                for index in [1,7]:
                    v=direct([1]+core+[2]);v['simulated_global_chunk_index']=index;v['offset_passed_to_model']=False
                    assert v['logits']==ref['logits'] and v['input_sha256']==ref['input_sha256']
                    controls[f'global{index}']=v
                assert recovery['native_full']['input_sha256']==ref['input_sha256']
                assert abs(recovery['native_full']['risk_score']-ref['risk_score'])<=1e-7
                record={k:row[k] for k in ['source_id','domain','text_type','label','variant','semantic_family','core_target_range','core_attack_span','core_cut']}
                record.update({'official':official,'shadow':shadow,'recovery':recovery,'controls':controls,
                    'elapsed_seconds':time.perf_counter()-before})
                stream.write(json.dumps(record,allow_nan=False)+'\n');stream.flush();completed+=1
                event({'completed_variants':completed,'planned_variants':len(rows),'source_id':row['source_id'],
                    'label':row['label'],'forward_calls':forwards,'seconds':round(time.perf_counter()-started,3)})
        handle.remove()
        assert all(sha(REPO/n)==h for n,h in seal.items())
        completion={'status':'SMOKE_ENGINEERING_PASS' if args.phase=='smoke' else 'M2_FULL_EXECUTED_REVIEW_REQUIRED',
            'run_id':run_id,'phase':args.phase,'n_variants':len(rows),'n_sources':len({r['source_id'] for r in rows}),
            'forward_calls':forwards,'elapsed_seconds':time.perf_counter()-started,'finished_utc':datetime.now(timezone.utc).isoformat(),
            'official_max_equivalence_verified':True,'fixed_whole_token_shadow_verified':True,
            'exact_global_negative_controls_verified':True,'recovery_full_reference_score_verified':True,
            'all_input_limits_le512':True,'historical_files_unchanged':len(seal),
            'observations_sha256':sha(out/'observations.jsonl'),'runner_sha256':sha(__file__)}
        write(out/'completion.json',completion)
        write(ROOT/(args.phase+'_receipt.json'),completion|{'completion_path':str(out/'completion.json'),
            'completion_sha256':sha(out/'completion.json'),'observations_path':str(out/'observations.jsonl')})
        event(completion)
    except BaseException:
        write(out/'FAILED.json',{'exception':traceback.format_exc(),'failed_utc':datetime.now(timezone.utc).isoformat()})
        raise
    finally:log.close()


if __name__=='__main__':main()
