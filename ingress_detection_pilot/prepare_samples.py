"""Readonly public-data view; never alter the R0-R4 population or outputs."""
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
UPSTREAM = 'c7b80114ae56f65fb8019ec82afdb3df91e4ed65'
DATA = 'cdfdfdba8838911ec3d120d5bbf584c0afb280f2'
SEED = 'ingress-pilot-v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def benchmark():
    checkout = REPO / 'upstream/LongPIBench'
    head = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD']).decode().strip()
    dirty = subprocess.check_output(['git', '-C', str(checkout), 'status', '--porcelain', '--untracked-files=no'])
    assert head == UPSTREAM and not dirty.strip(), 'Pinned upstream changed'
    sys.path.insert(0, str(checkout))
    module = importlib.import_module('longpibench.benchmark')
    assert Path(module.__file__).resolve().is_relative_to(checkout.resolve())
    module.DATA_ROOT = REPO / 'data' / DATA
    return module


def build():
    module = benchmark()
    archived = [json.loads(line) for line in (REPO / 'audit/prepared_inputs.jsonl').read_text(encoding='utf-8').splitlines()]
    index = {(r['suite'], r['item_id'], r['attack']): r for r in archived}
    records, cases = [], []
    for domain, goal, position, folder in [('email', '0', 'last', 'emails'), ('resume', '2', 'footnote', 'person_info')]:
        ranked = sorted(range(100), key=lambda i: hashlib.sha256(f'{SEED}:{domain}:{i}'.encode()).hexdigest())[:20]
        for rank, item_id in enumerate(ranked):
            split = 'calibration' if rank < 12 else 'test'
            for attack in ['no', 'authority_spoof']:
                row = index[domain, item_id, attack]
                case = module.prepare_example(domain, item_id, attack, goal, position).to_dict()
                assert all(case[k] == row[k] for k in case)
                source = module.DATA_ROOT / folder / f'{item_id}.json'
                assert sha(source) == row['source_sha256']
                record = {'sample_id': f'{domain}-{item_id:03d}-' + ('clean' if attack == 'no' else 'authority_spoof'),
                    'source_document_id': f'{domain}-{item_id:03d}', 'item_id': item_id,
                    'domain': domain, 'label': int(attack != 'no'), 'attack_type': 'none' if attack == 'no' else attack,
                    'split': split, 'split_role': 'calibration' if split == 'calibration' else 'development_holdout_not_paper_test',
                    'source_json_sha256': row['source_sha256'],
                    'data_prompt_sha256': hashlib.sha256(case['data_prompt'].encode()).hexdigest(),
                    'dataset_revision': DATA, 'upstream_commit': UPSTREAM}
                records.append(record)
                cases.append((record, case))
    assert len(records) == 80 and len({r['source_document_id'] for r in records}) == 40
    for source in {r['source_document_id'] for r in records}:
        assert len({r['split'] for r in records if r['source_document_id'] == source}) == 1
    return records, cases


if __name__ == '__main__':
    records, _ = build()
    path = ROOT / 'sample_manifest.jsonl'
    with path.open('x', encoding='utf-8') as stream:
        for row in records:
            stream.write(json.dumps(row, sort_keys=True) + '\n')
    print('Frozen 80 documents, 40 sources; calibration=48 rows/24 sources; development holdout=32 rows/16 sources')
