"""Complete report campaigns and offline reproduction of the pinned report revisions."""
from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace
import datetime,json,os,shutil,subprocess,sys,tempfile
from report_common import digest,write_json,load_module
import project1,project2,project3
SHARED=Path(__file__).resolve().parent
ADAPTERS={1:project1,2:project2,3:project3}

def specification(project):
    return next(r for r in json.loads((SHARED/'report-coverage.json').read_text())['reports'] if r['project']==project)

@contextmanager
def environment(**values):
    old={k:os.environ.get(k) for k in values}
    os.environ.update({k:str(v) for k,v in values.items()})
    try:yield
    finally:
        for k,v in old.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v

def followup(root,name):
    sys.path.insert(0,str(root/'scripts'))
    return load_module(root/'scripts'/f'{name}_repeat.py','full_'+name)

def evidence_files(directory):
    excluded={'source','source_snapshot','postprocessing_snapshot','analysis-source','pipeline-source','plots','figures','plotted-values','tables','report'}
    return [p for p in directory.rglob('*') if p.is_file() and not excluded.intersection(p.relative_to(directory).parts) and
            (p.suffix in {'.csv','.json','.log','.gz','.data'} or p.name.endswith('.fio')) and p.name not in {'validation.json','run.json','progress.json'}]

def hashes(sources):
    return {key:{str(p.relative_to(base)):digest(p) for p in evidence_files(base)} for key,base in sources.items()}

def verify_hashes(sources,expected):
    for key,files in expected.items():
        if key not in sources:raise ValueError('Missing source study: '+key)
        for name,sha in files.items():
            p=sources[key]/name
            if not p.is_file() or digest(p)!=sha:raise ValueError(f'Source checksum mismatch: {key}/{name}')

def stage(sources,dest):
    """Isolated analysis copies: never update saved measurements or historical tables."""
    result={}
    def ignore(directory,names):
        return [n for n in names if n in {'source','analysis-source','pipeline-source','source_snapshot','postprocessing_snapshot','__pycache__','plots','figures','report','plotted-values','disposable.bin'} or Path(n).suffix in {'.png','.svg','.pdf','.data'}]
    for key,src in sources.items():
        if not src.is_dir():raise ValueError('Missing report source: '+str(src))
        target=dest/key;shutil.copytree(src,target,ignore=ignore);result[key]=target
    return result

def run_renderer(name,sources,dest,*args):
    env=os.environ.copy();env.update(REPORT_SOURCES=json.dumps({k:str(v) for k,v in sources.items()}),REPORT_DEST=str(dest),PYTHONPATH=str(SHARED)+os.pathsep+env.get('PYTHONPATH',''))
    subprocess.run([sys.executable,str(SHARED/'renderers/run.py'),str(SHARED/'renderers'/f'{name}.py'),*map(str,args)],env=env,check=True)

def validate_sources(root,project,sources):
    spec=specification(project)
    missing=set(spec['sources'])-set(sources)
    if missing:raise ValueError('Incomplete report campaign; missing studies: '+', '.join(sorted(missing)))
    if project==1:
        # The five-study adapter validates fresh campaigns; historical runs have individual layouts.
        for key in ['working-set','cycles']:
            for kernel in ['axpy','dot','multiply']:
                p=sources[key]/(kernel+('-cycles' if key=='cycles' else '')+'.csv')
                if not p.is_file():raise ValueError('Missing SIMD evidence: '+str(p))
    elif project==2:
        project2.validate(root,sources['base'])
        import project2_hierarchy
        project2_hierarchy.validate(sources['hierarchy'])
    else:
        project3.validate(root,sources['base'])
        for name in ['block','mix','range','burst']:
            kwargs={'first_trials':5} if name=='block' else {}
            followup(root,name).render(sources[name],plots=False,**kwargs)

def regenerate_alignment(path):
    import csv,collections,math,numpy as np
    groups=collections.defaultdict(list)
    for row in csv.DictReader((path/'raw.csv').open()):
        if row['correct']!='pass':raise ValueError('Alignment correctness failed')
        groups[row['kernel'],row['datatype'],int(row['base']),row['condition'],row['implementation']].append(float(row['elapsed_ns'])/int(row['n']))
    if any(len(v)!=15 for v in groups.values()):raise ValueError('Incomplete alignment trials')
    med={k:np.median(v) for k,v in groups.items()};rows=[]
    for typ in ['float','double']:
        for n in sorted({k[2] for k in groups}):
            for condition in ['clean','tail','shifted','combined']:
                ratios=[med[k,typ,n,condition,'scalar']/med[k,typ,n,condition,'auto'] for k in ['axpy','dot','multiply']]
                rows.append(dict(datatype=typ,base=n,condition=condition,speedup=math.exp(sum(map(math.log,ratios))/3)))
    from report_common import write_csv
    write_csv(path/'average_speedup.csv',rows)

