"""Seal the M2 additive deliverables and ignored raw inventory after review."""
from datetime import datetime,timezone
import json
from pathlib import Path
import uuid
from prepare import sha,write

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]


def main():
    plan=json.loads((ROOT/'plan.json').read_text())
    old=json.loads((ROOT/'frozen_existing_files.json').read_text())['file_sha256']
    assert all(sha(REPO/n)==h for n,h in old.items())
    verify=json.loads((ROOT/'verification_full.json').read_text());assert verify['status']=='PASS'
    decision=json.loads((ROOT/'decision_review.json').read_text(encoding='utf-8'))
    paths=[REPO/'runs/20261018T152807Z-m2-context-4972b7f6',REPO/Path(plan['frozen_inputs_path']).parent]
    for phase in ['smoke','full']:
        receipt=json.loads((ROOT/(phase+'_receipt.json')).read_text())
        paths.append(Path(receipt['completion_path']).parent)
    inventory=[]
    for directory in paths:
        for path in sorted(directory.iterdir()):
            if path.is_file():inventory.append({'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path),'stored_in_git':False})
    write(ROOT/'raw_file_inventory.json',inventory)
    files={p.relative_to(REPO).as_posix():sha(p) for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    summary=json.loads((ROOT/'analysis_summary.json').read_text())
    receipt={'task_id':'M2-5060-001','status':'COMPLETED_EXPLORATORY_STOPPED_BEFORE_M3',
        'finished_utc':datetime.now(timezone.utc).isoformat(),'frozen_input_commit':'ccdd523',
        'full_run_input_commit':'88356a9','construction_run_id':plan['run_id'],
        'n_sources':40,'n_variants':80,'n_full_forwards':summary['forward_calls'],'n_smoke_forwards':176,
        'history_unchanged':len(old),'old960_and_M1_unchanged':True,'R2_5090_accessed':False,
        'decision':decision,'raw_inventory_sha256':sha(ROOT/'raw_file_inventory.json'),
        'raw_inventory_warning':'Full raw is local ignored E:/LongPIBench/runs; Git receipts are not full raw backup',
        'verification':'Independent numerical/ID/hash/confusion/McNemar checks PASS; plots inspected',
        'no_training_no_threshold_tuning_no_defense_algorithm':True,'no_M3_started':True,
        'file_sha256':files}
    write(ROOT/'completion_receipt.json',receipt)
    folder=REPO/'coordination/returns'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-m2-5060-001-'+uuid.uuid4().hex[:8])
    folder.mkdir(exist_ok=False)
    write(folder/'m2_receipt.json',{'task_id':receipt['task_id'],'status':receipt['status'],
        'decision':decision['decision'],'full_receipt':'ingress_detection_pilot/stage_m2/completion_receipt.json',
        'full_receipt_sha256':sha(ROOT/'completion_receipt.json')})
    text=f'''# M2-5060-001 completed, exploratory only

Frozen input commit ccdd523; full run input/analysis commit 88356a9. New 40 base sources, 80 benign/attack variants, 4-source/8-variant engineering smoke (176 forwards) and fresh full run ({summary['forward_calls']} forwards).

Decision: {decision['decision']}. See stage_m2/07_mechanism_analysis.md and08_go_no_go_report.md for Q1-Q7, all official/shadow/recovery conditions, paired uncertainty and unfavorable transitions. No algorithm or Stage M3 started.

Fixed Prompt Guard1209add6, original FP32 CPU scoring and>=0.5 threshold; official512 nonoverlap unchanged. Source-level paired resampling, full-token counterfactual coverage, all flip taxonomy and independent numerical verification are retained.437 historical tracked files including old960/M1 unchanged. No5090 R2 access, training, LCMD, threshold tuning or new defense.

Original construction failure preserved. Full new text/token/logits/raw/logs are LOCAL ignored E:/LongPIBench/runs, bound in stage_m2/raw_file_inventory.json; they are not uploaded to Git. Small manifest, reproducible construction/engine, reports, figures and hashes are committed separately.
'''
    with (folder/'REPORT.md').open('x',encoding='utf-8',newline='\n') as f:f.write(text)
    print(json.dumps({'artifacts':len(files),'receipt_directory':str(folder),'raw_files':len(inventory)}))


if __name__=='__main__':main()
