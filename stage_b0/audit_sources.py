"""Pin official model metadata and fetch small files without executing custom code."""
from __future__ import annotations
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'stage_b0' / 'source_audit'
CACHE = Path('E:/Caches/longpibench-b0')


def main():
    for name, value in {'HF_HUB_CACHE':str(CACHE/'hub'), 'HF_XET_CACHE':str(CACHE/'xet'),
                        'HF_ASSETS_CACHE':str(CACHE/'assets'), 'HF_MODULES_CACHE':str(CACHE/'modules'),
                        'TORCH_HOME':str(CACHE/'torch'), 'TEMP':str(CACHE/'temp'),
                        'TMP':str(CACHE/'temp')}.items():
        os.environ[name]=value
        Path(value).mkdir(parents=True,exist_ok=True)
    from huggingface_hub import HfApi, hf_hub_download
    api=HfApi()
    DEST.mkdir(exist_ok=True)
    inventory=[]
    models=[('prompt_guard_1','meta-llama/Prompt-Guard-86M','1209add6ca7d9c1d815171b8e5571587fe3e7b03'),
            ('prompt_guard_2','meta-llama/Llama-Prompt-Guard-2-86M',None),
            ('piguard','leolee99/PIGuard',None)]
    for role, repo, revision in models:
        record={'role':role,'repo_id':repo,'requested_revision':revision,'files':[]}
        start=time.perf_counter()
        try:
            info=api.model_info(repo,revision=revision,files_metadata=True)
            record['revision']=info.sha
            target=DEST/role
            target.mkdir(exist_ok=True)
            for f in info.siblings:
                name=f.rfilename
                lfs=getattr(f,'lfs',None)
                meta={'name':name,'size':f.size,'lfs_sha256':getattr(lfs,'sha256',None) if lfs else None}
                if (name.endswith('.py') or name in ['config.json','tokenizer_config.json','special_tokens_map.json','README.md']) and (f.size or 0)<400000:
                    cached=Path(hf_hub_download(repo,name,revision=info.sha,cache_dir=CACHE/'hub'))
                    blob=cached.read_bytes()
                    local=target/name
                    local.parent.mkdir(parents=True,exist_ok=True)
                    with local.open('xb') as stream: stream.write(blob)
                    meta.update(local_file=local.relative_to(ROOT).as_posix(),observed_sha256=hashlib.sha256(blob).hexdigest())
                record['files'].append(meta)
            record['status']='METADATA_AND_SMALL_SOURCES_FETCHED_NOT_MODEL_LOADED'
        except Exception as error:
            # Do not serialize request headers or token-bearing objects.
            record['status']='BLOCKED_METADATA_OR_SMALL_FILES'
            record['error_type']=type(error).__name__
            record['http_status']=getattr(getattr(error,'response',None),'status_code',None)
        record['seconds']=time.perf_counter()-start
        inventory.append(record)
        print(role,record['status'],record.get('revision'))
    result={'observed_utc':datetime.now(timezone.utc).isoformat(),'hostname':platform.node(),
            'python':sys.version,'models':inventory,'custom_code_executed':False,
            'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'cache_root':str(CACHE),'credentials_exposed':False}
    with (DEST/'model_metadata.json').open('x',encoding='utf8') as f:
        json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')


if __name__=='__main__':main()
