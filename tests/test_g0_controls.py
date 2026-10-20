"""Frozen-plan/data-integrity tests; no real detector inference."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from g0_resume_diagnosis.run_controls import PLAN, PLAN_SHA, RawLogitObserver


class FrozenControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads((ROOT / PLAN).read_text(encoding='utf-8'))

    def test_frozen_identity_and_exact_counts(self):
        self.assertEqual(hashlib.sha256((ROOT / PLAN).read_bytes()).hexdigest(), PLAN_SHA)
        self.assertEqual(Counter(c['condition'] for c in self.plan['controls']),
                         {'natural_full': 4, 'payload_only': 2, 'crossed_prefix': 16, 'intentional_payload_exclusion': 4})
        self.assertEqual(self.plan['sample_selection'], [['email', 0], ['email', 50], ['resume', 0], ['resume', 50]])

    def test_common_lengths_and_all_predeclared_pairs(self):
        m = self.plan['minimum_clean_body_tokens']
        self.assertEqual(self.plan['shared_body_lengths'], [64*(m//128), 64*(m//64)])
        self.assertEqual(len(self.plan['cross_domain_pairs']), 8)
        for pair in self.plan['cross_domain_pairs']:
            self.assertTrue(pair['length_matched_within8'])
            rows = [next(c for c in self.plan['controls'] if c['control_id'] == i) for i in pair['control_ids']]
            self.assertEqual(rows[0]['payload_sha256'], rows[1]['payload_sha256'])
            self.assertEqual(rows[0]['input_token_count'], rows[1]['input_token_count'])

    def test_original_payloads_and_intentional_exclusions(self):
        archive = [json.loads(l) for l in (ROOT / 'audit/prepared_inputs.jsonl').read_text(encoding='utf-8').splitlines()]
        payloads = {r['suite']: r['payload'] for r in archive if r['attack'] == 'authority_spoof' and r['item_id'] == 0}
        for row in self.plan['controls']:
            if row['payload_domain']:
                payload = payloads[row['payload_domain']]
                self.assertIn(payload, row['data'])
                self.assertTrue(row['payload_present_after_preprocessing'])
                self.assertEqual(row['payload_sha256'], hashlib.sha256(payload.encode()).hexdigest())
            else:
                self.assertEqual(row['condition'], 'intentional_payload_exclusion')
                self.assertFalse(row['payload_present_after_preprocessing'])
                self.assertIsNone(row['payload_token_span'])

    def test_text_and_token_integrity(self):
        for row in self.plan['controls']:
            self.assertEqual(hashlib.sha256(row['data'].encode()).hexdigest(), row['data_sha256'])
            self.assertEqual(len(row['input_token_ids']), row['input_token_count'])
            self.assertLess(row['input_token_count'] + 10, 32768)
            self.assertEqual(row['input_token_ids'][0], 1)

    def test_raw_logit_hook_does_not_replace_or_mutate_output(self):
        import torch
        tensor = torch.arange(24, dtype=torch.float32).reshape(1, 2, 12)
        before = tensor.clone()
        output = SimpleNamespace(logits=tensor)
        observer = RawLogitObserver()
        result = observer(None, (), output)
        self.assertIsNone(result)
        self.assertTrue(torch.equal(tensor, before))
        self.assertEqual(observer.arrays[0].tolist(), list(map(float, range(12, 24))))
        observer.arrays[0][0] = -999
        self.assertTrue(torch.equal(tensor, before))


if __name__ == '__main__':
    unittest.main()
