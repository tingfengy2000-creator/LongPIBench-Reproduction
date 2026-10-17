"""Synthetic CUDA BF16/NF4 check on a verified GPU. No model/data download."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import re
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repro.hardware import gpu_gate
from scripts.remote_preflight import run

CUDA_PROBE = '''import json,sys
r={'synthetic_only':True,'formal_samples_used':False,'passed':False}
try:
 import torch
 r.update(torch_version=torch.__version__,cuda_build=torch.version.cuda,cuda_available=torch.cuda.is_available())
 if not torch.cuda.is_available(): raise RuntimeError('CUDA is not available')
 r['device_name']=torch.cuda.get_device_name(0)
 r['memory_total_mib']=torch.cuda.get_device_properties(0).total_memory/1024**2
 r['capability']=list(torch.cuda.get_device_capability(0))
 if sys.argv[1].casefold() not in r['device_name'].casefold() or r['memory_total_mib']<int(sys.argv[2]):
  raise RuntimeError('CUDA device 0 does not match the required GPU and VRAM')
 torch.manual_seed(42)
 x=torch.ones((64,64),device='cuda',dtype=torch.bfloat16)
 r['cuda_bf16_ok']=bool((x@x)[0,0].item()==64)
 if not r['cuda_bf16_ok']: raise RuntimeError('CUDA BF16 check failed')
 import bitsandbytes as bnb
 r['bitsandbytes_version']=bnb.__version__
 layer=bnb.nn.Linear4bit(64,64,bias=False,compute_dtype=torch.bfloat16,compress_statistics=True,quant_type='nf4').to('cuda')
 y=layer(x)
 torch.cuda.synchronize()
 r['nf4_shape']=list(y.shape)
 r['nf4_finite']=bool(torch.isfinite(y).all().item())
 r['weight_device']=str(layer.weight.device)
 r['weight_dtype']=str(layer.weight.dtype)
 r['quant_state_present']=getattr(layer.weight,'quant_state',None) is not None
 r['passed']=r['nf4_finite'] and r['nf4_shape']==[64,64] and r['quant_state_present'] and layer.weight.device.type=='cuda'
except Exception as exc:
 r['error_type']=type(exc).__name__
 r['error']=str(exc)
print(json.dumps(r))
raise SystemExit(0 if r['passed'] else 2)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-gpu', default='RTX 5090')
    parser.add_argument('--task-id', default='R0-5090-002')
    parser.add_argument('--min-vram-mib', type=int, default=30000)
    args = parser.parse_args()
    if not args.require_gpu.strip() or args.min_vram_mib <= 0:
        parser.error('An explicit GPU name and positive VRAM are required')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', args.task_id):
        parser.error('Invalid task ID')
    inventory = run(['nvidia-smi', '--query-gpu=name,memory.total,memory.free,driver_version', '--format=csv'])
    gate = gpu_gate(inventory, args.require_gpu, args.min_vram_mib)
    runtime = (run([sys.executable, '-c', CUDA_PROBE, args.require_gpu, str(args.min_vram_mib)], timeout=45)
               if gate['passed'] else {'status': 'SKIPPED_HARDWARE_GATE_FAILED'})
    passed = gate['passed'] and runtime.get('returncode') == 0
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-gpu-runtime-' + uuid.uuid4().hex[:8]
    folder = ROOT / 'coordination/returns' / run_id
    folder.mkdir(parents=True, exist_ok=False)
    record = {'schema_version': 1, 'task_id': args.task_id, 'run_id': run_id,
              'hostname': platform.node(), 'platform': platform.platform(),
              'python_executable': sys.executable, 'phase': 'R0_SYNTHETIC_GPU_CHECK',
              'formal_inference_executed': False, 'model_load_verified': False,
              'status': 'SYNTHETIC_GPU_CHECK_PASSED' if passed else 'BLOCKED',
              'gpu_inventory': inventory, 'hardware_gate': gate, 'runtime': runtime,
              'git_head': run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'])}
    path = folder / 'gpu_runtime.json'
    with path.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({'return_path': str(path.relative_to(ROOT)), 'status': record['status']}, ensure_ascii=False))
    return 0 if passed else 2


if __name__ == '__main__':
    raise SystemExit(main())
