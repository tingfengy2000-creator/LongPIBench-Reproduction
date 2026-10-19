"""Integrity tests only: no real scores, weights or research results are created."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.export_r3_evidence import (audit_target, checked_raw, inserted_coverage,
                                       trace_features)
from repro.scoring import evaluate_response


class FakeTokenizer:
    """Deterministic character codec, for saved-record validation tests only."""
    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        text = json.dumps(messages) + ('assistant:' if add_generation_prompt else '')
        return list(map(ord, text)) if tokenize else text

    def decode(self, ids, *, skip_special_tokens):
        return ''.join(chr(i) for i in ids if i != 0)


class ExportIntegrityTests(unittest.TestCase):
    def test_insertion_interval_union(self):
        exact = 'EXACT_ORDERED_NONWHITESPACE_COVERAGE'
        self.assertEqual(inserted_coverage([10, 20], [[[5, 15], [13, 18]], [[18, 22]]], exact), 1)
        self.assertEqual(inserted_coverage([10, 20], [[[12, 15], [13, 16]]], exact), .4)
        self.assertEqual(inserted_coverage([10, 20], [], exact), 0)
        self.assertIsNone(inserted_coverage([10, 20], [], 'UNKNOWN'))
        self.assertIsNone(inserted_coverage(None, [], exact))
        with self.assertRaises(ValueError):
            inserted_coverage([10, 20], [[[16, 12]]], exact)

    def test_raw_hash_and_run_boundary(self):
        # Keep temporary artifacts on E:, following the workspace storage rule.
        (ROOT / 'runs').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / 'runs') as temp:
            root = Path(temp)
            run = root / 'runs' / 'source'
            run.mkdir(parents=True)
            path = run / 'test.json'
            path.write_bytes(b'{"test": true}')
            row = {'case_id': 'test', 'path': str(path), 'bytes': path.stat().st_size,
                   'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            self.assertEqual(checked_raw(root, {'raw_dir': str(run)}, row), {'test': True})
            bad = dict(row, sha256='0' * 64)
            with self.assertRaises(ValueError):
                checked_raw(root, {'raw_dir': str(run)}, bad)
            outside = root / 'test.json'
            outside.write_bytes(path.read_bytes())
            with self.assertRaises(ValueError):
                checked_raw(root, {'raw_dir': str(run)}, dict(row, path=str(outside)))

    def target_fixture(self):
        tokenizer = FakeTokenizer()
        benchmark = SimpleNamespace(parse_json_response=json.loads,
                                    score_response=lambda suite, goal, parsed: False)
        case = {'suite': 'email', 'goal': '0', 'system_prompt': 'Summarize the email.'}
        data = 'A benign email.'
        settings = {'chat_template_sha256': 'test-template', 'max_new_tokens': 200,
                    'pad_token_id': 0, 'eos_token_ids': [0]}
        messages = [{'role': 'system', 'content': case['system_prompt']}, {'role': 'user', 'content': data}]
        response = json.dumps({'summary': 'A meeting.', 'response': 'Acknowledged.'})
        ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
        generated = list(map(ord, response)) + [0]
        target = {'messages': messages, 'rendered_prompt': tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True),
                  'input_token_ids': ids, 'input_token_count': len(ids), 'chat_template_sha256': 'test-template',
                  'generation_attempted': True, 'generation_overrides': {'max_new_tokens': 200, 'do_sample': False, 'pad_token_id': 0},
                  'generated_token_ids': generated, 'output_token_count': len(generated),
                  'raw_response': response, 'stop_reason': 'EOS'}
        evaluation = evaluate_response('email', '0', response, parse=json.loads, score=benchmark.score_response)
        return {'target': target, 'evaluation': evaluation, 'validity': 'VALID'}, case, data, {'target': settings}, tokenizer, benchmark

    def test_valid_target_and_message_tampering(self):
        args = self.target_fixture()
        self.assertEqual(audit_target(*args), args[0]['evaluation'])
        bad = copy.deepcopy(args[0])
        bad['target']['messages'][1]['content'] = 'Changed user input'
        with self.assertRaises(ValueError):
            audit_target(bad, *args[1:])

    def test_decode_and_sampling_tampering(self):
        args = self.target_fixture()
        for key, value in [('raw_response', 'different'), ('generation_overrides', {'do_sample': True})]:
            bad = copy.deepcopy(args[0])
            bad['target'][key] = value
            with self.assertRaises(ValueError):
                audit_target(bad, *args[1:])

    def test_nonfinite_trace_preserves_evidence(self):
        trace = {'call_count': 2, 'nonfinite_helper': True, 'logged_errors': [], 'events': [
            {'function': 'compute_conditional_probability', 'finite': False,
             'condition_text': 'x' * 3000, 'target_text': 'tail', 'condition_exceeds_cropped_length': True,
             'average_log_probability': {'nonfinite': 'nan'}}]}
        summary = trace_features(trace)
        self.assertEqual(summary['condition_exceeds_crop_calls'], 1)
        self.assertEqual(summary['nonfinite_probability_calls'], 1)
        example = summary['first_nonfinite_probability_examples'][0]
        self.assertTrue(example['condition_text']['truncated'])
        self.assertEqual(example['condition_text']['full_chars'], 3000)
        self.assertEqual(example['average_log_probability'], {'nonfinite': 'nan'})
        self.assertEqual(len(trace['events'][0]['condition_text']), 3000)


if __name__ == '__main__':
    unittest.main()
