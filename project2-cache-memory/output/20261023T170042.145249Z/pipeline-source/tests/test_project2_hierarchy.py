"""Synthetic fixtures test arithmetic/filtering only; never report evidence."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import project2_hierarchy as h
from report_common import write_csv,write_json,digest


class HierarchyTests(unittest.TestCase):
    def fixture(self):
        un=dict(counters_available=True,operations=10000,l1_hits=2000,l2_hits=3000,l3_hits=3000,
                dram_reads=2000,ns_per_access=20,elapsed_ns=10000,thread_cpu_ns=10000)
        sampled=dict(counters_available=True,cycles=20000,ref_cycles=10000,tsc_hz=1e9,
                     ns_per_access=20,elapsed_ns=10000,thread_cpu_ns=10000)
        levels={}
        for k,n,c in [('L1',2000,4),('L2',3000,10),('L3',3000,20),('DRAM',2000,100)]:
            levels[k]=dict(n=n,weight=n*101,weighted_cycles=c*n*101,minimum=c,maximum=c)
        return un,sampled,dict(levels=levels)

    def test_weighted_means_and_paired_difference(self):
        r=h.analyze_pair(*self.fixture())
        self.assertAlmostEqual(r['h_cycles'],12.25)
        self.assertAlmostEqual(r['h_ns'],6.125)
        self.assertAlmostEqual(r['p_ns'],43.875)
        self.assertAlmostEqual(r['amat_ns'],14.9)
        self.assertTrue(r['amat_supported'])

    def test_missing_dram_not_imputed(self):
        un,s,ss=self.fixture();ss['levels'].pop('DRAM');un['dram_reads']=0
        r=h.analyze_pair(un,s,ss)
        self.assertIsNotNone(r['h_ns']);self.assertIsNone(r['p_ns']);self.assertIsNone(r['amat_ns'])

    def test_missing_hits_not_imputed(self):
        un,s,ss=self.fixture()
        for k in ['L1','L2','L3']:ss['levels'].pop(k)
        r=h.analyze_pair(un,s,ss)
        self.assertIsNone(r['h_ns']);self.assertIsNone(r['amat_ns'])

    def test_sparse_values_retained_as_exploratory(self):
        un,s,ss=self.fixture();ss['levels']['DRAM']['n']=2
        r=h.analyze_pair(un,s,ss)
        self.assertIsNotNone(r['p_ns']);self.assertFalse(r['p_supported'])
        self.assertIn('fewer_than_1000',r['p_flags'])

    def test_unknown_and_fill_buffer_remain_separate(self):
        un,s,ss=self.fixture();ss['levels']['FB']=dict(n=1000,weight=101000,weighted_cycles=10100000)
        r=h.analyze_pair(un,s,ss)
        self.assertAlmostEqual(r['h_ns'],6.125)
        self.assertIn('fill_buffer',r['quality_flags'])

    def test_unavailable_frequency_not_nominal_substitution(self):
        un,s,ss=self.fixture();s['counters_available']=False
        r=h.analyze_pair(un,s,ss)
        self.assertIsNone(r['h_ns']);self.assertEqual(r['m'],.2)

    def test_counter_probability_not_clipped(self):
        un,s,ss=self.fixture();un['dram_reads']=11000
        r=h.analyze_pair(un,s,ss)
        self.assertEqual(r['m'],1.1);self.assertIsNone(r['amat_ns'])

    def test_validation_flags_do_not_raise(self):
        un,s,ss=self.fixture();s['ns_per_access']=100;ss['lost_records']=1
        r=h.analyze_pair(un,s,ss)
        self.assertIsNotNone(r['amat_ns']);self.assertFalse(r['amat_supported'])

    def test_parse_integer_nanosecond_time(self):
        line=' 123 123456.123456789: 101 1000 10268100142 |OP LOAD|LVL L1 hit|SNP None|TLB L1 or L2 hit|LCK No|BLK N/A 5 abcd'
        r=h.parse_sample(line)
        self.assertEqual(r['time_ns'],123456123456789)
        self.assertEqual(r['cycles'],5);self.assertEqual(r['ip'],0xabcd)
        self.assertEqual(r['level'],'L1')
        self.assertEqual(h.parse_sample(line.replace('L1 hit','LFB/MAB hit'))['level'],'FB')
        self.assertEqual(h.parse_sample(line.replace('L1 hit','Uncached hit'))['level'],'unknown')
        self.assertIsNone(h.parse_sample('LOST 99 events'))

    def test_filter_pid_pc_address_alignment_time(self):
        m=dict(pid=123,load_ip=0xabcd,data_start=4096,data_end=8192,start_ns=10,end_ns=20)
        s=dict(pid=123,ip=0xabcd,address=4096,time_ns=15,cycles=5,period=101)
        self.assertTrue(h.accept_sample(s,m))
        for field,value in [('pid',1),('ip',0),('address',8192),('address',4097),('time_ns',21),('time_ns',9),('cycles',0)]:
            changed=s.copy();changed[field]=value
            self.assertFalse(h.accept_sample(changed,m),(field,value))

    def test_summary_preserves_missing_and_counts(self):
        r=h.analyze_pair(*self.fixture());r['bytes']=4096
        second=r.copy();second['p_ns']=second['amat_ns']=None
        out=h.summarize([r,second])[0]
        self.assertEqual(out['p_ns_n'],1);self.assertEqual(out['measured_ns_n'],2)

    def test_empty_acquisition_is_representable(self):
        r=h.analyze_pair({},{},{})
        self.assertIsNone(r['amat_ns']);self.assertIsNone(r['m'])

if __name__=='__main__':unittest.main()
