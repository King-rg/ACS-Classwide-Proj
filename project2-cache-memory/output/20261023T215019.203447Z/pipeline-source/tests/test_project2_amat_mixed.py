"""Synthetic tests exercise arithmetic/admission; fixtures are never report evidence."""
import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import project2_amat_mixed as mixed

class MixedTests(unittest.TestCase):
    def rows(self):
        rows=[]
        for t in range(45):
            for c,m in zip(mixed.CONDITIONS,[.12,.25,.45,.65]):
                rows.append(dict(trial=t,preparation=c[0],eviction_bytes=c[1],operations=131072,
                    l3_misses=m*131072,l3_hits=(.94-m)*131072,l2_misses=.94*131072,
                    ns_per_access=15+100*m,passes=1,elapsed_ns=250e6,counters_available=True,
                    mixed_measurement_valid=True,invalid_mixed_passes=0,max_overhead_fraction=.002))
        return rows
    def test_strict_failure_does_not_mean_mixed_failure(self):
        r=self.rows()[0];r.update(check='fail',invalid_residency_passes=1)
        self.assertFalse(mixed.errors(r))
    def test_quality_checks_remain(self):
        for changes in [dict(counters_available='false'),dict(invalid_mixed_passes=1),dict(l2_misses=0),dict(max_overhead_fraction=.01),dict(passes=2)]:
            r=self.rows()[0];r.update(changes);self.assertTrue(mixed.errors(r))
    def test_recovers_known_coefficients_and_units(self):
        rows,stats=mixed.model_rows(self.rows(),[dict(bytes=8*2**20,random=1,operations=100,llc_read_misses=50,ns_per_access=65)],bootstrap=20)
        self.assertAlmostEqual(stats['h_ns'],15);self.assertAlmostEqual(stats['P_ns'],100)
        self.assertAlmostEqual(rows[0]['estimated_ns'],65)
        self.assertFalse(rows[0]['outside_condition_miss_range'])
    def test_small_miss_span_rejected(self):
        rr=self.rows()
        for r in rr:r['l3_misses']=.2*131072;r['l3_hits']=.74*131072
        with self.assertRaisesRegex(ValueError,'Miss-ratio span'):mixed.design_check(rr)
    def test_changing_private_cache_fraction_rejected(self):
        rr=self.rows()
        for r in rr:
            if mixed.condition(r)==mixed.CONDITIONS[0]:r['l3_hits']-=.04*131072
        with self.assertRaisesRegex(ValueError,'coverage changes'):mixed.design_check(rr)

if __name__=='__main__':unittest.main()
