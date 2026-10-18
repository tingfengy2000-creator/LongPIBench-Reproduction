"""Real local inference on frozen independent orientation controls only."""
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
PILOT=ROOT.parent
sys.path.insert(0,str(PILOT))
from collect_scores import capture
from prepare_samples import benchmark, sha


def main():
    plan=json.loads((ROOT/'plan.json').read_text(encoding='utf-8'))
    assert sha(ROOT/'controls_manifest.jsonl')==plan['controls']['manifest_sha256']
    assert not (ROOT/'controls_observations.jsonl').exists()
    rows=[json.loads(x) for x in (ROOT/'controls_manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1')
    import torch
    torch.set_num_threads(4)
    bundle=json.loads((PILOT/'source_audit/distilbert-download.json').read_text(encoding='utf-8'))
    model_dir=PILOT/'models/distilbert'
    for item in bundle['files']:assert sha(model_dir/item['filename'])==item['sha256']
    benchmark()
    module=importlib.import_module('longpibench.detectors')
    start=datetime.now(timezone.utc).isoformat()
    detector=module.TransformerDetector(str(model_dir),threshold=.5,chunk_tokens=512)
    assert str(detector.device)=='cpu' and str(next(detector.model.parameters()).dtype)=='torch.float32'
    with (ROOT/'controls_observations.jsonl').open('x',encoding='utf-8') as stream:
        for row in rows:
            observed=capture(detector,row['text'])
            assert observed['chunk_count']==1
            record=dict(row,**observed)
            stream.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n');stream.flush()
    report={'status':'REAL_INDEPENDENT_CONTROLS_RECORDED','started_utc':start,'finished_utc':datetime.now(timezone.utc).isoformat(),
        'model_repo':'fmops/distilbert-prompt-injection','model_revision':bundle['revision'],
        'n':len(rows),'dtype':'float32','device':'cpu','torch':torch.__version__,
        'transformers':importlib.import_module('transformers').__version__,
        'config_id2label':detector.model.config.id2label,
        'documented_author_space_mapping':{'LABEL_0':'benign','LABEL_1':'prompt injection'},
        'author_space_revision':'ef784e4cadfe184f02683a87a6ad19f565fda9b4',
        'observation_sha256':sha(ROOT/'controls_observations.jsonl'),
        'intended_use':'Orientation diagnostic only, never historical relabeling or generalization estimate',
        'historical_scores_modified':False}
    with (ROOT/'control_run.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    print(json.dumps(report))


if __name__=='__main__':main()
