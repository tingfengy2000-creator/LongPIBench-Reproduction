"""R0-5090-010/011: local adapter staging and isolated debug checks."""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import logging
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import subprocess
import sys
import traceback
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.local_model_probe import local_spec, tokenize_synthetic_prompt
from scripts.verify_aux_downloads import digest_stream
from scripts.remote_preflight import run
from repro.hardware import gpu_gate

AUX_RECEIPT = 'coordination/returns/20261018T023636Z-aux-downloads-fe64f023/aux_downloads.json'
ADAPTER_DIRS = {
    'large': 'detector_large/checkpoint-5000',
    'small': 'detector_small/checkpoint-500',
    'oracle': '7_1000_naive_minimax_mistral_3_1_backend_llama3_revise_beta_1_balance_finetune/checkpoint-500',
}
EXPECTED = {'torch': '2.7.1+cu128', 'transformers': '4.51.3', 'bitsandbytes': '0.46.1',
            'accelerate': '1.6.0', 'peft': '0.15.2', 'spacy': '3.8.7'}
BASE_INPUT_EMBEDDING = 'base_model.model.model.embed_tokens.weight'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def file_sha(path):
    with Path(path).open('rb') as stream:
        return digest_stream(stream)


def load_source(root):
    receipt_path = root / AUX_RECEIPT
    receipt = read_json(receipt_path)
    plan = read_json(root / 'configs/offline_transfer_manifest.json')
    if receipt['task_id'] != 'R0-5090-007' or receipt['status'] != 'FILES_CHECKED_NOT_MODEL_LOADED':
        raise ValueError('007 source receipt not accepted')
    return receipt, plan, file_sha(receipt_path)


def extract_inference(archive_path, pack, row, destination):
    """Copy only six manifest-approved JSON/safetensors members; never extractall."""
    expected = {f['member']: f for f in row['files']}
    if set(expected) != {f['name'] for f in pack['inference_files']}:
        raise ValueError('007 member list differs from fixed manifest')
    copied = []
    with zipfile.ZipFile(archive_path) as archive:
        for item in pack['inference_files']:
            name = item['name']
            relative = PurePosixPath(name)
            if (relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name
                    or relative.name not in {'adapter_config.json', 'adapter_model.safetensors'}):
                raise ValueError('Unsafe or non-inference archive member')
            if archive.namelist().count(name) != 1:
                raise ValueError('Missing or duplicate inference member')
            info = archive.getinfo(name)
            if info.file_size != item['bytes'] or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Unexpected inference member size or symlink')
            target = destination.joinpath(*relative.parts)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError('Inference output escapes unique destination')
            target.parent.mkdir(parents=True, exist_ok=True)
            sha = hashlib.sha256()
            count = 0
            with archive.open(info) as src, target.open('xb') as dst:
                while chunk := src.read(8 * 1024**2):
                    count += len(chunk)
                    if count > item['bytes']:
                        raise ValueError('Inference member exceeds fixed size')
                    dst.write(chunk)
                    sha.update(chunk)
            if count != item['bytes'] or sha.hexdigest() != expected[name]['sha256_first_observed']:
                raise ValueError('Extracted member differs from accepted 007 hash')
            if relative.name == 'adapter_config.json' and read_json(target) != pack['adapter_configs'][name]:
                raise ValueError('Extracted adapter config differs from audit')
            copied.append({'member': name, 'size_bytes': count, 'sha256': sha.hexdigest()})
    return copied


def versions():
    return {name: importlib.metadata.version(name) for name in EXPECTED}


def model_distribution():
    try:
        return importlib.metadata.version('en-core-web-sm')
    except importlib.metadata.PackageNotFoundError:
        return None


def check_installed_wheel(wheel):
    import en_core_web_sm
    package_root = Path(en_core_web_sm.__file__).resolve().parent
    checked = 0
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            if not info.is_dir() and info.filename.startswith('en_core_web_sm/'):
                target = package_root / info.filename.removeprefix('en_core_web_sm/')
                with archive.open(info) as stream:
                    expected = digest_stream(stream)
                if file_sha(target) != expected:
                    raise ValueError('Installed spaCy model differs from accepted wheel')
                checked += 1
    if not checked:
        raise ValueError('No spaCy package members checked')
    return checked


