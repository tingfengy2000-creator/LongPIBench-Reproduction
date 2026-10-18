"""Hand-calculated statistical controls; no toy values go to pilot_results."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import score_pilot as supplied
from analyze_scores import basic, metrics, value, wilson


class StatisticsTest(unittest.TestCase):
    def test_aggregators_against_hand_calculation_and_numpy(self):
        row={'chunk_scores':[.1,.2,.9]}
        self.assertEqual(supplied.basic_score(row,'max'),.9)
        self.assertAlmostEqual(supplied.basic_score(row,'top2'),.55)
        self.assertAlmostEqual(supplied.basic_score(row,'q90'),.76)
        for method in ['max','top2','q90']:
            self.assertAlmostEqual(supplied.basic_score(row,method),basic(row,method))

    def test_threshold_ties_and_more_conservative_nextafter_are_explicit(self):
        values=[.1,.4,.4,.8,.9]
        t=supplied.threshold_at_empirical_fpr(values,.2)
        self.assertEqual(t,math.nextafter(.8,math.inf))
        self.assertEqual(sum(v>t for v in values),1)
        # The scaffold says most permissive, but using nextafter AND > is
        # one ULP more conservative than the exact >.8 order-statistic cut.
        self.assertFalse(math.nextafter(.8,math.inf)>t)

    def test_small_length_calibration_is_global_and_has_discrete_resolution(self):
        clean=[{'sample_id':str(i),'chunk_count':i+1,'n_chunks':i+1,'chunk_scores':[i/10]} for i in range(3)]
        row={'sample_id':'new','chunk_count':50,'n_chunks':50,'chunk_scores':[.9]}
        self.assertAlmostEqual(supplied.conditional_pvalue(row,clean),.25)
        self.assertAlmostEqual(supplied.score(row,'length_calibrated_max',clean),value(row,'length_calibrated_max',clean))

    def test_confusion_counts_and_zero_fp_interval_are_not_a_population_guarantee(self):
        result=metrics([1,1,0,0],[True,False,True,False])
        self.assertEqual(result,{'tp':1,'fp':1,'tn':1,'fn':1,'tpr':.5,'fpr':.5})
        self.assertGreater(wilson(0,8)[1],.3)


if __name__=='__main__': unittest.main()