def render_report(root,project,sources,out,expected):
    verify_hashes(sources,expected)
    work=stage(sources,out/'analysis-inputs');validate_sources(root,project,work)
    figures=out/'figures';figures.mkdir()
    if project==1:
        regenerate_alignment(work['alignment']);run_renderer('simd',work,figures)
        names={str(i):f'figure-{i}' for i in range(1,10)}
    elif project==2:
        project2.plot(root,work['base'])
        run_renderer('memory',work,figures);run_renderer('hierarchy',work,figures)
        names={f['id']:'fig'+f['id'] for f in specification(project)['figures']}
        for ext in ['png','svg']:(figures/f'fig6.{ext}').unlink(missing_ok=True)
    else:
        project3.plot(root,work['base']);run_renderer('ssd',work,figures)
        for name in ['block','mix','range','burst']:
            args=['--plot',str(work[name])]+(['--first-trials','5'] if name=='block' else [])
            env=os.environ.copy();env['PYTHONPATH']=str(root/'scripts')+os.pathsep+str(SHARED)
            subprocess.run([sys.executable,str(SHARED/'renderers/run.py'),str(root/'scripts'/f'{name}_repeat.py'),*args],env=env,check=True)
            for p in work[name].glob('fig*.*'):shutil.copy2(p,figures/p.name)
            shutil.copytree(work[name]/'plotted-values',figures/'plotted-values',dirs_exist_ok=True)
        names={'1':'fig1-baselines','2':'fig2-block-size','3':'fig3-read-write-mix','4a':'fig4b-little-law','4b':'fig4a-throughput-latency','5':'fig5-tail-latency','6':'fig6-file-range','7':'fig7-write-burst','8':'fig8-page-cache'}
    # Collect human-readable summary tables alongside the exact panel coordinates.
    tables=out/'tables';tables.mkdir()
    for study,path in work.items():
        target=tables/study;target.mkdir()
        for name in ['summary.csv','average_speedup.csv','paired-ratios.csv','averaged-time-series.csv','selected-trials.csv','little_law.csv']:
            if (path/name).is_file():shutil.copy2(path/name,target/name)
        if (path/'tables').is_dir():shutil.copytree(path/'tables',target,dirs_exist_ok=True)
    entries=[]
    for f in specification(project)['figures']:
        source=names[f['id']];stable='figure-'+f['id']
        for ext in ['png','svg']:
            p=figures/f'{source}.{ext}'
            if not p.is_file() or not p.stat().st_size:raise ValueError('Missing required figure: '+str(p))
            if p.stem!=stable:p.rename(figures/f'{stable}.{ext}')
        values=list((figures/'plotted-values').glob(source+'-panel-*.csv'))
        if not values:raise ValueError('Missing plotted values: '+source)
        f=dict(f)
        if project==3 and f['id']=='5':
            knee=json.loads((work['base']/'queue_analysis.json').read_text())['near_knee_qd']
            f['report_caption']=f['caption']
            f['caption']=f['caption'].replace('QD 8 and QD 32', 'QD 8 (both mid-range and near-knee)' if knee==8 else f'QD 8 and QD {knee}')
        entries.append(dict(f,files={ext:str((figures/f'{stable}.{ext}').relative_to(out)) for ext in ['png','svg']},plotted_values=[str(p.relative_to(out)) for p in values]))
    import numpy,matplotlib
    write_json(figures/'manifest.json',dict(figures=entries,environment=dict(python=sys.version,numpy=numpy.__version__,matplotlib=matplotlib.__version__)))
    verify_hashes(sources,expected)
    write_json(out/'coverage.json',dict(complete=True,figure_count=len(entries),report=specification(project),figures=entries,source_hashes=expected,sources={k:str(v) for k,v in sources.items()}))

def preflight(root,project,run):
    ADAPTERS[project].preflight(root)
    if project==2:
        if not shutil.which('perf'):raise ValueError('Full report requires perf load sampling')
        if 0 not in os.sched_getaffinity(0):raise ValueError('Report hierarchy protocol requires allowed CPU 0')
        import project2_hierarchy
        probe=project2_hierarchy.acquisition_pair(root,run/'preflight-hierarchy',16384,15,101,3)
        commands=json.loads((run/'preflight-hierarchy/commands.json').read_text())
        if any(c['returncode'] for c in commands):raise ValueError('Required hierarchy counters or perf sampling unavailable; see preflight-hierarchy logs')
        sample=json.loads((run/'preflight-hierarchy/sample-summary.json').read_text())
        if sample.get('decode_returncode',0):raise ValueError('Hierarchy sample decoding unavailable')
    if project==3 and shutil.disk_usage(root).free<=24*2**30:
        raise ValueError('Complete SSD report requires more than 24 GiB free for follow-ups')

