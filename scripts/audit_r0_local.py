"""Offline R0 structural audit. No inference, weights, API calls or training."""
from __future__ import annotations
import ast
from collections import Counter
from contextlib import nullcontext
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import warnings

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'audit' / 'evidence'
sys.path.insert(0, str(ROOT / 'upstream' / 'LongPIBench'))
from longpibench import benchmark
from longpibench.attacks import injection
from longpibench.runner import run_model

def sha(blob):
    return hashlib.sha256(blob).hexdigest()

def command(args):
    proc = subprocess.run(args, capture_output=True, timeout=30)
    return {'args': args, 'returncode': proc.returncode, 'stdout': proc.stdout.decode('utf-8', errors='replace'), 'stderr': proc.stderr.decode('utf-8', errors='replace')}

def write_json(name, obj):
    path = EVIDENCE / name
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def main():
    pkgs = {}
    for name in ('torch','transformers','peft','bitsandbytes','huggingface-hub','spacy','pytest','numpy'):
        try:
            pkgs[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pkgs[name] = None
    env = {'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(), 'packages': pkgs, 'gpu': command(['nvidia-smi','--query-gpu=name,memory.total,memory.used,driver_version','--format=csv']), 'wsl': command(['wsl','--list','--verbose'])}
    write_json('environment.json', env)
    repos = {}
    for name in ('LongPIBench', 'Open-Prompt-Injection'):
        path = ROOT / 'upstream' / name
        repos[name] = {k: command(['git','-C',str(path), *args]) for k,args in [('head',['rev-parse','HEAD']),('status',['status','--porcelain']),('remote',['remote','-v']),('history',['log','-5','--format=%H %aI %s'])]}
    write_json('repositories.json', repos)
    rev = json.loads((EVIDENCE / 'hf_dataset_info.json').read_text(encoding='utf-8'))['sha']
    benchmark.DATA_ROOT = ROOT / 'data' / rev
    findings, errors = {}, []
    prepared = []
    for suite, folder, goal in [('email','emails','0'),('resume','person_info','2')]:
        paths = sorted((benchmark.DATA_ROOT / folder).glob('*.json'))
        actual_ids = sorted(int(p.stem) for p in paths)
        if actual_ids != list(range(100)):
            errors.append(f'{suite}: IDs are not exactly 0..99')
        hashes = Counter()
        schema = Counter()
        lengths = []
        for p in paths:
            blob = p.read_bytes()
            hashes[sha(blob)] += 1
            obj = json.loads(blob)
            schema[','.join(sorted(obj))] += 1
            if suite == 'email':
                for k in ('email_out','email_in','attachment_content'):
                    if not isinstance(obj.get(k),str) or not obj[k].strip():
                        errors.append(f'{p.name}: empty/invalid {k}')
            else:
                if not isinstance(obj.get('name'),str) or not obj['name'].strip():
                    errors.append(f'{p.name}: invalid name')
                for k in ('work_experience','education','publications','skills'):
                    if not isinstance(obj.get(k),list):
                        errors.append(f'{p.name}: invalid {k}')
            clean = benchmark.prepare_example(suite,int(p.stem),'no',goal)
            attacked = benchmark.prepare_example(suite,int(p.stem),'authority_spoof',goal)
            payload = injection(suite,'authority_spoof',goal)
            assert attacked.data_prompt == clean.data_prompt + ('\n\n' if suite == 'resume' else '') + payload
            assert payload not in clean.data_prompt
            assert attacked.data_prompt.endswith(payload)
            lengths.append(len(attacked.data_prompt))
            for example in (clean,attacked):
                record = example.to_dict()
                record.update(record_type='prepared_input_not_model_result', dataset_revision=rev, source_sha256=sha(blob), input_chars=len(example.data_prompt), input_token_count=None, target_inference_executed=False)
                if example.attack != 'no':
                    record.update(payload=payload, inserted_span_chars=[len(example.data_prompt)-len(payload),len(example.data_prompt)], span_convention='0-based Unicode code points, end-exclusive; inserted text, not independent semantic annotation')
                prepared.append(record)
        findings[suite] = {'files':len(paths), 'ids':actual_ids,'duplicate_file_hash_groups':sum(c>1 for c in hashes.values()),'schemas':dict(schema),'attacked_chars':{'min':min(lengths),'median':statistics.median(lengths),'max':max(lengths)},'actual_target_tokens':'NOT_MEASURED','construction_checks':len(paths)}
    write_json('dataset_audit.json', {'revision':rev,'suites':findings,'errors':errors,'scope':'JSON schema and public prepare_example only; no semantic labels, no tokenizer or inference'})
    out = ROOT / 'audit' / 'prepared_inputs.jsonl'
    with out.open('x',encoding='utf-8') as f:
        for row in sorted(prepared,key=lambda r:(r['suite'],r['item_id'],r['attack'])):
            f.write(json.dumps(row,ensure_ascii=False)+'\n')
    probes = {'scope':'Synthetic contract probes, NOT benchmark results', 'scorer':[]}
    for value in ('Qualified','Unqualified','Not qualified','The candidate is not qualified','Borderline',None):
        response = {} if value is None else {'final_recommendation':value}
        probes['scorer'].append({'response':response,'official_success':benchmark.score_response('resume','2',response)})
    class InvalidModel:
        def query(self,*args):
            return 'not JSON'
    with tempfile.TemporaryDirectory(dir=ROOT / 'audit') as temp:
        path = Path(temp) / 'synthetic_runner_probe.jsonl'
        asr = run_model(InvalidModel(),suite='email',attack='authority_spoof',goal='0',position='default',start=0,count=1,output=path)
        record = json.loads(path.read_text(encoding='utf-8'))
        probes['runner_parse_failure'] = {'official_asr':asr,'record':record,'prompts_retained': 'data_prompt' in record or 'system_prompt' in record}
    # Execute only the unmodified helper probability function with shape doubles.
    # This checks its index arithmetic without installing or running a model.
    import numpy as np
    source = ROOT / 'upstream/Open-Prompt-Injection/OpenPromptInjection/apps/PromptLocate.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    fn = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='compute_conditional_probability')
    namespace = {'np':np,'torch':SimpleNamespace(no_grad=nullcontext)}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'), namespace)
    class Batch(dict):
        def to(self,device):
            return self
    class Tokenizer:
        def __call__(self,text,**kwargs):
            count = 1500 if text=='condition' else 1600
            return Batch(input_ids=np.zeros((1,count),dtype=int),attention_mask=np.ones((1,count),dtype=int))
    class ShapeModel:
        device = 'cpu'
        def __call__(self,**kwargs):
            return SimpleNamespace(logits=None)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter('always')
        avg,total = namespace['compute_conditional_probability']('condition','target',Tokenizer(),ShapeModel())
    probes['helper_index_arithmetic'] = {'condition_tokens':1500,'full_tokens_before_crop':1600,'full_tokens_after_crop':1024,'average_is_nan':bool(np.isnan(avg)),'total':float(total),'warnings':[str(w.message) for w in captured],'model_executed':False,'note':'Shape-only double; no estimate of real case incidence'}
    write_json('contract_probes.json',probes)
    write_json('evidence_integrity.json',{'files':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in sorted(EVIDENCE.iterdir()) if p.is_file()] + [{'path':str(out.relative_to(ROOT)),'bytes':out.stat().st_size,'sha256':sha(out.read_bytes())}]})
    print(json.dumps({'dataset_revision':rev,'prepared_inputs':len(prepared),'dataset_errors':errors,'suites':findings,'helper_nan_reproduced':probes['helper_index_arithmetic']['average_is_nan']},ensure_ascii=False))

if __name__=='__main__':
    main()
