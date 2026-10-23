"""Coordinator-only one-time derivation; preserves the frozen004 collector."""
import ast
import difflib
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'stage_b0/scoring_v2'))
from common import PLAN, load_inputs, sha, save


def build():
    base = ROOT/'stage_b0/scoring_v2/collect.py'
    load_inputs()
    old = base.read_text(encoding='utf8')
    new = old
    changes = [
        ('import argparse\n',
         'import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scoring_v2"))\nimport argparse\n'),
        ('''    assert whole.model.ft_model.active_adapters == ['default']
    assert whole.model.ft_model.generation_config.to_dict() == frozen['saved_generation_defaults']
    nf4 = [m for m in whole.model.base_model.modules() if type(m).__name__ == 'Linear4bit']
    assert len(nf4) == 224
    assert all(m.weight.quant_state is not None and m.compute_dtype == torch.bfloat16 for m in nf4)
''', '''    import bitsandbytes as bnb
    from quant_audit import inspect_structure
    structure = inspect_structure(whole, frozen['saved_generation_defaults'], bnb, torch)
    report['loaded_structure_audit'] = structure
    save(raw/'loaded_structure_audit.json', structure)
    if structure['failed_checks']:
        raise AssertionError('DATASENTINEL_STRUCTURE_CHECK_FAILED:'+','.join(structure['failed_checks']))
'''),
        ("choices=['piguard', 'prompt_guard_1', 'datasentinel', 'llama']", "choices=['datasentinel', 'llama']"),
        ('    plan, rows = load_inputs()  # Must precede network/torch/output creation.\n',
         '    plan, rows = load_inputs()  # Original004 condition remains frozen.\n    from contract import verify_contract\n    verify_contract()\n'),
        ("    report = {'status': 'STARTED', 'role': args.role,", "    report = {'task_id': 'B0-5090-005', 'recovery_contract_sha256': sha(Path(__file__).with_name('recovery_contract.json')),\n              'status': 'STARTED', 'role': args.role,"),
        ("        # No HTTP objects, credential-bearing URLs, exception dumps or automatic retries.\n",
         "        import traceback\n        report['error_frames'] = [{'file': Path(f.filename).name, 'line': f.lineno, 'function': f.name}\n                                  for f in traceback.extract_tb(exc.__traceback__)]\n        # No HTTP objects, credential-bearing URLs or automatic retries.\n"),
    ]
    for before, after in changes:
        assert new.count(before) == 1, 'Patch anchor changed'
        new = new.replace(before, after, 1)
    # Strongly scope the actual inference implementation changes.
    def functions(source):
        return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(source).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    a, b = functions(old), functions(new)
    assert set(a) == set(b)
    changed = sorted(k for k in a if a[k] != b[k])
    assert changed == ['collect_datasentinel', 'main'], changed
    target = HERE/'collect_005.py'
    with target.open('x', encoding='utf8', newline='\n') as f:
        f.write(new)
    patch = HERE/'collector_004_to_005.diff'
    with patch.open('x', encoding='utf8', newline='\n') as f:
        f.writelines(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                        fromfile='frozen004/collect.py', tofile='recovery005/collect_005.py'))
    save(HERE/'derivation.json', {'base_source': base.relative_to(ROOT).as_posix(), 'base_sha256': sha(base),
                                'base_execution_plan_sha256': sha(PLAN), 'derived_sha256': sha(target),
                                'diff_sha256': sha(patch), 'changed_functions': changed,
                                'llama_function_ast_identical': a['collect_llama'] == b['collect_llama'],
                                'datasentinel_inference_change': 'Only pre-forward structure verification replaced; query/generation/window/threshold unchanged',
                                'normalization': 'Source derivation uses LF; original source bytes preserved'})
    print('Derived005 collector; original004 source remains unchanged')


if __name__ == '__main__':
    build()