def acquire(root,project,run):
    if project==1:
        project1.acquire(root,run);project1.validate(root,run)
        sources={key:run/'studies'/key for key in specification(1)['sources']}
    else:
        base=run/'studies/base';base.mkdir(parents=True)
        ADAPTERS[project].acquire(root,base);ADAPTERS[project].validate(root,base)
        sources={'base':base}
        if project==2:
            import project2_hierarchy
            path=run/'studies/hierarchy';path.mkdir()
            with environment(PROJECT2_HIERARCHY_TRIALS=30):
                project2_hierarchy.acquire(root,path,SimpleNamespace(modules=project2.modules,build_cases=project2.build_cases))
            project2_hierarchy.validate(path);sources['hierarchy']=path
        else:
            for name in ['block','mix','range','burst']:
                print('SSD follow-up: '+name,flush=True)
                sources[name]=followup(root,name).acquire(out=run/'studies'/name,plots=False,publish=False)
    write_json(run/'campaign.json',dict(project=project,sources={k:str(v.relative_to(run)) for k,v in sources.items()},source_hashes=hashes(sources)))
    return sources

def execute(root,project,action,requested=None):
    from report_pipeline import select_run,execute as legacy_execute
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    if project==2 and action in ['all','benchmark'] and os.environ.get('PROJECT2_SCOPE','full')!='full':
        return legacy_execute(root,project,action,requested)
    out=root/'output'/('reproduce-'+stamp if action=='reproduce' else 'plots-'+stamp if action=='plots' else stamp)
    out.mkdir(parents=True)
    state=dict(project=project,action=action,acquisition_complete=False,plots_complete=False)
    write_json(out/'run.json',state)
    try:
        if action=='reproduce':
            if requested:raise ValueError('RUN_DIR is for make plots; reproduce uses pinned report sources')
            spec=specification(project);sources={k:root/v for k,v in spec['sources'].items()};expected=spec['source_hashes']
        elif action=='plots':
            chosen=select_run(root,requested)
            if not (chosen/'campaign.json').exists() and project==1 and all((chosen/'studies'/k).is_dir() for k in project1.STUDIES):
                project1.validate(root,chosen)
                sources={k:chosen/'studies'/k for k in specification(1)['sources']}
                render_report(root,project,sources,out,hashes(sources))
                state.update(plots_complete=True,complete=True);write_json(out/'run.json',state);return out
            if not (chosen/'campaign.json').exists():
                if not requested:raise ValueError('LATEST is a legacy partial campaign. Use make reproduce for the full saved report, or RUN_DIR for an explicitly partial replay.')
                work=stage({'partial':chosen},out/'analysis-inputs')['partial']
                meta=json.loads((work/'metadata.json').read_text())
                standalone=next((name for key,name in [('blocks_kib','block'),('writes_pct','mix'),('ranges_mib','range'),('idle_s','burst')] if key in meta),None) if project==3 else None
                if standalone:
                    options={'first_trials':5} if standalone=='block' else {}
                    followup(root,standalone).render(work,**options)
                else:
                    ADAPTERS[project].validate(root,work);ADAPTERS[project].plot(root,work)
                write_json(out/'coverage.json',dict(complete=False,partial=True,source=str(chosen)))
                state.update(plots_complete=True,partial=True);write_json(out/'run.json',state);return out
            campaign=json.loads((chosen/'campaign.json').read_text());sources={k:chosen/v for k,v in campaign['sources'].items()};expected=campaign['source_hashes']
        else:
            if requested:raise ValueError('RUN_DIR selects saved data for make plots only')
            preflight(root,project,out)
            shutil.copytree(SHARED,out/'pipeline-source',ignore=shutil.ignore_patterns('__pycache__'))
            sources=acquire(root,project,out)
            expected=json.loads((out/'campaign.json').read_text())['source_hashes']
            state['acquisition_complete']=True;write_json(out/'run.json',state)
            temporary=root/'output/LATEST.tmp';temporary.write_text(out.name+'\n');temporary.replace(root/'output/LATEST')
        if action!='benchmark':
            render_report(root,project,sources,out,expected);state['plots_complete']=True
        state['complete']=True;write_json(out/'run.json',state);return out
    except BaseException as error:
        state['error']=str(error);write_json(out/'run.json',state);raise
