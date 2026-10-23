"""Check dense sampling configuration and measured-point provenance rules."""
import unittest
import run_evidence
import plot_dense

class DenseChartTests(unittest.TestCase):
    def test_grid_and_boundaries(self):
        sizes=run_evidence.DENSE_FOOTPRINT_KIB
        self.assertEqual(len(sizes),34)
        self.assertEqual(sizes,sorted(set(sizes)))
        self.assertEqual((sizes[0],sizes[-1]),(12,98304))
        for boundary in [48,1280,24576]:
            self.assertIn(boundary,sizes)
            self.assertTrue(any(.90*boundary<=x<boundary for x in sizes))
            self.assertTrue(any(boundary<x<=1.10*boundary for x in sizes))

    def test_dense_cases_are_separate_full_remeasurement(self):
        cases=run_evidence.cases('dense')
        self.assertEqual(len(cases),204)
        for kernel in ['axpy','dot','multiply']:
            for dtype in ['float','double']:
                selected=[c for c in cases if c[0]==kernel and c[1]==dtype]
                self.assertEqual(len(selected),34)
                self.assertTrue(all(c[2]=='working_set' and c[4:]==(1,0) and c[3]%8==0 for c in selected))
        self.assertEqual(len(run_evidence.cases('full')),162)

    def test_missing_points_not_synthesized(self):
        with self.assertRaisesRegex(ValueError,'Missing/duplicate'):
            plot_dense.checked_points([],[],[],dict(sweep='dense',repeats=3,target_footprints_kib=[12,48]))

if __name__=='__main__':unittest.main()
