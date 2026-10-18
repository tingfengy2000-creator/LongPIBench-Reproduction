"""Synthetic arithmetic fixtures are unit tests only, never experiment input."""
import unittest
import offline


class OfflineAuditTest(unittest.TestCase):
    def clean(self):
        return [dict(sample_id=f'{d}-{i:03d}-clean',domain=d,split='calibration',label=0,
            n_chunks=(1 if d=='resume' else 5),maximum=(i+1)/100,token_count=100+i)
            for d in ['email','resume'] for i in range(40)]

    def test_fit_ignores_calibration_attacks_and_all_holdout(self):
        clean=self.clean()
        poison=[dict(clean[0],sample_id='attack',label=1,maximum=100.),
            dict(clean[1],sample_id='holdout',split='test',maximum=200.)]
        self.assertEqual(offline.fit(clean)[1],offline.fit(clean+poison)[1])

    def test_domain_neighborhood_and_leave_one_out(self):
        clean=self.clean();row=clean[0]
        refs=offline.neighborhood(row,clean,'domain_length_max',True)
        self.assertEqual(len(refs),28)
        self.assertTrue(all(r['domain']=='email' for r in refs))
        self.assertNotIn(row['sample_id'],[r['sample_id'] for r in refs])

    def test_exact_tie_threshold_does_not_exceed_budget(self):
        vals=[.9]*5+[.1]*35
        cut=offline.threshold(vals)
        self.assertEqual(sum(v>cut for v in vals),0)

    def test_tied_and_perfect_auc_ap(self):
        labels=[0,0,1,1]
        tied=offline.curves(labels,[.5]*4)
        self.assertAlmostEqual(tied['auroc'],.5)
        self.assertAlmostEqual(tied['average_precision'],.5)
        perfect=offline.curves(labels,[0.,0.,1.,1.])
        self.assertEqual(perfect['auroc'],1.)
        self.assertEqual(perfect['average_precision'],1.)
        for values in [[.5]*4,[0.,0.,1.,1.]]:
            offline.independently_check_curves(labels,values,offline.curves(labels,values))

    def test_domain_cutoff_cannot_change_within_domain_ranking(self):
        rows=self.clean();clean,fitted=offline.fit(rows)
        labels=[i%2 for i in range(40)]
        original=[offline.score(r,'global_max',clean) for r in rows[:40]]
        domain=[offline.score(r,'domain_max',clean) for r in rows[:40]]
        self.assertEqual(offline.curves(labels,original),offline.curves(labels,domain))


if __name__=='__main__':unittest.main()