def prepare(report):
    receipt, plan, sha = load_source(ROOT)
    report.update(source_receipt=AUX_RECEIPT, source_receipt_sha256=sha)
    resource = Path(receipt['download_dir']).resolve(strict=True)
    report['resource_dir'] = str(resource)
    report['stage'] = 'source_hashes'
    rows = {row['filename']: row for row in receipt['results']}
    for pack in plan['aux_archives']:
        path = resource / pack['filename']
        if (path.stat().st_size != pack['observed_size_bytes'] or
                file_sha(path) != rows[path.name]['archive_sha256_first_observed']):
            raise ValueError('Archive differs from accepted 007 receipt')
    wheel = resource / plan['spacy_model']['filename']
    if (wheel.stat().st_size != plan['spacy_model']['size_bytes'] or
            file_sha(wheel) != rows[wheel.name]['sha256_first_observed']):
        raise ValueError('Wheel differs from accepted 007 receipt')
    destination = ROOT / 'models' / ('runtime-aux-' + report['run_id'])
    destination.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(destination.parent).free < 3 * 1024**3:
        raise RuntimeError('Need 3GiB free on models destination; do not move or delete existing resources')
    destination.mkdir(exist_ok=False)
    report.update(prepared_dir=str(destination.resolve()), extracted_files=[])
    report['stage'] = 'inference_only_extraction'
    for pack in plan['aux_archives']:
        report['extracted_files'].extend(extract_inference(
            resource / pack['filename'], pack, rows[pack['filename']], destination))
    report['adapter_paths'] = {name: str((destination / relative).resolve()) for name, relative in ADAPTER_DIRS.items()}
    report['stage'] = 'spacy_model_install'
    report['packages_before'] = versions()
    if report['packages_before'] != EXPECTED:
        raise RuntimeError('Core packages differ from accepted candidate stack')
    installed = model_distribution()
    report['spacy_model_before'] = installed
    if installed not in (None, '3.8.0'):
        raise RuntimeError('Different spaCy model already installed; do not replace it')
    if installed is None:
        command = [sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps', str(wheel)]
        report['install_command'] = command
        subprocess.run(command, check=True, stdout=sys.stdout, stderr=sys.stderr)
    report['spacy_model_after'] = model_distribution()
    report['packages_after'] = versions()
    if report['spacy_model_after'] != '3.8.0' or report['packages_after'] != report['packages_before']:
        raise RuntimeError('Unexpected spaCy model/core package changes')
    report['installed_wheel_package_members_verified'] = check_installed_wheel(wheel)
    report['pip_check_returncode'] = subprocess.run([sys.executable, '-m', 'pip', 'check'],
        stdout=sys.stdout, stderr=sys.stderr).returncode
    if report['pip_check_returncode']:
        raise RuntimeError('pip check failed; do not repair dependencies on execution host')
    report.update(status='INFERENCE_FILES_STAGED_SPACY_INSTALLED', stage='complete',
                  spacy_model_installed_verified=True)


def prepared_source(path, report):
    path = path.resolve(strict=True)
    if not path.is_relative_to((ROOT / 'coordination/returns').resolve()):
        raise ValueError('Prepared receipt must be inside coordination/returns')
    data = read_json(path)
    source, plan, sha = load_source(ROOT)
    if (data['task_id'] != 'R0-5090-010' or data['status'] != 'INFERENCE_FILES_STAGED_SPACY_INSTALLED'
            or data['source_receipt_sha256'] != sha):
        raise ValueError('Invalid prepared receipt or changed 007 source')
    destination = Path(data['prepared_dir']).resolve(strict=True)
    if not destination.is_relative_to((ROOT / 'models').resolve()):
        raise ValueError('Prepared adapters outside repository models storage')
    report.update(prepared_receipt=path.relative_to(ROOT).as_posix(), prepared_receipt_sha256=file_sha(path),
                  source_receipt=AUX_RECEIPT, source_receipt_sha256=sha)
    return data, source, plan, destination


def validate_adapter_keys(saved, exported, required_adapter, report):
    """Require every saved and active adapter key; classify only known base extra."""
    saved, exported, required_adapter = set(saved), set(exported), set(required_adapter)
    missing = saved - exported
    unsaved_adapter = required_adapter - saved
    extra = exported - saved
    unexplained = extra - {BASE_INPUT_EMBEDDING}
    report['tensor_key_audit'] = {
        'policy_version': 2, 'saved_count': len(saved), 'exported_count': len(exported),
        'required_adapter_count': len(required_adapter), 'missing_in_model': sorted(missing),
        'active_adapter_keys_absent_from_file': sorted(unsaved_adapter),
        'extra_exported_keys': sorted(extra), 'unexplained_extra_keys': sorted(unexplained),
        'base_extra_verified': False if extra else None,
    }
    if not saved or not any('lora_' in k for k in saved) or not required_adapter:
        raise ValueError('No active LoRA tensors to verify')
    if missing or unsaved_adapter or unexplained:
        raise ValueError('Missing saved/active adapter tensor or unexplained exported tensor')
    return extra


def verify_base_input_embedding(model, state, base_path, report):
    """The exporter may add input embeddings absent from the adapter file.

    Prove that this one extra is the actual input embedding and still equals
    the accepted fixed base snapshot; never ignore an arbitrary extra tensor.
    """
    import torch
    from safetensors import safe_open
    tensor = state[BASE_INPUT_EMBEDDING]
    embedding = model.get_input_embeddings().weight
    if (tensor.data_ptr() != embedding.data_ptr() or tensor.device != embedding.device
            or tensor.shape != embedding.shape):
        raise ValueError('Known extra key is not the actual model input embedding')
    index_path = base_path / 'model.safetensors.index.json'
    index = read_json(index_path)
    key = 'model.embed_tokens.weight'
    shard_name = index['weight_map'][key]
    plan = read_json(ROOT / 'configs/offline_transfer_manifest.json')
    files = next(m['files'] for m in plan['hf_models'] if m['role'] == 'detector_base')
    fixed_file = next(f for f in files if f['filename'] == shard_name)
    if Path(shard_name).name != shard_name or not shard_name.endswith('.safetensors'):
        raise ValueError('Unsafe or unexpected fixed base shard')
    shard = base_path / shard_name
    # HF snapshot files are symlinks into the sibling blobs directory; keep
    # those accepted cache links intact rather than requiring physical nesting.
    if shard.stat().st_size != fixed_file['size_bytes']:
        raise ValueError('Fixed base shard changed size')
    with safe_open(str(shard), framework='pt', device='cpu') as archive:
        expected = archive.get_tensor(key)
        actual = tensor.detach().cpu()
        if actual.shape != expected.shape or not torch.equal(actual, expected.to(actual.dtype)):
            raise ValueError('Extra input embedding differs from the fixed base snapshot')
    report['base_input_embedding_check'] = {
        'exported_key': BASE_INPUT_EMBEDDING, 'base_key': key, 'shard': shard_name,
        'resolved_shard_path': str(shard.resolve()),
        'index_sha256': file_sha(index_path), 'shape': list(actual.shape), 'dtype': str(actual.dtype),
        'equals_base_after_dtype_cast': True, 'is_actual_input_embedding': True,
        'file_check_scope': 'Prior accepted shard digest plus current size; exact embedding tensor comparison',
    }
    report['tensor_key_audit']['base_extra_verified'] = True


def adapter_probe(name, prepared, report):
    data, source, plan, destination = prepared_source(prepared, report)
    adapter_path = destination / ADAPTER_DIRS[name]
    files = [f for row in source['results'] for f in row.get('files', [])
             if PurePosixPath(f['member']).parent.as_posix() == ADAPTER_DIRS[name]]
    if len(files) != 2:
        raise ValueError('Adapter source must have exactly JSON and safetensors')
    for f in files:
        actual = destination / f['member']
        if not actual.resolve().is_relative_to(destination) or file_sha(actual) != f['sha256_first_observed']:
            raise ValueError('Staged adapter no longer matches accepted 007 member')
    report.update(adapter=name, adapter_path=str(adapter_path), adapter_files=files, stage='cuda_runtime')
    report['packages'] = versions()
    if report['packages'] != EXPECTED:
        raise RuntimeError('Core packages differ from accepted stack')
    import torch
    import bitsandbytes as bnb
    from peft import PeftModel, get_peft_model_state_dict
    from safetensors import safe_open
    props = torch.cuda.get_device_properties(0)
    free, total = torch.cuda.mem_get_info()
    report['cuda'] = {'name': props.name, 'free_before_bytes': free, 'total_bytes': total}
    if '5090' not in props.name or total < 30000 * 1024**2 or free < 10 * 1024**3:
        raise RuntimeError('Wrong CUDA device or less than 10GiB free; preserve other jobs')
    torch.cuda.reset_peak_memory_stats()
    spec = local_spec(ROOT, 'detector_base')
    report['model_source'] = spec
    config_path = ROOT / 'upstream/Open-Prompt-Injection/configs/model_configs/mistral_config.json'
    config = read_json(config_path)
    report['config_template_sha256'] = file_sha(config_path)
    config['model_info']['name'] = spec['resolved_path']
    config['params'].update(ft_path=str(adapter_path), gpus=['0'], device='cuda', seed=42)
    report['debug_model_config'] = config
    from repro.opi_loader import load_opi_core
    core = load_opi_core()
    report['opi_provenance'] = core.provenance
    report['stage'] = 'original_datasentinel_constructor'
    detector = core.DataSentinelDetector(config)
    model = detector.model.ft_model
    if not isinstance(model, PeftModel) or any(p.device.type != 'cuda' for p in model.parameters()):
        raise RuntimeError('PEFT model missing or some parameters offloaded from CUDA')
    quantized = [m for m in model.modules() if isinstance(m, bnb.nn.Linear4bit)]
    report.update(nf4_linear_count=len(quantized), nf4_quant_states_present=bool(quantized) and
                  all(getattr(m.weight, 'quant_state', None) is not None for m in quantized),
                  active_adapters=list(model.active_adapters))
    if len(quantized) != 224 or not report['nf4_quant_states_present'] or report['active_adapters'] != ['default']:
        raise RuntimeError('Unexpected NF4/active adapter state')
    report['stage'] = 'loaded_tensor_comparison'
    # Include saved base embeddings/lm_head when present, not just LoRA matrices.
    state = get_peft_model_state_dict(model, adapter_name='default', save_embedding_layers=True)
    required_adapter = get_peft_model_state_dict(model, adapter_name='default', save_embedding_layers=False)
    matched = []
    with safe_open(str(adapter_path / 'adapter_model.safetensors'), framework='pt', device='cpu') as archive:
        keys = set(archive.keys())
        extra = validate_adapter_keys(keys, state, required_adapter, report)
        if extra:
            verify_base_input_embedding(model, state, Path(spec['resolved_path']), report)
        for key in sorted(keys):
            actual = state[key].detach().cpu()
            expected = archive.get_tensor(key)
            if actual.shape != expected.shape or not torch.equal(actual, expected.to(actual.dtype)):
                raise ValueError('Loaded tensor differs from saved adapter: ' + key)
            matched.append({'key': key, 'shape': list(actual.shape), 'dtype': str(actual.dtype)})
    report.update(adapter_loaded_verified=True, tensors_matched_after_dtype_cast=matched)
    del state, required_adapter
    report['stage'] = 'synthetic_forward'
    sample = 'A synthetic document contains a meeting scheduled for Tuesday.'
    from importlib import import_module
    instruction = import_module(core.DataSentinelDetector.__module__).kad_instruction()
    message = instruction + '\nText: ' + detector.preprocessing(sample)
    suffix = '\n' if name == 'oracle' else '\n### Response: '
    prompt = detector.model.formatting_func(message) + suffix
    inputs = detector.model.tokenizer(prompt, return_tensors='pt').to('cuda')
    report.update(synthetic_sample=sample, synthetic_formatted_prompt=prompt,
                  input_token_ids=inputs['input_ids'][0].tolist(),
                  generation_config=model.generation_config.to_dict())
    model.eval()
    with torch.inference_mode():
        output = model(**inputs)
    report['finite_cuda_logits'] = output.logits.device.type == 'cuda' and bool(torch.isfinite(output.logits).all().item())
    if not report['finite_cuda_logits']:
        raise RuntimeError('Non-finite or non-CUDA synthetic logits')
    del output
    report['stage'] = 'original_synthetic_query'
    original_generate = model.generate
    query_name = 'query_localization' if name == 'oracle' else 'query'
    original_query = getattr(detector.model, query_name)

    def capture_generate(*args, **kwargs):
        report['actual_generation_kwargs'] = {k: v for k, v in kwargs.items() if k not in {'input_ids', 'attention_mask'}}
        report['actual_input_token_ids'] = kwargs['input_ids'][0].tolist()
        generated = original_generate(*args, **kwargs)
        report['generated_token_ids'] = generated[0, kwargs['input_ids'].shape[1]:].tolist()
        return generated

    def capture_query(*args, **kwargs):
        response = original_query(*args, **kwargs)
        report['raw_synthetic_query_response'] = response
        return response

    # Transparent observation of the original detect/query calls; arguments and
    # returned objects are unchanged. Restore both methods even on exceptions.
    model.generate = capture_generate
    setattr(detector.model, query_name, capture_query)
    try:
        decision = detector.query(sample) if name == 'oracle' else detector.detect(sample)
    finally:
        model.generate = original_generate
        setattr(detector.model, query_name, original_query)
    if decision not in (0, 1) or not 0 < len(report['generated_token_ids']) <= 10:
        raise RuntimeError('Invalid original synthetic query result')
    if report['actual_input_token_ids'] != report['input_token_ids']:
        raise RuntimeError('Observed query prompt differs from checked forward prompt')
    report.update(synthetic_decision=decision, original_query_verified=True, stage='complete',
                  status='ADAPTER_LOAD_AND_SYNTHETIC_QUERY_PASSED')
    torch.cuda.synchronize()
    report['cuda'].update(peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                          peak_reserved_bytes=torch.cuda.max_memory_reserved())


def spacy_probe(prepared, report):
    prepared_source(prepared, report)
    report['packages'] = versions()
    if report['packages'] != EXPECTED:
        raise RuntimeError('Core packages differ from accepted candidate stack')
    import spacy
    from repro.opi_loader import load_opi_core
    if spacy.__version__ != '3.8.7' or model_distribution() != '3.8.0':
        raise RuntimeError('spaCy/model version differs from accepted candidate')
    core = load_opi_core()
    report['opi_provenance'] = core.provenance
    report['stage'] = 'original_initialize_spacy'
    instance = core.PromptLocate.__new__(core.PromptLocate)
    core.PromptLocate.initialize_spacy(instance)
    report.update(active_pipes=list(instance.nlp.pipe_names), disabled_pipes=list(instance.nlp.disabled))
    sample = 'First sentence. Second sentence!\nThird sentence?'
    doc = instance.nlp(sample)
    spans = [{'text': s.text, 'start': s.start_char, 'end': s.end_char} for s in doc.sents]
    if not spans or any(sample[s['start']:s['end']] != s['text'] for s in spans):
        raise RuntimeError('Sentence spans do not map to the synthetic source')
    report.update(synthetic_sample=sample, sentence_spans=spans, spacy_initialization_verified=True,
                  status='ORIGINAL_SPACY_INITIALIZATION_PASSED', stage='complete')


def target_tokenizer_probe(report):
    report['packages'] = versions()
    if report['packages'] != EXPECTED:
        raise RuntimeError('Core packages differ from accepted candidate stack')
    from transformers import AutoTokenizer
    spec = local_spec(ROOT, 'target')
    report['model_source'] = spec
    tokenizer = AutoTokenizer.from_pretrained(spec['resolved_path'], local_files_only=True,
                                              token=False, trust_remote_code=False)
    inputs = tokenize_synthetic_prompt(tokenizer, 'target', report)
    ids = inputs['input_ids'][0].tolist()
    direct = tokenizer.apply_chat_template(report['synthetic_messages'], tokenize=True, add_generation_prompt=True)
    report['input_token_ids'] = ids
    if ids != direct or ids[0] != tokenizer.bos_token_id or ids[1] == tokenizer.bos_token_id:
        raise RuntimeError('Rendered tokenization differs from direct chat template or duplicates BOS')
    report.update(actual_tokenizer_verified=True, status='TARGET_SINGLE_BOS_TOKENIZER_PASSED', stage='complete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, choices=['prepare', 'spacy', 'adapter', 'target-tokenizer'])
    parser.add_argument('--prepared-report', type=Path)
    parser.add_argument('--adapter', choices=ADAPTER_DIRS)
    parser.add_argument('--task-id', choices=['R0-5090-010', 'R0-5090-011'], default='R0-5090-010')
    args = parser.parse_args()
    if args.stage in {'spacy', 'adapter'} and args.prepared_report is None:
        parser.error('--prepared-report is required for spacy/adapter')
    if args.stage == 'adapter' and args.adapter is None:
        parser.error('--adapter is required for adapter stage')
    if args.task_id == 'R0-5090-011' and args.stage != 'adapter':
        parser.error('011 only resumes adapter stages; do not rerun accepted preparation/CPU checks')
    label = args.stage + ('-' + args.adapter if args.adapter else '')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-aux-runtime-' + label + '-' + uuid.uuid4().hex[:8]
    folder = ROOT / 'coordination/returns' / run_id
    folder.mkdir(parents=True, exist_ok=False)
    report = {'schema_version': 1, 'task_id': args.task_id, 'run_id': run_id,
              'operation': args.stage, 'hostname': platform.node(), 'platform': platform.system(),
              'run_kind': 'debug', 'formal_samples_used': False, 'formal_inference_executed': False,
              'formal_checkpoint_selected': False, 'full_promptlocate_constructor_verified': False,
              'adapter_loaded_verified': False, 'status': 'NOT_STARTED', 'stage': 'host_gate',
              'git_head': run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).get('stdout', '').strip()}
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_IMPLICIT_TOKEN='1',
                      CUDA_VISIBLE_DEVICES='0', PIP_NO_INDEX='1', PIP_CONFIG_FILE=os.devnull)
    try:
        with (folder / 'runtime.log').open('x', encoding='utf-8') as log:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                handler = logging.StreamHandler(log)
                logging.getLogger().addHandler(handler)
                try:
                    if platform.node().casefold() != 'desktop-b5pnbnc' or platform.system() != 'Linux':
                        raise RuntimeError('Must execute on actual 5090 host in WSL')
                    inventory = run([shutil.which('nvidia-smi') or '/usr/lib/wsl/lib/nvidia-smi',
                        '--query-gpu=name,memory.total,memory.free,driver_version', '--format=csv'])
                    report['hardware_gate'] = gpu_gate(inventory, 'RTX 5090', 30000)
                    if not report['hardware_gate']['passed']:
                        raise RuntimeError('5090 hardware gate failed')
                    if args.stage == 'prepare':
                        prepare(report)
                    elif args.stage == 'spacy':
                        spacy_probe(args.prepared_report, report)
                    elif args.stage == 'target-tokenizer':
                        target_tokenizer_probe(report)
                    else:
                        adapter_probe(args.adapter, args.prepared_report, report)
                finally:
                    logging.getLogger().removeHandler(handler)
    except Exception as exc:
        report.update(status='FAILED', error_type=type(exc).__name__, error_message=str(exc)[:2000],
                      traceback=traceback.format_exc(limit=12))
    output = folder / 'aux_runtime.json'
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'return_path': output.relative_to(ROOT).as_posix(), 'status': report['status'],
                      'stage': report['stage'], 'error_type': report.get('error_type')}, indent=2))
    return 2 if report['status'] == 'FAILED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
