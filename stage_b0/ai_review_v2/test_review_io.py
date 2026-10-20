import copy
import importlib.util
import unittest
from pathlib import Path
from review_io import validate_records
from label_gate import second_review_required,require_exploratory_label_freeze


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.cases={'item1':{'text_sha256':'x','untrusted_document':'A past report quoted an override command.'}}
        self.row={'review_id':'item1','text_sha256':'x','ai_label':0,'role':'quotation',
                  'evidence':'A past report quoted','reason':'明确归属过去报告的引用，并非面向当前任务的新指令。','ambiguity':False,'confidence':'high'}
    def test_valid_quotation(self):self.assertEqual(validate_records([self.row],self.cases)['n'],1)
    def test_fabricated_evidence_rejected(self):
        bad=copy.deepcopy(self.row);bad['evidence']='not in the document'
        with self.assertRaises(AssertionError):validate_records([bad],self.cases)
    def test_missing_and_duplicate_rejected(self):
        with self.assertRaises(AssertionError):validate_records([],self.cases)
        with self.assertRaises(AssertionError):validate_records([self.row,self.row],self.cases)
    def test_uncertain_requires_explicit_null(self):
        row=copy.deepcopy(self.row);row.update(ai_label=None,role='uncertain',ambiguity=True)
        self.assertEqual(validate_records([row],self.cases)['n_uncertain'],1)
    def test_model_disagreement_requires_second(self):
        mapping=[{'review_id':'item1','sample_id':'s1','fixed_second_review_required':False}]
        needed=second_review_required([{'sample_id':'s1','label':1}],[self.row],mapping)
        self.assertEqual(needed,{'item1'})
    def test_authorization_is_not_finished_review(self):
        with self.assertRaisesRegex(RuntimeError,'not complete'):
            require_exploratory_label_freeze(Path(__file__).parents[1],Path(__file__).parent/'no_review_yet.json')


if __name__=='__main__':unittest.main()
