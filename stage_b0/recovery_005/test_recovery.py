import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from cached_scores import check_chunk, allowed_model_target
from quant_audit import inspect_layers

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


class RecoveryTests(unittest.TestCase):
    def test_class_name_collision_does_not_double_count_native_layers(self):
        Native = type('Linear4bit', (), {})
        Wrapper = type('Linear4bit', (), {})
        items = []
        for i in range(224):
            layer = Native()
            layer.weight = SimpleNamespace(quant_state=SimpleNamespace(quant_type='nf4', nested=True), device='cuda:0')
            layer.compute_dtype = 'bf16'
            items.extend([(f'layer{i}', Wrapper()), (f'layer{i}.base_layer', layer)])
        model = SimpleNamespace(named_modules=lambda: iter(items))
        result = inspect_layers(model, Native, 'bf16')
        self.assertEqual(result['legacy_class_name_count'], 448)
        self.assertEqual(result['native_count'], 224)
        self.assertTrue(result['native_count_224'])
        self.assertTrue(result['native_compute_dtype_matches'])

    def test_missing_native_quant_state_or_wrong_dtype_still_fails(self):
        Native = type('Linear4bit', (), {})
        layer = Native(); layer.weight = SimpleNamespace(quant_state=None, device='cpu'); layer.compute_dtype = 'fp32'
        result = inspect_layers(SimpleNamespace(named_modules=lambda: iter([('layer', layer)])), Native, 'bf16')
        self.assertFalse(result['native_quant_states_present'])
        self.assertFalse(result['native_compute_dtype_matches'])
        self.assertFalse(result['native_on_cuda'])

    def test_cached_wrong_softmax_cannot_pass(self):
        with self.assertRaises(AssertionError):
            check_chunk({'raw_logits': [0., 0.], 'class_softmax': [.1, .9], 'score': .9,
                         'native_argmax_label': 'injection'}, ['benign', 'injection'])

    def test_hf_sibling_blob_allowed_but_not_external_drive(self):
        self.assertTrue(allowed_model_target('/mnt/e/cache/hub/models--example/blobs/abc'))
        self.assertFalse(allowed_model_target('/mnt/c/cache/blob'))
        self.assertFalse(allowed_model_target('/mnt/e-other/cache/blob'))
        self.assertFalse(allowed_model_target('/mnt/e/../c/cache/blob'))

    def test_cached_risk_remains_max_not_sum(self):
        valid = {'raw_logits': [0., 0., 0.], 'class_softmax': [1/3]*3,
                 'score': 1/3, 'native_argmax_label': 'BENIGN'}
        check_chunk(valid, ['BENIGN', 'INJECTION', 'JAILBREAK'])
        with self.assertRaises(AssertionError):
            check_chunk(dict(valid, score=2/3), ['BENIGN', 'INJECTION', 'JAILBREAK'])

    def test_actual_llama_function_is_unchanged(self):
        def fn(path, name):
            return next(n for n in ast.parse(path.read_text(encoding='utf8')).body if isinstance(n, ast.FunctionDef) and n.name == name)
        old = fn(ROOT/'stage_b0/scoring_v2/collect.py', 'collect_llama')
        new = fn(HERE/'collect_005.py', 'collect_llama')
        self.assertEqual(ast.dump(old), ast.dump(new))

    def test_datasentinel_inference_after_structure_checks_is_unchanged(self):
        def tail(path):
            tree = ast.parse(path.read_text(encoding='utf8'))
            fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'collect_datasentinel')
            index = next(i for i, n in enumerate(fn.body) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                         and isinstance(n.value.func, ast.Attribute) and n.value.func.attr == 'update'
                         and any(k.arg == 'load_seconds' for k in n.value.keywords))
            return [ast.dump(n) for n in fn.body[index:]]
        self.assertEqual(tail(ROOT/'stage_b0/scoring_v2/collect.py'), tail(HERE/'collect_005.py'))


if __name__ == '__main__':
    unittest.main()
