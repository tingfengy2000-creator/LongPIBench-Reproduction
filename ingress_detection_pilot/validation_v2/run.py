"""Offline real-score execution for a frozen expansion; no R0-R4 writes."""
import argparse
from datetime import datetime, timezone
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
PILOT=ROOT.parent
sys.path.insert(0,str(ROOT))
from prepare import build, sha
sys.path.insert(0,str(PILOT))
from collect_scores import capture


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--detector',required=True,choices=['deberta','distilbert','prompt-guard'])
    args=parser.parse_args()
    assert ROOT.resolve().drive.upper()=='E:'
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1')
    plan=json.loads((ROOT/'plan.json').read_text())
    assert sha(PILOT/'collect_scores.py')==plan['capture_adapter_sha256']
    assert sha(PILOT/'score_pilot.py')==plan['supplied_scorer_sha256']
    assert sha(ROOT/'sample_manifest.jsonl')==plan['sample_manifest_sha256']
    records,cases=build()
    assert records==[json.loads(x) for x in (ROOT/'sample_manifest.jsonl').read_text().splitlines()]
    meta=json.loads((PILOT/'source_audit'/f'{args.detector}.json').read_text())
    bundle=json.loads((PILOT/'source_audit'/f'{args.detector}-download.json').read_text())
    assert meta['sha']==bundle['revision']==plan['model_versions'][args.detector]
    model_dir=PILOT/'models'/args.detector
    for file in bundle['files']:assert sha(model_dir/file['filename'])==file['sha256']
    import torch
    torch.set_num_threads(plan['threads_per_detector'])
    assert not torch.cuda.is_available(), 'Frozen condition is CPU; do not change device silently'
    folder=ROOT/'results'/args.detector
    folder.mkdir(parents=True,exist_ok=False)
    manifest={'status':'STARTED','task_id':'INGRESS-5060-002','formal_paper_experiment':False,
        'started_utc':datetime.now(timezone.utc).isoformat(),'hostname':platform.node(),
        'input_commit':subprocess.check_output(['git','-C',str(PILOT.parent),'rev-parse','HEAD']).decode().strip(),
        'runner_sha256':sha(Path(__file__)),'plan_sha256':sha(ROOT/'plan.json'),
        'model_repo':meta['id'],'model_revision':meta['sha'],'python':sys.version,
        'original_detectors_sha256':sha(PILOT.parent/'upstream/LongPIBench/longpibench/detectors.py'),
        'capture_sha256':sha(PILOT/'collect_scores.py'), 'sample_manifest_sha256':sha(ROOT/'sample_manifest.jsonl'),
        'runtime':{k:importlib.metadata.version(k) for k in ['torch','transformers','tokenizers','numpy','safetensors','sentencepiece']}}
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    module=importlib.import_module('longpibench.detectors')
    detector=module.TransformerDetector(str(model_dir),threshold=.5,chunk_tokens=512)
    assert str(detector.device)=='cpu' and str(next(detector.model.parameters()).dtype)=='torch.float32'
    runtime={'id2label':detector.model.config.id2label,'tokenizer_class':type(detector.tokenizer).__name__,
        'tokenizer_model_max_length':detector.tokenizer.model_max_length,'max_position_embeddings':detector.model.config.max_position_embeddings,
        'device':str(detector.device),'dtype':str(next(detector.model.parameters()).dtype)}
    try:
        with (folder/'pilot_real_scores.jsonl').open('x',encoding='utf-8') as stream:
            for i,(record,case) in enumerate(cases,1):
                captured=capture(detector,case['data_prompt'])
                captured.update(record,detector=args.detector,model_repo=meta['id'],model_revision=meta['sha'],
                    score_type='max_of_selected_class_softmax_components_not_calibrated_attack_probability')
                stream.write(json.dumps(captured,ensure_ascii=False,allow_nan=False)+'\n');stream.flush()
                if i==1 or i%10==0:print(json.dumps({'detector':args.detector,'done':i,'total':len(cases)}),flush=True)
    except BaseException as exc:
        (folder/'failure.json').write_text(json.dumps({'status':'FAILED_PARTIAL_PRESERVED','type':type(exc).__name__,'message':str(exc)},indent=2)+'\n')
        raise
    completion=dict(manifest,status='REAL_SCORES_COLLECTED',n_variants=len(records),n_source_documents=160,
        runtime_model=runtime,scores_sha256=sha(folder/'pilot_real_scores.jsonl'),finished_utc=datetime.now(timezone.utc).isoformat())
    (folder/'completion.json').write_text(json.dumps(completion,indent=2)+'\n')
    print(json.dumps({'detector':args.detector,'status':completion['status'],'n':len(records)}),flush=True)


if __name__=='__main__':main()
