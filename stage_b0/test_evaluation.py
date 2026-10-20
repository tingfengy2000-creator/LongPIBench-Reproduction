import math
import tempfile
import unittest
from pathlib import Path
from evaluation import threshold_for_fpr,cascade_threshold,auroc,average_precision,require_human_signoff,native_windows


class TinyTokenizer:
    def __call__(self,text,**kwargs):return {'input_ids':list(range(10,10+len(text)))}
    def num_special_tokens_to_add(self,pair=False):return 2
    def prepare_for_model(self,ids,**kwargs):return {'input_ids':[1]+ids+[2],'attention_mask':[1]*(len(ids)+2),'special_tokens_mask':[1]+[0]*len(ids)+[1]}


class EvaluationTests(unittest.TestCase):
    def test_all_token_coverage_last_partial_chunk(self):
        ids,chunks=native_windows(TinyTokenizer(),'x'*1023)
        self.assertEqual([(c['start_token'],c['end_token']) for c in chunks],[(0,510),(510,1020),(1020,1023)])
        self.assertEqual(sum(len(c['source_token_ids']) for c in chunks),len(ids))
    def test_tied_negative_threshold_does_not_exceed_budget(self):
        values=[.1,.2,.3,.4,.5,.6,.7,.8,.9,.9]
        t=threshold_for_fpr(values,.1)
        self.assertEqual(sum(v>=t for v in values),0)
        self.assertGreater(t,.9)
    def test_adjacent_float_boundary(self):
        x=.5;y=math.nextafter(x,math.inf)
        t=threshold_for_fpr([x,y]+[0.]*18,.05)
        self.assertEqual(t,y);self.assertEqual(sum(v>=t for v in [x,y]+[0.]*18),1)
    def test_cascade_gate_high_recall(self):
        values=[i/100 for i in range(100)]
        t=cascade_threshold(values,.95)
        self.assertEqual(sum(x>=t for x in values),95)
    def test_metric_ties_and_perfect_ranking(self):
        perfect=[{'label':0,'score':.1},{'label':1,'score':.9}]
        self.assertEqual(auroc(perfect),1);self.assertEqual(average_precision(perfect),1)
        tied=[{'label':0,'score':.5},{'label':1,'score':.5}]
        self.assertEqual(auroc(tied),.5);self.assertEqual(average_precision(tied),.5)
    def test_unsiged_candidate_set_is_blocked(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent.parent/'runs') as d:
            with self.assertRaisesRegex(RuntimeError,'not been signed'):require_human_signoff(d)


if __name__=='__main__':unittest.main()
