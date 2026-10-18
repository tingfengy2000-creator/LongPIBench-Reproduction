"""Offline single-model GPU load and synthetic short-inference probe.

One invocation loads one model. No adapters, downloads, benchmark samples or ASR.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repro.hardware import gpu_gate
from scripts.remote_preflight import run

PUBLIC_RECEIPT = 'coordination/returns/20261017T152919Z-public-models-f7e08811/public_models.json'
TARGET_RECEIPT = 'coordination/returns/20261017T160020Z-offline-hf-0a7c5a5d/hf_files.json'


def local_spec(root, role):
    plan = json.loads((root / 'configs/offline_transfer_manifest.json').read_text(encoding='utf-8'))
    model = next(item for item in plan['hf_models'] if item['role'] == role)
    fixed = json.loads((root / 'configs/upstream_lock.json').read_text(encoding='utf-8'))['model_snapshots_observed_at_audit'][role]
    if model['repo_id'] != fixed['repo_id'] or model['revision'] != fixed['revision']:
        raise ValueError('Model file plan differs from fixed model lock')
    receipt_path = root / (TARGET_RECEIPT if role == 'target' else PUBLIC_RECEIPT)
    raw = receipt_path.read_bytes()
    receipt = json.loads(raw)
    result = next(item for item in receipt['results'] if item['role'] == role)
    if (result['repo_id'] != model['repo_id'] or result['revision'] != model['revision']
            or result['status'] != 'FILES_VERIFIED_NOT_MODEL_LOADED'):
        raise ValueError('Model file receipt does not match the fixed model')
    if role == 'target':
        path = root / 'models/direct-hf/hf/target'
    else:
        path = root / 'models/hf-cache' / ('models--' + model['repo_id'].replace('/', '--')) / 'snapshots' / model['revision']
    # Follow the current repository symlinks (including /mnt/e), never interpret
    # a Windows path or silently copy/move the existing model cache.
    for item in model['files']:
        if (path / item['filename']).stat().st_size != item['size_bytes']:
            raise ValueError('Current file size differs from accepted download receipt')
    return {'role': role, 'repo_id': model['repo_id'], 'revision': model['revision'],
            'path': str(path), 'resolved_path': str(path.resolve(strict=True)),
            'source_receipt': receipt_path.relative_to(root).as_posix(),
            'source_receipt_sha256': hashlib.sha256(raw).hexdigest(),
            'config_sha256': hashlib.sha256((path / 'config.json').read_bytes()).hexdigest(),
            'file_check_scope': 'Prior accepted full hashes plus current sizes; no repeated large-file hashing'}


def tokenize_synthetic_prompt(tokenizer, role, report):
    if role == 'target':
        messages = [{'role': 'system', 'content': 'Reply with the single word READY.'},
                    {'role': 'user', 'content': 'This is an isolated model loading check.'}]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        report['synthetic_messages'] = messages
        report['chat_template_sha256'] = hashlib.sha256((tokenizer.chat_template or '').encode('utf-8')).hexdigest()
        # The rendered chat already includes BOS and role delimiters. Adding
        # tokenizer special tokens again duplicated BOS in the original 009.
        inputs = tokenizer(prompt, return_tensors='pt', add_special_tokens=False)
        report['tokenization'] = {'rendered_chat': True, 'add_special_tokens': False}
    else:
        prompt = 'This is a synthetic model loading check.'
        inputs = tokenizer(prompt, return_tensors='pt')
        report['tokenization'] = {'rendered_chat': False, 'add_special_tokens': 'tokenizer_default'}
    report['synthetic_prompt'] = prompt
    return inputs


def probe_runtime(spec, report):
    # Set before importing the GPU/model runtime. Explicit token=False below also
    # avoids credential lookup in library requests, even with local_files_only.
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['CUDA_VISIBLE_DEVICES'] = '0'
    report['stage'] = 'environment'
    expected = {'torch': '2.7.1+cu128', 'transformers': '4.51.3',
                'bitsandbytes': '0.46.1', 'accelerate': '1.6.0'}
    report['packages'] = {name: importlib.metadata.version(name) for name in expected}
    if report['packages'] != expected:
        raise RuntimeError('GPU/model package versions differ from the accepted candidate stack')
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable')
    props = torch.cuda.get_device_properties(0)
    if '5090' not in props.name or props.total_memory < 30000 * 1024**2:
        raise RuntimeError('CUDA device 0 is not the required 5090 with >=30000MiB')
    free, total = torch.cuda.mem_get_info(0)
    required_gib = {'helper': 2, 'detector_base': 8, 'target': 20}[spec['role']]
    report['cuda'] = {'device': props.name, 'cuda_build': torch.version.cuda,
                      'total_bytes': total, 'free_before_bytes': free,
                      'minimum_free_gib_for_probe': required_gib}
    if free < required_gib * 1024**3:
        raise RuntimeError('Insufficient free VRAM; preserve other processes, do not force eviction')
    torch.manual_seed(42)
    report['seed'] = 42
    torch.cuda.reset_peak_memory_stats(0)
    path = spec['resolved_path']
    local = {'local_files_only': True, 'trust_remote_code': False, 'token': False}
    report['stage'] = 'tokenizer'
    tokenizer = AutoTokenizer.from_pretrained(path, **local,
        **({'add_bos_token': True} if spec['role'] == 'detector_base' else {}))
    inputs = tokenize_synthetic_prompt(tokenizer, spec['role'], report)
    report['input_token_ids'] = inputs['input_ids'][0].tolist()
    report['input_token_count'] = int(inputs['input_ids'].shape[1])
    kwargs = {**local, 'use_safetensors': True, 'low_cpu_mem_usage': True,
              'device_map': {'': 0}}
    if spec['role'] == 'detector_base':
        kwargs['quantization_config'] = BitsAndBytesConfig(load_in_4bit=True,
            bnb_4bit_use_double_quant=True, bnb_4bit_quant_type='nf4',
            bnb_4bit_compute_dtype=torch.bfloat16)
        # Match QLoraModel's omission of torch_dtype; report the effective dtype.
        report['load_mode'] = 'NF4_DOUBLE_QUANT_BF16_COMPUTE_NONQUANT_DTYPE_DEFAULT'
    elif spec['role'] == 'target':
        kwargs['torch_dtype'] = torch.bfloat16
        report['load_mode'] = 'BF16_NO_QUANTIZATION'
    else:
        kwargs.update(torch_dtype=torch.float32, output_attentions=True)
        report['load_mode'] = 'FP32_OUTPUT_ATTENTIONS_TRUE'
    report['stage'] = 'model_load'
    started = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(path, **kwargs)
    model.eval()
    torch.cuda.synchronize()
    report['load_seconds_including_disk_io'] = time.perf_counter() - started
    if any(parameter.device.type != 'cuda' for parameter in model.parameters()):
        raise RuntimeError('Some parameters are not on CUDA; no automatic CPU offload accepted')
    report['embedding_dtype'] = str(model.get_input_embeddings().weight.dtype)
    if spec['role'] == 'target' and model.get_input_embeddings().weight.dtype != torch.bfloat16:
        raise RuntimeError('Target embedding dtype differs from requested BF16')
    if spec['role'] == 'helper' and model.get_input_embeddings().weight.dtype != torch.float32:
        raise RuntimeError('Helper embedding dtype differs from requested FP32')
    report['device_map'] = {key: str(value) for key, value in getattr(model, 'hf_device_map', {}).items()}
    report['attention_implementation'] = getattr(model.config, '_attn_implementation', None)
    if spec['role'] == 'detector_base':
        import bitsandbytes as bnb
        quantized = [module for module in model.modules() if isinstance(module, bnb.nn.Linear4bit)]
        report['nf4_linear_count'] = len(quantized)
        report['nf4_quant_states_present'] = all(getattr(module.weight, 'quant_state', None) is not None for module in quantized)
        if not quantized or not report['nf4_quant_states_present']:
            raise RuntimeError('Full Mistral NF4 state not established')
    elif bool(getattr(model, 'is_quantized', False)):
        raise RuntimeError('Unexpected quantization for target/helper')
    report['model_load_verified'] = True
    report['generation_config'] = model.generation_config.to_dict()
    inputs = inputs.to('cuda:0')
    report['stage'] = 'synthetic_forward'
    started = time.perf_counter()
    with torch.inference_mode():
        output = model(**inputs)
    torch.cuda.synchronize()
    report['forward_seconds'] = time.perf_counter() - started
    report['logits_shape'] = list(output.logits.shape)
    report['logits_device'] = str(output.logits.device)
    report['finite_logits'] = bool(torch.isfinite(output.logits).all().item())
    report['attentions_returned'] = getattr(output, 'attentions', None) is not None
    if not report['finite_logits'] or output.logits.device.type != 'cuda':
        raise RuntimeError('Forward logits are non-finite or not on CUDA')
    report['synthetic_forward_verified'] = True
    del output
    report['stage'] = 'synthetic_short_generation'
    report['generation_overrides'] = {'max_new_tokens': 8, 'do_sample': False,
                                      'pad_token_id': tokenizer.eos_token_id}
    with torch.inference_mode():
        generated = model.generate(**inputs, **report['generation_overrides'])
    torch.cuda.synchronize()
    ids = generated[0, inputs['input_ids'].shape[1]:].tolist()
    if not ids or len(ids) > 8:
        raise RuntimeError('Invalid short generation token count')
    report['generated_token_ids'] = ids
    report['raw_synthetic_response'] = tokenizer.decode(ids, skip_special_tokens=False)
    report['short_generation_verified'] = True
    report['cuda'].update(peak_allocated_bytes=torch.cuda.max_memory_allocated(0),
                          peak_reserved_bytes=torch.cuda.max_memory_reserved(0))
    report.update(stage='complete', status='MODEL_LOAD_AND_SYNTHETIC_CHECK_PASSED')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', required=True, choices=['helper', 'detector_base', 'target'])
    args = parser.parse_args()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-model-load-' + args.role + '-' + uuid.uuid4().hex[:8]
    report = {'schema_version': 1, 'task_id': 'R0-5090-009', 'run_id': run_id,
              'role': args.role, 'hostname': platform.node(), 'platform': platform.system(),
              'python': sys.version, 'run_kind': 'debug', 'formal_samples_used': False,
              'formal_inference_executed': False, 'download_executed': False,
              'adapter_loaded': False, 'model_load_verified': False,
              'synthetic_forward_verified': False, 'short_generation_verified': False,
              'long_context_or_20000_token_budget_verified': False,
              'status': 'NOT_STARTED', 'stage': 'hardware_gate'}
    head = run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'])
    report['git_head'] = head.get('stdout', '').strip() if head.get('returncode') == 0 else None
    try:
        if platform.node().casefold() != 'desktop-b5pnbnc' or platform.system() != 'Linux':
            report['status'] = 'BLOCKED_WRONG_HOST_OR_SHELL'
        else:
            binary = shutil.which('nvidia-smi') or '/usr/lib/wsl/lib/nvidia-smi'
            inventory = run([binary, '--query-gpu=name,memory.total,memory.free,driver_version', '--format=csv'])
            report['hardware_gate'] = gpu_gate(inventory, 'RTX 5090', 30000)
            if not report['hardware_gate']['passed']:
                report['status'] = 'BLOCKED_HARDWARE'
            else:
                report['stage'] = 'local_file_inventory'
                spec = local_spec(ROOT, args.role)
                report['model_source'] = spec
                probe_runtime(spec, report)
    except Exception as exc:
        report.update(status='FAILED', error_type=type(exc).__name__,
                      error_message=str(exc)[:2000], traceback=traceback.format_exc(limit=8))
    folder = ROOT / 'coordination/returns' / run_id
    folder.mkdir(parents=True, exist_ok=False)
    output = folder / 'model_load.json'
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'return_path': output.relative_to(ROOT).as_posix(), 'role': args.role,
                      'status': report['status'], 'stage': report['stage'],
                      'model_load_verified': report['model_load_verified'],
                      'error_type': report.get('error_type')}, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'MODEL_LOAD_AND_SYNTHETIC_CHECK_PASSED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
