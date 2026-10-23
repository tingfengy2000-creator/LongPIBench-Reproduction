"""Coordinator-only binding of added recovery files; never replaces the004 plan."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'stage_b0/scoring_v2'))
from common import PLAN, load_inputs, save, sha
from review_004 import SOURCE, RECEIPT, check


if __name__ == '__main__':
    load_inputs(); check()
    paths = [p for p in HERE.iterdir() if p.is_file() and p.suffix in ['.py', '.diff', '.json', '.md']
             and p.name not in ['recovery_contract.json', 'preparation_validation.json']]
    paths += sorted(RECEIPT.glob('*'))
    paths = [p for p in paths if p.is_file()]
    contract = {'task_id': 'B0-5090-005', 'status': 'FROZEN_RECOVERY_NOT_EXECUTED', 'source_004_commit': SOURCE,
                'base_execution_plan_sha256': sha(PLAN), 'serial_roles': ['datasentinel', 'llama'],
                'source_cached_records': 800, 'new_planned_records': 1200,
                'engineering_patch': 'Typed NF4 guard, pre-assertion structure dump and named traceback locations only',
                'historical_failure_cause_confirmed': False, 'models_or_inference_parameters_changed': False,
                'old_collector_and_plan_modified': False, 'holdout_metrics_computed': False,
                'file_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(paths))}}
    save(HERE/'recovery_contract.json', contract)
    print('Frozen005:', sha(HERE/'recovery_contract.json'))
