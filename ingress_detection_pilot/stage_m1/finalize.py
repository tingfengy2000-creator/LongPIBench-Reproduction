"""Seal additive M1 delivery; never change prior evidence."""
from datetime import datetime,timezone
import json
from pathlib import Path
import uuid
from prepare import sha,write

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]


def main():
    seal=json.loads((ROOT/'frozen_existing_files.json').read_text())['file_sha256']
    assert all(sha(REPO/n)==h for n,h in seal.items())
    plan=json.loads((ROOT/'plan.json').read_text())
    files={p.relative_to(REPO).as_posix():sha(p) for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    receipt={'task_id':'M1-5060-001','status':'COMPLETED_EXPLORATORY_MECHANISM_NOT_ALGORITHM',
        'run_id':plan['run_id'],'finished_utc':datetime.now(timezone.utc).isoformat(),
        'frozen_design_commit':'e43a80b21ae9e9b5142cb2097b10df1435c2556c','new_sources':24,
        'format_records':216,'document_records':72,'real_forward_calls':336,
        'historical_files_unchanged':len(seal),'original960_untouched':True,'R2_5090_accessed':False,
        'A':'Stable paired score sensitivity: 22/24 rise, median+0.054039 for no-CLS tail; components not fully separated',
        'B':'No pure-format classification flips; one confounded official constructed-document FP, not stable population FPR evidence',
        'C':'Limited further mechanism validation justified; no defense/LCMD development justified',
        'D':'Next candidate: tail semantic fragmentation/local context loss vs residual length; suggestion only',
        'task2':'20+20 bounded availability previews, no detector scoring; common long support unconfirmed; independent group design delivered',
        'not_done':['training','threshold adjustment','new defense algorithms','multiscale','800-source collection','new formal-paper test'],
        'files':files}
    write(ROOT/'completion_receipt.json',receipt)
    folder=REPO/'coordination/returns'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-m1-5060-001-'+uuid.uuid4().hex[:8])
    folder.mkdir(exist_ok=False)
    write(folder/'m1_receipt.json',{'task_id':receipt['task_id'],'status':receipt['status'],'run_id':receipt['run_id'],
        'full_receipt':'ingress_detection_pilot/stage_m1/completion_receipt.json','full_receipt_sha256':sha(ROOT/'completion_receipt.json')})
    report='''# M1-5060-001 completed (exploratory only)

Input/frozen design commit: e43a80b21ae9e9b5142cb2097b10df1435c2556c.
Run: 20261018T134643Z-m1-boundary-efd3eb5b.

24 newly authored benign fragments, 216 format/control records and72 official document records;336 actual CPU FP32 forwards. Same fixed Prompt Guard weights and official score/threshold. No-CLS tail raises22/24 scores, median+0.054039; no format-only classification flips. One constructed split-core document false positive is confounded by tail content and length; stable deployment FPR effect unproven.48 identical-input position reexecutions have zero logit/score differences.

Commands: prepare.py -> freeze commit -> run.py -> analyze.py -> audit_candidates.py -> verify.py -> finalize.py, all under ingress_detection_pilot/stage_m1/. Verification PASS,405 preexisting tracked hashes unchanged. Raw in stage_m1/raw/20261018T134643Z-m1-boundary-efd3eb5b/. Full report mechanism_report.md, design independent_data_design.md, environment/schema/figures and exact hashes included.

Task2 inspected only20+20 publicly available rows for token-length/source feasibility, no detector calls. Common long support and independent source counts remain unproven;800-source collection not started. Full raw candidate PII remains local E cache; only hashes/counts committed.

No training, threshold tuning, new defense, LCMD, multiscale, historical rerun or5090 R2 access. Further mechanism work is a recommendation only; no next phase launched.
'''
    with (folder/'REPORT.md').open('x',encoding='utf-8',newline='\n') as stream:stream.write(report)
    print(json.dumps({'delivery_files':len(files),'receipt_dir':str(folder),'historical_seal':'405/405 PASS'}))


if __name__=='__main__':main()
