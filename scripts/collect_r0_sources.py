"""Read-only network collection for R0; never downloads model weight files."""
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'audit' / 'evidence'
OUT.mkdir(parents=True, exist_ok=True)

def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'LongPIBench-R0-audit/1.0'}), timeout=60) as r:
        return r.read()

def save(name, url):
    p = OUT / name
    if p.exists():
        raise FileExistsError(p)
    p.write_bytes(fetch(url))
    return {'path': str(p.relative_to(ROOT)), 'url': url, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}

def main():
    sources = [
        ('longpibench.pdf', 'https://arxiv.org/pdf/2608.28411v1'),
        ('promptlocate.pdf', 'https://arxiv.org/pdf/2510.12252'),
        ('longpibench.html', 'https://arxiv.org/html/2608.28411v1'),
        ('promptlocate.html', 'https://arxiv.org/html/2510.12252'),
        ('hf_dataset_info.json', 'https://huggingface.co/api/datasets/RainWatcher/LongPIBench'),
        ('llama_model_info.json', 'https://huggingface.co/api/models/meta-llama/Llama-3.1-8B-Instruct'),
        ('mistral_model_info.json', 'https://huggingface.co/api/models/mistralai/Mistral-7B-v0.1'),
        ('helper_model_info.json', 'https://huggingface.co/api/models/openai-community/gpt2'),
    ]
    manifest, errors = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(save, n, u): (n, u) for n, u in sources}
        for f in concurrent.futures.as_completed(jobs):
            try:
                manifest.append(f.result())
            except Exception as e:
                errors.append({'source': jobs[f], 'error': str(e)})
    info_path = OUT / 'hf_dataset_info.json'
    if info_path.exists():
        info = json.loads(info_path.read_text(encoding='utf-8'))
        rev = info['sha']
        manifest.append(save('hf_tree.json', f'https://huggingface.co/api/datasets/RainWatcher/LongPIBench/tree/{rev}?recursive=true&limit=1000'))
        paths = [x['rfilename'] for x in info['siblings'] if x['rfilename'].startswith(('emails/', 'person_info/')) and x['rfilename'].endswith('.json')]
        def dataset_file(path):
            dest = ROOT / 'data' / rev / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                raise FileExistsError(dest)
            blob = fetch(f'https://huggingface.co/datasets/RainWatcher/LongPIBench/resolve/{rev}/{path}')
            dest.write_bytes(blob)
            return {'path': str(dest.relative_to(ROOT)), 'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob)}
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            jobs = {pool.submit(dataset_file, p): p for p in paths}
            for f in concurrent.futures.as_completed(jobs):
                try:
                    manifest.append(f.result())
                except Exception as e:
                    errors.append({'source': jobs[f], 'error': str(e)})
    (OUT / 'source_manifest.json').write_text(json.dumps({'collected_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'files': manifest, 'errors': errors}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'files': len(manifest), 'errors': errors, 'dataset_revision': info.get('sha') if info_path.exists() else None}))

if __name__ == '__main__':
    main()
