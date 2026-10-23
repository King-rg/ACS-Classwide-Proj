"""Regression tests for scientific calculations and the public workflow."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import project1
import project2
import project3
import report_pipeline as pipeline
from report_common import point, samples, write_json

WORKSPACE=Path(__file__).resolve().parents[2]


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def adapter(self, fail=None):
        events=[]
        adapter=Mock()
        adapter.preflight.side_effect=lambda root:events.append('build/check')
        def acquire(root,run):
            events.append(('acquire',run))
            (run/'raw.csv').write_text('trial,value\n0,12\n')
            if fail:raise ValueError(fail)
        adapter.acquire.side_effect=acquire
        adapter.validate.side_effect=lambda root,run:events.append(('validate',run))
        adapter.plot.side_effect=lambda root,run:events.append(('plot',run))
        return adapter,events

    def test_all_is_ordered_and_passes_same_run(self):
        adapter,events=self.adapter()
        with patch.object(pipeline,'load_module',return_value=adapter):
            run=pipeline.execute(self.root,1,'all')
        self.assertEqual(events,['build/check',('acquire',run),('validate',run),('plot',run)])
        state=json.loads((run/'run.json').read_text())
        self.assertTrue(state['acquisition_complete'] and state['plots_complete'])
        self.assertEqual((self.root/'output/LATEST').read_text().strip(),run.name)

    def test_benchmark_then_plots_does_not_reacquire(self):
        adapter,events=self.adapter()
        with patch.object(pipeline,'load_module',return_value=adapter):
            run=pipeline.execute(self.root,2,'benchmark')
            self.assertFalse(adapter.plot.called)
            pipeline.execute(self.root,2,'plots')
        self.assertEqual(adapter.acquire.call_count,1)
        self.assertEqual(adapter.plot.call_args.args[1],run)

    def test_hierarchy_keeps_full_report_latest(self):
        (self.root/'output').mkdir()
        (self.root/'output/LATEST').write_text('historical-report\n')
        adapter,events=self.adapter()
        original=adapter.acquire.side_effect
        def acquire(root,run):
            original(root,run)
            write_json(run/'metadata.json',{'scope':'amat-hierarchy'})
        adapter.acquire.side_effect=acquire
        with patch.object(pipeline,'load_module',return_value=adapter):
            run=pipeline.execute(self.root,2,'all')
            pipeline.execute(self.root,2,'plots',str(run))
        self.assertEqual((self.root/'output/LATEST').read_text(),'historical-report\n')
        self.assertEqual((self.root/'output/LATEST_HIERARCHY').read_text().strip(),run.name)
        self.assertEqual(adapter.acquire.call_count,1)

    def test_failure_preserves_previous_latest_without_plotting(self):
        (self.root/'output').mkdir()
        (self.root/'output/LATEST').write_text('previous\n')
        adapter,events=self.adapter('Missing counters')
        with patch.object(pipeline,'load_module',return_value=adapter):
            with self.assertRaisesRegex(ValueError,'Missing counters'):
                pipeline.execute(self.root,1,'all')
        self.assertFalse(adapter.plot.called)
        self.assertEqual((self.root/'output/LATEST').read_text(),'previous\n')
        state=next((self.root/'output').glob('*/run.json'))
        self.assertFalse(json.loads(state.read_text())['acquisition_complete'])
        self.assertTrue((state.parent/'raw.csv').exists())

    def test_plot_failure_is_retryable_without_remeasurement(self):
        adapter,_=self.adapter()
        adapter.plot.side_effect=ValueError('renderer failed')
        with patch.object(pipeline,'load_module',return_value=adapter):
            with self.assertRaisesRegex(ValueError,'renderer failed'):
                pipeline.execute(self.root,3,'all')
            run=pipeline.select_run(self.root,None)
            self.assertTrue(json.loads((run/'run.json').read_text())['acquisition_complete'])
            adapter.plot.side_effect=None
            pipeline.execute(self.root,3,'plots',str(run))
        self.assertEqual(adapter.acquire.call_count,1)

    def test_tampered_data_and_incomplete_run_rejected(self):
        adapter,_=self.adapter()
        with patch.object(pipeline,'load_module',return_value=adapter):
            run=pipeline.execute(self.root,1,'benchmark')
            (run/'raw.csv').write_text('changed')
            with self.assertRaisesRegex(ValueError,'checksum'):
                pipeline.execute(self.root,1,'plots')
        write_json(run/'run.json',{'acquisition_complete':False})
        with self.assertRaisesRegex(ValueError,'incomplete'):
            pipeline.select_run(self.root,str(run))

    def test_missing_dependency_does_not_acquire(self):
        adapter,_=self.adapter()
        adapter.preflight.side_effect=ValueError('Missing dependency')
        with patch.object(pipeline,'load_module',return_value=adapter):
            with self.assertRaises(ValueError):pipeline.execute(self.root,2,'all')
        self.assertFalse(adapter.acquire.called)

    def test_make_public_targets_and_parallel_dispatch(self):
        for project in ['project1-simd','project2-cache-memory','project3-ssd']:
            root=WORKSPACE/project
            text=(root/'Makefile').read_text()
            self.assertIn('.PHONY: all benchmark plots',text)
            for target in ['', 'all','benchmark','plots','reproduce']:
                args=['make','-n','-j4']+([target] if target else [])
                result=subprocess.run(args,cwd=root,capture_output=True,text=True,check=True)
                self.assertEqual(result.stdout.count('report_pipeline.py'),1)
                self.assertIn(' '+(target or 'all')+' --project',result.stdout)
            for removed in ['run','quick','full','check','clean']:
                self.assertNotEqual(subprocess.run(['make','-n',removed],cwd=root,capture_output=True).returncode,0)


class ScientificTests(unittest.TestCase):
    def test_trial_completeness_and_paired_statistics(self):
        with self.assertRaises(ValueError):samples([{'trial':0,'ns':1},{'trial':0,'ns':2}],'ns',2)
        with self.assertRaises(ValueError):samples([{'trial':0,'ns':float('nan')}],'ns',1)
        result=point('paired',1,[1,2,3,10])
        self.assertEqual((result['y'],result['y_q25'],result['y_q75']),(2.5,1.75,4.75))

    def test_counter_and_page_evidence(self):
        row=dict(study='tlb',check='pass',elapsed_ns=1,counters_available=True,
                 huge=1,huge_bytes=4096,bytes=4096,threads=1,
                 cycles=20,llc_read_misses=0,dtlb_read_misses=0)
        project2.require_evidence(row)
        with self.assertRaisesRegex(ValueError,'counter'):
            project2.require_evidence(dict(row,counters_available=False))
        with self.assertRaisesRegex(ValueError,'huge-page'):
            project2.require_evidence(dict(row,huge_bytes=0))
        with self.assertRaisesRegex(ValueError,'counter'):
            project2.require_evidence(dict(row,cycles=float('nan')))

    def test_dense_matrix_and_required_baselines(self):
        cases=project2.build_cases([0,2,4,6,8,10])
        self.assertEqual(len(cases),249)
        self.assertEqual(len({tuple(r.values()) for r in cases}),len(cases))
        self.assertEqual({r['read_pct'] for r in cases if r['study']=='mix'},set(range(0,101,10)))
        self.assertTrue({16384,524288,8388608,201326592}.issubset({r['bytes'] for r in cases if r['study']=='working_set'}))

    def test_near_knee_is_first_depth_not_first_input(self):
        rows=[dict(qd=32,iops=100),dict(qd=8,iops=91),dict(qd=1,iops=30),dict(qd=16,iops=95)]
        self.assertEqual(project3.near_knee(rows)['qd'],8)
        self.assertEqual(len(project3.expected_cases()),35)
        self.assertEqual(len(project3.expected_cases(False)),33)

    def test_fio_log_units_and_partial_window(self):
        data=[[1000,500000,1,0,0],[2000,400000,1,0,0],[2001,300000,1,0,0]]
        points=project3.state_points(data,1/1000)
        self.assertEqual([p['y'] for p in points],[500,400,300])
        self.assertEqual(points[-1]['window_ms'],1)
        self.assertIn('Partial',points[-1]['annotation'])
        self.assertEqual(project3.state_points([[1000,2048]],1/1024)[0]['y'],2)

    def test_saved_fio_arithmetic_and_corruption(self):
        root=WORKSPACE/'project3-ssd'
        source=root/'output/20261021T235058Z'
        if not source.exists():self.skipTest('Historical fixture unavailable')
        project3.validate(root,source)
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            run=Path(temp)
            for p in source.iterdir():
                if p.suffix in ['.csv','.json','.log']:shutil.copy2(p,run/p.name)
            (run/'raw').symlink_to(source/'raw',target_is_directory=True)
            import csv
            from report_common import read_csv,write_csv
            rows=read_csv(run/'raw.csv');rows[0]['lat_us']='99999999'
            write_csv(run/'raw.csv',rows)
            with self.assertRaisesRegex(ValueError,'arithmetic|checksum'):project3.validate(root,run)


class SSDSafetyTests(unittest.TestCase):
    def test_fiona_command_is_not_accepted_as_fio(self):
        with patch.dict(os.environ,{'FIO':'wrong-fio'}), \
             patch('subprocess.check_output',return_value='fio, version 1.9.6'):
            with self.assertRaisesRegex(ValueError,'FIO storage benchmark unavailable'):
                project3.fio_environment(WORKSPACE/'project3-ssd')

    def exercise(self, error, existing=False, allocation_failure=False):
        import runpy
        import signal
        script=WORKSPACE/'project3-ssd/scripts/run.py'
        with tempfile.TemporaryDirectory() as temp:
            run=Path(temp)
            target=run/'disposable.bin'
            if existing:target.write_bytes(b'pre-existing data')
            handler=signal.getsignal(signal.SIGTERM)
            try:
                with patch.dict(os.environ,{'REPORT_RUN_DIR':str(run),'REPORT_FIO':'fake-fio'}), \
                     patch.object(sys,'argv',[str(script),'--profile','quick']), \
                     patch('subprocess.check_output',return_value='fio-3.33'), \
                     patch('subprocess.run',side_effect=error), \
                     patch('shutil.disk_usage',return_value=Mock(free=10*2**30)), \
                     patch('os.posix_fallocate',side_effect=OSError('Disk full') if allocation_failure else None):
                    with self.assertRaises((OSError,subprocess.CalledProcessError,KeyboardInterrupt)):
                        runpy.run_path(str(script),run_name='__main__')
            finally:
                signal.signal(signal.SIGTERM,handler)
            if existing:self.assertEqual(target.read_bytes(),b'pre-existing data')
            else:self.assertFalse(target.exists())

    def test_fio_failure_removes_owned_file(self):
        self.exercise(subprocess.CalledProcessError(1,['fake-fio']))
    def test_interrupt_removes_owned_file(self):
        self.exercise(KeyboardInterrupt())
    def test_allocation_failure_removes_owned_file(self):
        self.exercise(ValueError('unused'),allocation_failure=True)
    def test_existing_file_is_not_removed(self):
        self.exercise(ValueError('unused'),existing=True)


if __name__=='__main__':unittest.main()
