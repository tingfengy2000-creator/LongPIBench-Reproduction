import json
import unittest

from receive_gemini_followup import available_records, identify


class TruncatedResponseTests(unittest.TestCase):
    def test_truncated_final_row_is_not_a_label(self):
        valid = {'review_id': 'a', 'ai_label': 1}
        tail = '{"review_id":"b","text_sha256":"'+'a'*64+'","ai_label":0,"role":"quotation","'
        rows, incomplete = available_records((json.dumps(valid)+'\n'+tail).encode())
        self.assertEqual(rows, [valid])
        self.assertFalse(incomplete['accepted_as_review'])
        self.assertEqual(incomplete['review_id'], 'b')
        self.assertEqual(incomplete['raw_line'], tail)

    def test_invalid_middle_row_cannot_be_skipped(self):
        raw = b'{"review_id":"truncated\n{"review_id":"later"}'
        with self.assertRaises(json.JSONDecodeError):
            available_records(raw)

    def test_other_final_json_errors_cannot_be_repaired(self):
        with self.assertRaises(json.JSONDecodeError):
            available_records(b'{"review_id": invalid}')

    def test_foreign_batch_ids_cannot_be_accepted(self):
        with self.assertRaises(AssertionError):
            identify(b'{"review_id":"foreign","text_sha256":"unknown"}')


if __name__ == '__main__':
    unittest.main()
