"""Clone exact official commits; optionally restore 200 pinned data files."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def git(*args):
    return subprocess.check_output(['git',*map(str,args)],text=True).strip()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-data',action='store_true')
    args=parser.parse_args()
    lock=json.loads((ROOT/'configs/upstream_lock.json').read_text(encoding='utf-8'))
    for name,repo in lock['repositories'].items():
        dest=ROOT/'upstream'/name
        if not dest.exists():
            dest.parent.mkdir(exist_ok=True)
            subprocess.run(['git','clone','--no-checkout',repo['url'],str(dest)],check=True)
            subprocess.run(['git','-C',str(dest),'checkout','--detach',repo['commit']],check=True)
        if git('-C',dest,'rev-parse','HEAD')!=repo['commit']:
            raise RuntimeError(f'{name}: existing checkout differs from lock; refusing to change it')
        if git('-C',dest,'status','--porcelain'):
            raise RuntimeError(f'{name}: checkout is dirty; refusing to continue')
        print(name+': '+repo['commit'])
    if args.download_data:
        rev=lock['dataset']['revision']
        manifest=json.loads((ROOT/'audit/evidence/source_manifest.json').read_text(encoding='utf-8'))
        entries=[e for e in manifest['files'] if e['path'].replace('\\','/').startswith('data/'+rev+'/')]
        if len(entries)!=200: raise ValueError('Expected exactly 200 data file hashes')
        def restore(e):
            rel=e['path'].replace('\\','/')
            dest=ROOT/rel
            if not dest.exists():
                path=rel.split('/',2)[2]
                url=f'https://huggingface.co/datasets/{lock["dataset"]["repo_id"]}/resolve/{rev}/{path}'
                with urllib.request.urlopen(url,timeout=60) as r: blob=r.read()
                if hashlib.sha256(blob).hexdigest()!=e['sha256']: raise ValueError('Remote hash mismatch: '+rel)
                dest.parent.mkdir(parents=True,exist_ok=True)
                with dest.open('xb') as f: f.write(blob)
            if hashlib.sha256(dest.read_bytes()).hexdigest()!=e['sha256']:
                raise ValueError('Local hash mismatch; refusing overwrite: '+rel)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(restore,entries))
        print('Pinned Email + Resume: 200/200 SHA256 verified')

if __name__=='__main__': main()
