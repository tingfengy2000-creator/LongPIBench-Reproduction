"""Recovery005 code binding, in addition to the unchanged004 data/label gate."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'stage_b0/scoring_v2'))
from common import PLAN, load_inputs, sha


def verify_contract():
    plan, rows = load_inputs()
    contract = json.loads((HERE/'recovery_contract.json').read_text(encoding='utf8'))
    assert contract['task_id'] == 'B0-5090-005'
    assert contract['base_execution_plan_sha256'] == sha(PLAN)
    assert contract['serial_roles'] == ['datasentinel', 'llama']
    for name, digest in contract['file_sha256'].items():
        assert sha(ROOT/name) == digest, 'Recovery005 file changed: '+name
    return plan, rows, contract
