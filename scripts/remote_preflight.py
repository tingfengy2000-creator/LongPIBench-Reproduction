"""Cross-platform, no-install preflight with append-only Git return artifacts.

Does not read credentials, download weights or execute benchmark inference.
"""
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repro.hardware import gpu_gate

def run(args, timeout=30):
    try:
        p = subprocess.run(args,capture_output=True,timeout=timeout)
        return {'command':args,'returncode':p.returncode,'stdout':p.stdout.decode('utf-8',errors='replace'),'stderr':p.stderr.decode('utf-8',errors='replace')}
    except Exception as e:
        return {'command':args,'error':type(e).__name__+': '+str(e)}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label',default='machine-5090')
    parser.add_argument('--task-id',default='R0-5090-001')
    parser.add_argument('--require-gpu', help='Required GPU name substring, e.g. RTX 5090')
    parser.add_argument('--min-vram-mib',type=int,default=30000)
    args=parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',args.label):
        parser.error('label must be 1..40 ASCII letters, digits, hyphen or underscore')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,60}',args.task_id):
        parser.error('invalid task ID')
    if args.min_vram_mib <= 0:
        parser.error('min-vram-mib must be positive')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+args.label+'-'+uuid.uuid4().hex[:8]
    folder=ROOT/'coordination/returns'/run_id
    folder.mkdir(parents=True,exist_ok=False)
    names=['torch','transformers','peft','bitsandbytes','accelerate','huggingface-hub','spacy','datasets','openai','fschat','google-generativeai']
    versions={}
    for name in names:
        try: versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: versions[name]=None
    gpu=run(['nvidia-smi','--query-gpu=name,memory.total,memory.free,driver_version','--format=csv'])
    hardware_gate = gpu_gate(gpu,args.require_gpu,args.min_vram_mib) if args.require_gpu else {'passed':None,'scope':'INVENTORY_ONLY_NO_HARDWARE_REQUIREMENT'}
    torch_code='''import json,torch
r={'version':torch.__version__,'cuda_build':torch.version.cuda,'cuda_available':torch.cuda.is_available(),'architectures':torch.cuda.get_arch_list()}
if torch.cuda.is_available():
 r['gpu']=torch.cuda.get_device_name(0)
 r['capability']=list(torch.cuda.get_device_capability(0))
 x=torch.ones((64,64),device='cuda',dtype=torch.bfloat16)
 y=x@x
 torch.cuda.synchronize()
 r['bf16_matmul_ok']=bool(y[0,0].item()==64)
print(json.dumps(r))
'''
    if hardware_gate['passed'] is False:
        torch_probe={'status':'SKIPPED_HARDWARE_GATE_FAILED'}
    else:
        torch_probe=run([sys.executable,'-c',torch_code],timeout=60) if versions['torch'] else {'status':'NOT_INSTALLED'}
    report={'schema_version':1,'task_id':'R0-5090-001','run_id':run_id,'label':args.label,'timestamp_utc':datetime.now(timezone.utc).isoformat(),'phase':'R0_PREFLIGHT_ONLY','formal_inference_executed':False,'python':sys.version,'python_executable':sys.executable,'platform':platform.platform(),'disk_free_bytes':shutil.disk_usage(ROOT).free,'packages':versions,'gpu':gpu,'torch_probe':torch_probe,'git_head':run(['git','-C',str(ROOT),'rev-parse','HEAD']),'git_branch':run(['git','-C',str(ROOT),'branch','--show-current']),'git_status_before_return':run(['git','-C',str(ROOT),'status','--short']),'upstream_heads':{name:run(['git','-C',str(ROOT/'upstream'/name),'rev-parse','HEAD']) for name in ['LongPIBench','Open-Prompt-Injection']},'followups':['Verify actual GPU is RTX 5090 with ~32GB','If torch is installed, inspect CUDA BF16 smoke result','NF4/model loading and authorized HF access remain separate checks','Do not infer formal readiness from this report alone']}
    path=folder/'preflight.json'
    report.update(schema_version=2,task_id=args.task_id,hostname=platform.node(),hardware_gate=hardware_gate,
                  task_status='BLOCKED' if hardware_gate['passed'] is False else 'PREFLIGHT_RECORDED_NOT_FULL_ACCEPTANCE')
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'return_path':str(path.relative_to(ROOT)),'run_id':run_id,'hardware_gate':hardware_gate,'gpu':gpu,'torch_probe':torch_probe},ensure_ascii=False,indent=2))
    return 2 if hardware_gate['passed'] is False else 0

if __name__=='__main__': raise SystemExit(main())
