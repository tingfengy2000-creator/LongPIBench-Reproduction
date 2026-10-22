import unittest
from import_gemini_batch import normalize_evidence


class EvidenceNormalizationTests(unittest.TestCase):
    def test_unique_json_escaping_artifact_only(self):
        rows=[{'review_id':'a','ai_label':0,'reason':'keep reason','evidence':'Quoted \\"test\\".'}]
        cases={'a':{'untrusted_document':'Record: Quoted "test". It was rejected.'}}
        normalized,changes=normalize_evidence(rows,cases)
        self.assertEqual(normalized[0]['evidence'],'Quoted "test".')
        self.assertEqual(rows[0]['evidence'],'Quoted \\"test\\".')
        self.assertEqual(normalized[0]['ai_label'],0)
        self.assertEqual(len(changes),1)
    def test_already_literal_untouched(self):
        rows=[{'review_id':'a','evidence':'literal'}]
        self.assertEqual(normalize_evidence(rows,{'a':{'untrusted_document':'A literal record'}}),(rows,[]))
    def test_fabricated_quote_rejected(self):
        with self.assertRaises(ValueError):normalize_evidence([{'review_id':'a','evidence':'not there'}],{'a':{'untrusted_document':'actual'}})
    def test_ambiguous_normalization_not_guessed(self):
        with self.assertRaises(ValueError):normalize_evidence([{'review_id':'a','evidence':'\\"x\\"'}],{'a':{'untrusted_document':'"x" and "x"'}})


if __name__=='__main__':unittest.main()
