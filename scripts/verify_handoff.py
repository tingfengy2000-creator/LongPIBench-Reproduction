"""Offline verification of pinned source data and repository handoff links."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
errors=[]
verified=0
manifest=json.loads((ROOT/'audit/evidence/source_manifest.json').read_text(encoding='utf-8'))
for row in manifest['files']:
    path=ROOT/row['path'].replace('\\','/')
    if not path.is_file():
        errors.append('Missing source: '+str(path.relative_to(ROOT)))
    elif hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
        errors.append('Source hash mismatch: '+str(path.relative_to(ROOT)))
    else:
        verified+=1
for md in [ROOT/'README.md',*list((ROOT/'audit').glob('*.md')),*list((ROOT/'coordination').rglob('*.md'))]:
    for target in re.findall(r'\]\(([^)]+)\)',md.read_text(encoding='utf-8')):
        if target.startswith(('https://','http://','#')):
            continue
        if not (md.parent/target).exists():
            errors.append('Broken link: '+str(md.relative_to(ROOT))+' -> '+target)
prepared=[json.loads(line) for line in (ROOT/'audit/prepared_inputs.jsonl').read_text(encoding='utf-8').splitlines()]
keys={(r['suite'],r['item_id'],r['attack']) for r in prepared}
if len(prepared)!=400 or len(keys)!=400:
    errors.append('Prepared-input count/uniqueness mismatch')
if any(r['target_inference_executed'] for r in prepared):
    errors.append('Prepared inputs mislabelled as model results')
report={'source_hashes_verified':verified,'source_manifest_original_download_errors_preserved':manifest['errors'],'prepared_input_rows':len(prepared),'link_and_hash_errors':errors,'scope':'Offline integrity and handoff links, not model inference'}
out=ROOT/'audit/handoff_validation.json'
with out.open('x',encoding='utf-8') as f:
    json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps(report,ensure_ascii=False,indent=2))
if errors:
    raise SystemExit(1)
