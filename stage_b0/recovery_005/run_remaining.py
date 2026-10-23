"""Verify existing800, then run only the uncompleted DS400 and Llama800."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'stage_b0/scoring_v2'))
from common import PLAN, save, sha
from contract import verify_contract
from review_004 import check as check_receipt


def data_drive(path):
    resolved = Path(path).resolve()
    assert resolved.is_relative_to(Path('/mnt/e')) or resolved.is_relative_to(Path('/mnt/d')), 'Use actual D/E path'
    return resolved


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check-only', action='store_true')
    ap.add_argument('--cache-root', type=Path, default=Path('/mnt/e/LongPIBench-Reproduction/models/b0-cache'))
    ap.add_argument('--raw-root', type=Path, default=Path('/mnt/e/LongPIBench-Reproduction/runs/stage-b0-v2'))
    args = ap.parse_args()
    plan, rows, contract = verify_contract()
    check_receipt()
    if args.check_only:
        print(json.dumps({'status': 'RECOVERY005_STATIC_GATE_PASSED_NOT_GPU_EXECUTED', 'reuse_existing_records': 800,
                          'new_roles': contract['serial_roles'], 'new_planned_records': 1200,
                          'cached_raw_verified_on_this_machine': False, 'recovery_contract_sha256': sha(HERE/'recovery_contract.json')}))
        return 0
    assert platform.system() == 'Linux' and platform.node().casefold() == 'desktop-b5pnbnc'
    cache = data_drive(args.cache_root); root = data_drive(args.raw_root)
    cache.mkdir(parents=True, exist_ok=True); root.mkdir(parents=True, exist_ok=True)
    assert shutil.disk_usage(root).free >= 4*1024**3, 'Need4GiB free; do not delete old results'
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-b0-recovery005-'+uuid.uuid4().hex[:8]
    lock = root/'active_job.lock'
    with lock.open('x', encoding='utf8') as f:
        f.write(run_id)
    job = root/run_id; job.mkdir(exist_ok=False)
    receipt = ROOT/'coordination/returns'/run_id; receipt.mkdir(exist_ok=False)
    state = {'task_id': 'B0-5090-005', 'run_id': run_id, 'status': 'STARTED',
             'input_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
             'execution_plan_sha256': sha(PLAN), 'recovery_contract_sha256': sha(HERE/'recovery_contract.json'),
             'cache_root': str(cache), 'raw_directory': str(job), 'reused_source_commit': contract['source_004_commit'],
             'roles': [], 'new_planned_records': 1200, 'thresholds_fitted': False, 'holdout_metrics_computed': False,
             'is_formal_paper_experiment': False, 'pg2_status': 'BLOCKED_HTTP403_NOT_RETRIED'}
    save(job/'job.json', state)
    code = 0
    try:
        for key, part in [('HF_HUB_CACHE', 'hub'), ('HF_MODULES_CACHE', 'modules'), ('HF_XET_CACHE', 'xet'),
                          ('HF_ASSETS_CACHE', 'assets'), ('TORCH_HOME', 'torch'), ('TEMP', 'temp'), ('TMP', 'temp')]:
            p = cache/part; p.mkdir(parents=True, exist_ok=True); os.environ[key] = str(p)
        from cached_scores import verify_cached
        cached = verify_cached(rows, plan)
        save(job/'cached800_verification.json', cached); save(receipt/'cached800_verification.json', cached)
        state['cached800_verification_sha256'] = sha(job/'cached800_verification.json')
        for role in contract['serial_roles']:
            command = [sys.executable, str(HERE/'collect_005.py'), '--role', role, '--job', str(job)]
            print(json.dumps({'stage': role, 'run_id': run_id}), flush=True)
            with (job/(role+'.runtime.log')).open('x', encoding='utf8') as log:
                proc = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding='utf8', errors='replace')
                for line in proc.stdout:
                    log.write(line); log.flush(); print(line, end='', flush=True)
                exit_code = proc.wait()
            item = {'role': role, 'exit_code': exit_code}
            completion = job/role/'completion.json'
            if completion.is_file():
                value = json.loads(completion.read_text(encoding='utf8'))
                item.update(status=value['status'], record_counts=value['record_counts'], completion_sha256=sha(completion))
                save(receipt/(role+'_collection.json'), value)
            state['roles'].append(item)
            if exit_code != 0:
                code = 3; break
        state['status'] = 'REMAINING1200_COLLECTED_REVIEW_REQUIRED' if code == 0 else 'RECOVERY005_FAILED_STOP_REVIEW'
    except Exception as exc:
        import traceback
        code = 3
        state.update(status='RECOVERY005_FAILED_STOP_REVIEW', error_type=type(exc).__name__,
                     error_frames=[{'file': Path(f.filename).name, 'line': f.lineno, 'function': f.name}
                                   for f in traceback.extract_tb(exc.__traceback__)])
        if isinstance(exc, AssertionError):
            state['assertion_reason'] = str(exc)[:500]
    finally:
        state['new_candidate_records_saved'] = sum(sum(r.get('record_counts', {}).values()) for r in state['roles'])
        state['raw_file_sha256'] = {p.relative_to(job).as_posix(): sha(p) for p in job.rglob('*.json')}
        save(job/'recovery_completion.json', state); save(receipt/'recovery_run.json', state)
        with (receipt/'REPORT.md').open('x', encoding='utf8', newline='\n') as f:
            f.write(f"# B0-5090-005接续回执\n\n状态：{state['status']}；输入commit：{state['input_commit']}。\n\n"
                    f"完整raw：{job}。004两分类器800条仅只读核验，没有模型重跑；新角色与完成数量见recovery_run.json。\n\n"
                    'DataSentinel结构审计在断言前保存loaded_structure_audit.json；本次未改模型、精度、原query或候选。'
                    '004旧失败原因仍只记录为候选，只有本次实测结构证据才支持进一步判断。'
                    '无阈值拟合、留出性能汇总、ASR或新算法。完成后停止等待审查。\n')
        if lock.read_text(encoding='utf8') == run_id:
            lock.unlink()
    print(json.dumps({'receipt': str(receipt.relative_to(ROOT)), 'status': state['status'], 'exit_code': code}), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
