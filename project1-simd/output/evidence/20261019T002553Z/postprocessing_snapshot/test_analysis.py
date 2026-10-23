import copy
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('analysis',Path(__file__).with_name('analyze_evidence.py'))
analysis=importlib.util.module_from_spec(spec);spec.loader.exec_module(analysis)

class EvidenceAnalysisTests(unittest.TestCase):
    def rows(self):
        result=[]
        for impl,scale in [('scalar',1),('auto',.5),('simd',.25)]:
            for trial in range(5):
                r={k:'0' for k in analysis.KEYS};r.update(run_id='test',repeat='0',study='working_set',kernel='axpy',datatype='float',implementation=impl,n='10',stride='1',footprint_bytes='80',coefficient='1.25',warmups='2',calls='4',seed='4320')
                r.update(trial=str(trial),elapsed_ns=str((trial+1)*40*scale),core_cycles=str((trial+1)*80*scale),tsc_ticks=str((trial+1)*120*scale),user_instructions='400',llc_misses='2',max_abs_error='0',khz_start='3000000',khz_end='3000000')
                result.append(r)
        return result
    def test_batch_normalization_and_cycles(self):
        summary=analysis.summaries(self.rows());scalar=summary[0]
        self.assertEqual(scalar['median_ns'],30)
        self.assertEqual(scalar['median_core_cycles_per_element'],6)
        self.assertAlmostEqual(scalar['gflops'],20/30)
        ratios=analysis.compare(summary)
        self.assertEqual([r['speedup'] for r in ratios],[2,4])
    def test_variants_must_share_calls(self):
        summary=analysis.summaries(self.rows());summary[1]['calls']='8'
        with self.assertRaisesRegex(ValueError,'exact'):analysis.compare(summary)
    def test_alignment_and_stride_not_pooled(self):
        summary=analysis.summaries(self.rows());summary[1]['offset_elements']='1'
        with self.assertRaisesRegex(ValueError,'exact'):analysis.compare(summary)
    def test_process_repeats_remain_separate(self):
        rows=analysis.summaries(self.rows());other=copy.deepcopy(rows)
        for r in other:r['repeat']='1';r['calls']='8';r['median_ns']*=2
        results=analysis.collapse_repeats(rows+other,'median_ns',analysis.CONFIG+['implementation'])
        self.assertEqual(len(results),3)
        self.assertEqual(results[0]['repeat_count'],2)
        self.assertEqual((results[0]['median'],results[0]['low'],results[0]['high']),(45,30,60))
    def test_missing_raw_trial_rejected(self):
        with self.assertRaisesRegex(ValueError,'five'):analysis.summaries(self.rows()[1:])
if __name__=='__main__':unittest.main()
