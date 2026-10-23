"""Serial fresh-process scoring for B0; no holdout metrics or threshold tuning."""
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

from common import ROOT, PLAN, load_inputs, save, sha


def on_data_drive(path):
    resolved = Path(path).resolve()
    assert resolved.is_relative_to(Path('/mnt/e')) or resolved.is_relative_to(Path('/mnt/d')), 'Use actual D/E path'
    return resolved


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check-only', action='store_true')
    ap.add_argument('--cache-root', type=Path, default=Path('/mnt/e/LongPIBench-Reproduction/models/b0-cache'))
    ap.add_argument('--raw-root', type=Path, default=Path('/mnt/e/LongPIBench-Reproduction/runs/stage-b0-v2'))
    args = ap.parse_args()
    plan, rows = load_inputs()
    if args.check_only:
        print(json.dumps({'status': 'EXPLORATORY_COLLECTION_INPUT_GATE_PASSED_NO_MODEL_LOADED',
                          'rows': len(rows), 'source_documents': len({r['source_document_id'] for r in rows}),
                          'roles': plan['serial_roles'], 'pg2': 'BLOCKED_HTTP_403_NOT_RUN',
                          'execution_plan_sha256': sha(PLAN)}))
        return 0
    assert platform.system() == 'Linux' and platform.node().casefold() == 'desktop-b5pnbnc', 'Use actual5090 WSL'
    cache = on_data_drive(args.cache_root); raw_root = on_data_drive(args.raw_root)
    cache.mkdir(parents=True, exist_ok=True); raw_root.mkdir(parents=True, exist_ok=True)
    assert shutil.disk_usage(cache).free >= 8*1024**3, 'Need8GiB free; preserve old evidence'
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-b0-scores-'+uuid.uuid4().hex[:8]
    lock_path = raw_root/'active_job.lock'
    # Exclusive lock is never guessed stale or silently overwritten.
    with lock_path.open('x', encoding='utf8') as f:
        f.write(run_id)
    job = raw_root/run_id; job.mkdir(exist_ok=False)
    receipt = ROOT/'coordination/returns'/run_id; receipt.mkdir(exist_ok=False)
    state = {'task_id': 'B0-5090-004', 'run_id': run_id, 'status': 'RUNNING',
             'input_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
             'hostname': platform.node(), 'execution_plan_sha256': sha(PLAN), 'raw_directory': str(job),
             'cache_root': str(cache), 'roles': [], 'pg2_status': 'BLOCKED_HTTP_403_NOT_RUN',
             'label_basis': 'EXPLORATORY_AI_REVIEW_NOT_HUMAN_GOLD', 'is_formal_paper_experiment': False,
             'thresholds_fitted': False, 'holdout_metrics_computed': False, 'no_sample_retries': True}
    save(job/'job.json', state)
    code = 0
    try:
        for role in plan['serial_roles']:
            command = [sys.executable, str(Path(__file__).with_name('collect.py')), '--role', role, '--job', str(job)]
            print(json.dumps({'stage': 'starting_role', 'role': role, 'run_id': run_id}), flush=True)
            with (job/(role+'.runtime.log')).open('x', encoding='utf8') as log:
                process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf8', errors='replace')
                for line in process.stdout:
                    log.write(line); log.flush(); print(line, end='', flush=True)
                exit_code = process.wait()
            manifest = job/role/'completion.json'
            item = {'role': role, 'exit_code': exit_code, 'completion_manifest_present': manifest.is_file()}
            if manifest.is_file():
                data = json.loads(manifest.read_text(encoding='utf8'))
                item.update(status=data['status'], record_counts=data['record_counts'],
                            completion_sha256=sha(manifest), raw_manifest=str(manifest))
                save(receipt/(role+'_collection.json'), data)
            state['roles'].append(item)
            if exit_code == 2:
                code = max(code, 2)  # Model access blocker only, preserve and continue independent roles.
            elif exit_code != 0:
                code = 3; break
        state['status'] = ('COLLECTION_FAILED_STOP_REVIEW' if code == 3 else
                           'PARTIAL_COLLECTION_MODEL_ACCESS_BLOCKED' if code == 2 else
                           'NON_PG2_EXPLORATORY_SCORES_COLLECTED_REVIEW_REQUIRED')
    except Exception as exc:
        code = 3
        state.update(status='SUPERVISOR_FAILED_STOP_REVIEW', error_type=type(exc).__name__)
    finally:
        state['candidate_records_saved'] = sum(sum(r.get('record_counts', {}).values()) for r in state['roles'])
        state['planned_candidate_role_pairs_excluding_pg2'] = 2000
        state['raw_manifest_sha256'] = {p.relative_to(job).as_posix(): sha(p) for p in job.rglob('*.json')}
        save(job/'job_completion.json', state)
        save(receipt/'collection_run.json', state)
        report = f'''# B0-5090-004探索性原始评分收集

状态：{state['status']}。输入commit：{state['input_commit']}。
执行配置SHA256：{state['execution_plan_sha256']}。

完整raw：{job}。分角色结果及退出码见collection_run.json。
PG2沿用003的固定版本403阻碍，本次未重试或替代。
本轮没有拟合阈值、汇总留出指标或进行业务目标验证；不是B0总体完成或正式论文证据。

标签为冻结AI探索标签。无模型/样本自动重跑、无阈值优化、无新算法。
时间包含tokenization、有限性检查和记录观察开销，不当作优化部署吞吐。
完成后停止等待协调端核对raw覆盖与评分，再另行冻结开发阈值及一次性留出汇总。
'''
        with (receipt/'REPORT.md').open('x', encoding='utf8', newline='\n') as f:
            f.write(report)
        if lock_path.read_text(encoding='utf8') == run_id:
            lock_path.unlink()  # Only our exact ephemeral lock; preserve every raw/receipt file.
    print(json.dumps({'receipt': str(receipt.relative_to(ROOT)), 'status': state['status'], 'exit_code': code}), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
