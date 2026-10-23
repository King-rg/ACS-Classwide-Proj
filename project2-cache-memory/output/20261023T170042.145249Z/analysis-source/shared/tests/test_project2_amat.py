"""Admission and analysis tests: no fabricated data is published as evidence."""
import sys,unittest,tempfile,json,os,subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import project2_amat as amat
from report_common import write_csv,write_json,digest

class PreparedTests(unittest.TestCase):
    def good(self):
        n=131072
        return dict(check='pass',preparation='l3-resident',operations=n,passes=1,
            l3_hits=n,l3_misses=0,l2_misses=n,counters_available=True,
            invalid_residency_passes=0,max_overhead_fraction=.001,elapsed_ns=250000000,
            ns_per_access=20,trial=0)
    def test_counter_and_residency_failures(self):
        self.assertEqual(amat.controlled_errors(self.good()),[])
        for changes in [dict(counters_available=False),dict(l3_hits=100),
                        dict(l3_misses=131072),dict(invalid_residency_passes=1),
                        dict(max_overhead_fraction=.01),dict(passes=2),dict(l2_misses=0)]:
            r=self.good();r.update(changes)
            self.assertTrue(amat.controlled_errors(r),changes)
    def test_flushed_requires_misses(self):
        r=self.good();r.update(preparation='cache-flushed',l3_hits=0,l3_misses=131072)
        self.assertFalse(amat.controlled_errors(r))
        r['l3_misses']=100;self.assertTrue(amat.controlled_errors(r))
    def test_penalty_is_median_of_paired_differences(self):
        c=[]
        for i,(h,d) in enumerate([(10,100),(20,21),(30,50)]):
            c.extend([dict(trial=i,preparation='l3-resident',ns_per_access=h),dict(trial=i,preparation='cache-flushed',ns_per_access=d)])
        w=[dict(bytes=8388608,random=1,ns_per_access=t,llc_read_misses=50,operations=100) for t in [29,30,31]]
        rows,s=amat.model_rows(c,w)
        self.assertEqual(s['hit_ns'],20)
        self.assertEqual(s['paired_penalty_ns'],20) # difference of medians would be 30
        self.assertEqual(rows[0]['estimated_ns'],30)
    def test_csv_false_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);r=self.good();r['counters_available']=False
            write_csv(p/'controlled.csv',[r]);write_json(p/'metadata.json',dict(controlled_sha256=digest(p/'controlled.csv')))
            with self.assertRaises(ValueError):amat.validate(p)
    def test_missing_trials_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);write_csv(p/'controlled.csv',[self.good()]);write_json(p/'metadata.json',dict(controlled_sha256=digest(p/'controlled.csv')))
            with self.assertRaisesRegex(ValueError,'Missing controlled trials'):amat.validate(p)

if __name__=='__main__':unittest.main()
