"""Download only public pinned inference files; never access credential stores."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent


def download(alias):
    meta = json.loads((ROOT / 'source_audit' / (alias + '-files.json')).read_text(encoding='utf-8'))
    folder = ROOT / 'models' / alias
    folder.mkdir(parents=True, exist_ok=True)
    names = {'config.json', 'model.safetensors', 'tokenizer.json', 'tokenizer_config.json',
             'special_tokens_map.json', 'added_tokens.json', 'spm.model', 'vocab.txt'}
    results = []
    for item in meta['siblings']:
        name = item['rfilename']
        if name not in names:
            continue
        path = folder / name
        url = f"https://huggingface.co/{meta['id']}/resolve/{meta['sha']}/{name}"
        if path.exists():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            digest = hashlib.sha256()
            count = 0
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'LongPIBench-ingress-pilot'}), timeout=60) as source, path.with_suffix(path.suffix + '.part').open('xb') as target:
                while chunk := source.read(1024**2):
                    target.write(chunk)
                    digest.update(chunk)
                    count += len(chunk)
                    if count % (32*1024**2) == 0:
                        print(alias, name, count, flush=True)
            digest = digest.hexdigest()
            path.with_suffix(path.suffix + '.part').rename(path)
        assert path.stat().st_size == item['size'], (alias, name, 'size')
        if item.get('lfs'):
            assert digest == item['lfs']['sha256'], (alias, name, 'LFS digest')
        results.append({'filename': name, 'bytes': path.stat().st_size, 'sha256': digest, 'url': url})
    report = {'alias': alias, 'repo_id': meta['id'], 'revision': meta['sha'], 'files': results}
    output = ROOT / 'source_audit' / (alias + '-download.json')
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print(alias, 'FILES_VERIFIED', flush=True)


if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(download, ['deberta', 'distilbert']))
