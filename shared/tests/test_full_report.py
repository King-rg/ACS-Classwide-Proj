"""Coverage contract, source integrity, and full-campaign orchestration tests."""
from pathlib import Path
import json,os,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import full_report as full
from report_common import write_json

class FullReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def sources(self):
        path=self.root/'saved';path.mkdir();(path/'raw.csv').write_text('trial,value\n0,1\n');return {'base':path}
    def test_all_29_figures_have_captions_renderers_and_sources(self):
        expected=[['1','2','3','4','5','6','7','8','9'],['1','2a','2b','3','4a','4b','5','6a','6b','7','8'],['1','2','3','4a','4b','5','6','7','8']]
        for project,ids in enumerate(expected,1):
            spec=full.specification(project)
            self.assertEqual([f['id'] for f in spec['figures']],ids)
            self.assertTrue(spec['revision'])
            for f in spec['figures']:
                self.assertTrue(f['caption'] and f['renderer'])
                self.assertTrue(set(f['datasets'])<=set(spec['sources']))
    def test_corrupt_or_missing_evidence_is_rejected(self):
        sources=self.sources();expected=full.hashes(sources)
        full.verify_hashes(sources,expected)
        (sources['base']/'raw.csv').write_text('corrupt')
        with self.assertRaisesRegex(ValueError,'checksum'):full.verify_hashes(sources,expected)
        (sources['base']/'raw.csv').unlink()
        with self.assertRaisesRegex(ValueError,'checksum'):full.verify_hashes(sources,expected)
    def test_analysis_copy_does_not_write_back(self):
        sources=self.sources();before=full.hashes(sources);copy=full.stage(sources,self.root/'work')
        (copy['base']/'raw.csv').write_text('changed')
        full.verify_hashes(sources,before)
    def test_missing_followup_is_not_replaced_by_historical_data(self):
        with self.assertRaisesRegex(ValueError,'missing studies'):
            full.validate_sources(self.root,3,{'base':self.root})
    def test_failed_full_acquisition_does_not_publish_latest(self):
        (self.root/'output').mkdir();(self.root/'output/LATEST').write_text('prior\n')
        with patch.object(full,'preflight'),patch.object(full,'acquire',side_effect=ValueError('follow-up failed')):
            with self.assertRaisesRegex(ValueError,'follow-up'):full.execute(self.root,3,'all')
        self.assertEqual((self.root/'output/LATEST').read_text(),'prior\n')
    def test_unsupported_preflight_never_starts_acquisition(self):
        with patch.object(full,'preflight',side_effect=ValueError('unsupported hardware')),patch.object(full,'acquire') as acquire:
            with self.assertRaisesRegex(ValueError,'unsupported'):full.execute(self.root,2,'all')
            acquire.assert_not_called()
    def test_reproduce_never_acquires(self):
        sources=self.sources();spec={'sources':{'base':'saved'},'source_hashes':full.hashes(sources)}
        with patch.object(full,'specification',return_value=spec),patch.object(full,'render_report') as render,patch.object(full,'acquire') as acquire,patch.object(full,'preflight') as preflight:
            full.execute(self.root,3,'reproduce');render.assert_called_once();acquire.assert_not_called();preflight.assert_not_called()
    def test_plots_uses_campaign_sources_without_acquisition(self):
        source=self.root/'output/prior';source.mkdir(parents=True)
        write_json(source/'run.json',{'acquisition_complete':True})
        write_json(source/'campaign.json',{'sources':{'base':'studies/base'},'source_hashes':{}})
        with patch.object(full,'render_report') as render,patch.object(full,'acquire') as acquire:
            full.execute(self.root,3,'plots',str(source))
            self.assertEqual(render.call_args.args[2],{'base':source/'studies/base'});acquire.assert_not_called()
    def test_plot_failure_keeps_acquisition_retryable(self):
        def acquire(root,project,out):
            (out/'studies').mkdir();write_json(out/'campaign.json',{'sources':{},'source_hashes':{}});return {}
        with patch.object(full,'preflight'),patch.object(full,'acquire',side_effect=acquire),patch.object(full,'render_report',side_effect=ValueError('renderer')):
            with self.assertRaisesRegex(ValueError,'renderer'):full.execute(self.root,1,'all')
        latest=(self.root/'output/LATEST').read_text().strip()
        state=json.loads((self.root/'output'/latest/'run.json').read_text())
        self.assertTrue(state['acquisition_complete']);self.assertFalse(state['plots_complete'])
    def test_full_preflight_checks_large_huge_page_spans(self):
        from types import SimpleNamespace
        seen=[]
        def probe(args,**kwargs):
            size=int(args[2]);seen.append(size)
            return json.dumps(dict(check='pass',elapsed_ns=1,counters_available=True,cycles=1,llc_read_misses=0,dtlb_read_misses=0,huge_bytes=0 if size==96*2**20 else size))
        with patch.object(full.project2,'preflight'),patch.object(full.project2,'modules',return_value=(SimpleNamespace(select_cpus=lambda:[0]),None)),patch.object(full.subprocess,'check_output',side_effect=probe):
            with self.assertRaisesRegex(ValueError,'huge-page'):
                full.preflight(self.root,2,self.root)
        self.assertIn(96*2**20,seen)
        self.assertEqual(json.loads((self.root/'preflight-memory.json').read_text())[-1]['huge_bytes'],0)
    def test_parent_lock_blocks_another_public_command(self):
        import fcntl,subprocess
        folder=self.root/'output';folder.mkdir()
        with (folder/'.pipeline.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            result=subprocess.run([sys.executable,str(full.SHARED/'report_pipeline.py'),'reproduce','--project','1','--root',str(self.root)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Another report command',result.stderr)
        self.assertEqual(list(folder.iterdir()),[folder/'.pipeline.lock'])
    def test_legacy_latest_cannot_claim_complete_report(self):
        run=self.root/'output/old';run.mkdir(parents=True)
        (self.root/'output/LATEST').write_text('old')
        with self.assertRaisesRegex(ValueError,'legacy partial'):
            full.execute(self.root,2,'plots')
    def test_empty_coverage_is_not_success(self):
        sources=self.sources()
        with patch.object(full,'specification',return_value={'sources':{'base':'saved'},'figures':[{'id':'1'}]}),patch.object(full,'validate_sources'),patch.object(full.project2,'plot'),patch.object(full,'run_renderer'):
            with self.assertRaisesRegex(ValueError,'Missing required figure'):
                full.render_report(self.root,2,sources,self.root/'rendered',full.hashes(sources))
    def test_benchmark_does_not_render(self):
        def acquire(root,project,out):
            write_json(out/'campaign.json',{'sources':{},'source_hashes':{}});return {}
        with patch.object(full,'preflight'),patch.object(full,'acquire',side_effect=acquire),patch.object(full,'render_report') as render:
            full.execute(self.root,1,'benchmark');render.assert_not_called()

if __name__=='__main__':unittest.main()
