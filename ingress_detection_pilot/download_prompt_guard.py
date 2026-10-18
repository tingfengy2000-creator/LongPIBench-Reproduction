"""Authorized fixed Prompt Guard inference files, exclusively on E:."""
import hashlib
import json
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

ROOT=Path(__file__).resolve().parent
REPO='meta-llama/Prompt-Guard-86M'
REVISION='1209add6ca7d9c1d815171b8e5571587fe3e7b03'


if __name__=='__main__':
    folder=ROOT/'models/prompt-guard'
    assert folder.resolve().drive.upper()=='E:'
    names={'model.safetensors','config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json'}
    info=HfApi().model_info(REPO,revision=REVISION,files_metadata=True,token=True)
    assert info.sha==REVISION
    snapshot_download(REPO,revision=REVISION,allow_patterns=sorted(names),local_dir=folder,
        cache_dir=r'E:\Caches\huggingface\hub',token=True,max_workers=2)
    rows=[]
    for item in info.siblings:
        if item.rfilename not in names:continue
        path=folder/item.rfilename
        with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        assert path.stat().st_size==item.size
        if item.lfs:assert digest==item.lfs.sha256
        rows.append({'filename':item.rfilename,'bytes':item.size,'sha256':digest})
    assert {r['filename'] for r in rows}==names
    report={'repo_id':REPO,'revision':REVISION,'files':rows,'status':'INFERENCE_FILES_VERIFIED','credentials_exposed':False}
    with (ROOT/'source_audit/prompt-guard-download.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    print(json.dumps({'status':report['status'],'bytes':sum(r['bytes'] for r in rows)}))
