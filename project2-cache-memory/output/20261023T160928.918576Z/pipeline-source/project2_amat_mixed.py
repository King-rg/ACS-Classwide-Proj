"""Mixed-residency effective AMAT estimates; never labels preparation as isolation."""
from pathlib import Path
import json, os, random, shutil, subprocess
import numpy as np
from report_common import digest, write_json, write_csv, read_csv
from project2_amat import controlled_args

CONDITIONS=[('l3-resident',n*2**20) for n in (2,4,8)]+[('cache-flushed',0)]
METHOD='mixed-residency-v1'

def truth(v):return str(v).lower()=='true'
def condition(r):return (r['preparation'],int(r['eviction_bytes']))
def errors(r):
    e=[]
    if not truth(r.get('counters_available')):e.append('unavailable/multiplexed counters')
    if not truth(r.get('mixed_measurement_valid')):e.append('invalid mixed-condition envelope')
    if int(r.get('invalid_mixed_passes',1)):e.append('per-pass event reconciliation failed')
    n=float(r.get('operations',0))
    if not n:return e+['no completed reads']
    h,m,l2=[float(r[k])/n for k in ('l3_hits','l3_misses','l2_misses')]
    if not .90<=h+m<=1.05 or not .90<=l2<=1.05 or abs(h+m-l2)>.01:e.append('event accounting failed')
    if float(r['max_overhead_fraction'])>=.01:e.append('overhead >=1%')
    if n!=int(r['passes'])*131072:e.append('incomplete traversal')
    if float(r['elapsed_ns'])<250e6:e.append('short trial')
    if not np.isfinite(float(r['ns_per_access'])) or float(r['ns_per_access'])<=0:e.append('invalid time')
    return e

def design_check(rows):
    groups=[[r for r in rows if condition(r)==c] for c in CONDITIONS]
    if any(not g for g in groups):raise ValueError('Missing preparation condition')
    ms=[np.median([float(r['l3_misses'])/float(r['operations']) for r in g]) for g in groups]
    coverage=[np.median([(float(r['l3_hits'])+float(r['l3_misses']))/float(r['operations']) for r in g]) for g in groups]
    # Declared before acquisition: require a useful miss-ratio range and stable
    # private-cache contribution. These are design checks, not confidence levels.
    if np.ptp(ms)<.30:raise ValueError('Miss-ratio span below 0.30; weak parameter identification')
    if np.ptp(coverage)>.03:raise ValueError('L3 event coverage changes by over 3 percentage points')
    return dict(condition_miss_ratios=list(map(float,ms)),condition_L3_event_coverage=list(map(float,coverage)))

def acquire(root,output,adapter):
    acq,_=adapter.modules(root);cpu=acq.select_cpus()[0]
    cases=[c for c in adapter.build_cases([cpu]) if c['study']=='working_set']
    meta=acq.collect_metadata('amat-focused',45,250,[cpu],os.environ.get('CC','cc'),os.environ.get('CFLAGS','-O3 -march=native -std=c11 -Wall -Wextra -Wpedantic'),cases)
    meta.update(scope='amat-focused',amat_method=METHOD,rounds=3,trials_per_round=15,benchmark_sha256=digest(root/'build/memory_bench'),historical_report_run='20261022T203612.685890Z',protocol='Four mixed-residency conditions, fixed 8 MiB chain, 45 matched trial blocks. Three separate pilot blocks. Fresh processes; randomized condition order; >=250 ms timed traversal, preparation excluded. Full 32-size sequential/random working-set sweep in same focused campaign.',acceptance=dict(min_L3_event_coverage=.90,max_L3_event_coverage=1.05,max_event_reconciliation_error=.01,max_overhead_fraction=.01,min_condition_miss_span=.30,max_condition_coverage_span=.03),parameter_interpretation='Regression effective intercept and slope; neither is an isolated hardware timing.')
    acq.snapshot_sources(output);shutil.copy2(root/'build.mk',output/'source/build.mk')
    (output/'disassembly.txt').write_text(subprocess.check_output(['objdump','-d',str(root/'build/memory_bench')],text=True))
    (output/'event-catalog.txt').write_text(subprocess.run(['perf','list','--details','mem_load_retired*'],capture_output=True,text=True).stdout)
    write_json(output/'metadata.json',meta)
    rng=random.Random(4320);controlled=[];warm=[];pilots=[]
    def call(c,phase,t):
        args=controlled_args(root,cpu,*c);p=subprocess.run(args,capture_output=True,text=True)
        try:r=json.loads(p.stdout)
        except json.JSONDecodeError:r={}
        with (output/'controlled-attempts.jsonl').open('a') as f:f.write(json.dumps(dict(phase=phase,trial=t,command=args,returncode=p.returncode,stderr=p.stderr,result=r))+'\n')
        meta['commands'].append(args)
        # Exit 4 denotes failure of the unchanged strict-isolation protocol.
        # Admission here is explicitly separate, and raw strict failures remain.
        e=errors(r)
        if p.returncode not in (0,4):e.append(f'benchmark exit {p.returncode}')
        if e:raise ValueError(f'{phase} {c} trial {t}: {e}')
        return dict(trial=t,round=t//15+1,**r)
    try:
        for t in range(3):
            order=list(CONDITIONS);rng.shuffle(order)
            for c in order:pilots.append(call(c,'pilot',t))
            write_csv(output/'mixed-pilots.csv',pilots)
            print(f'Mixed AMAT pilot block {t+1}/3 passed measurement checks',flush=True)
        meta['pilot_design']=design_check(pilots);write_json(output/'metadata.json',meta)
        for t in range(45):
            order=list(CONDITIONS);rng.shuffle(order)
            for c in order:
                controlled.append(call(c,'measurement',t));write_csv(output/'controlled.csv',controlled)
            pairs=[cases[i:i+2] for i in range(0,len(cases),2)];rng.shuffle(pairs)
            for pair in pairs:
                for c in pair[::(-1 if t%2 else 1)]:
                    args=adapter.arguments(root,c,[cpu],250);p=subprocess.run(args,capture_output=True,text=True)
                    with (output/'working-set-attempts.jsonl').open('a') as f:f.write(json.dumps(dict(command=args,stdout=p.stdout,stderr=p.stderr,returncode=p.returncode))+'\n')
                    p.check_returncode();r=dict(c,trial=t,round=t//15+1,trial_in_round=t%15,**json.loads(p.stdout))
                    adapter.require_evidence(r);warm.append(r);write_csv(output/'raw.csv',warm);meta['commands'].append(args)
            print(f'Mixed AMAT acquisition: round {t//15+1}, block {t%15+1}/15',flush=True)
        meta['final_design']=design_check(controlled)
    finally:
        for name in ('raw','controlled'):meta[name+'_sha256']=digest(output/(name+'.csv')) if (output/(name+'.csv')).exists() else None
        meta['attempt_sha256']={p.name:digest(p) for p in output.glob('*attempts.jsonl')}
        write_json(output/'metadata.json',meta)

def validate(run):
    meta=json.loads((run/'metadata.json').read_text());rows=read_csv(run/'controlled.csv');seen=set()
    for name in ('raw','controlled'):
        if digest(run/(name+'.csv'))!=meta[name+'_sha256']:raise ValueError('Changed '+name)
    for r in rows:
        e=errors(r)
        if e:raise ValueError(str(e))
        key=(int(r['trial']),condition(r))
        if key in seen:raise ValueError('Duplicate controlled trial')
        seen.add(key)
    if seen!={(t,c) for t in range(45) for c in CONDITIONS}:raise ValueError('Incomplete controlled campaign')
    design_check(rows)

def fit(rows):
    x=np.array([float(r['l3_misses'])/float(r['operations']) for r in rows]);y=np.array([float(r['ns_per_access']) for r in rows])
    if np.ptp(x)<.05:raise ValueError('Insufficient miss-ratio variation')
    return np.linalg.lstsq(np.column_stack([np.ones(len(x)),x]),y,rcond=None)[0]

def model_rows(controlled,working,bootstrap=5000):
    design=design_check(controlled);h,p=fit(controlled)
    if h<=0 or p<=0:raise ValueError('Nonpositive effective AMAT parameters')
    trials=sorted({int(r['trial']) for r in controlled});blocks={t:[r for r in controlled if int(r['trial'])==t] for t in trials}
    rng=np.random.default_rng(4320);samples=[]
    # Resample matched four-condition blocks within each acquisition round.
    rounds=[trials[i:i+15] for i in range(0,len(trials),15)]
    for _ in range(bootstrap):
        ids=np.concatenate([rng.choice(g,len(g),replace=True) for g in rounds])
        samples.append(fit([r for t in ids for r in blocks[int(t)]]))
    b=np.array(samples);ci=np.quantile(b,[.025,.975],axis=0)
    if np.any(ci[0]<=0):raise ValueError('Parameter uncertainty includes nonpositive costs')
    summaries=[]
    for c in CONDITIONS:
        rr=[r for r in controlled if condition(r)==c]
        summaries.append(dict(preparation=c[0],eviction_MiB=c[1]/2**20,median_miss_ratio=float(np.median([float(r['l3_misses'])/float(r['operations']) for r in rr])),median_ns=float(np.median([float(r['ns_per_access']) for r in rr])),L3_event_coverage=float(np.median([(float(r['l3_hits'])+float(r['l3_misses']))/float(r['operations']) for r in rr]))))
    sensitivity=[dict(omitted=str(c),h_ns=float(v[0]),P_ns=float(v[1])) for c in CONDITIONS for v in [fit([r for r in controlled if condition(r)!=c])]]
    rows=[];support=(min(d['median_miss_ratio'] for d in summaries),max(d['median_miss_ratio'] for d in summaries))
    for size in sorted({int(r['bytes']) for r in working if int(r['random'])==1 and int(r['bytes'])>=8*2**20}):
        rr=[r for r in working if int(r['random'])==1 and int(r['bytes'])==size];y=np.array([float(r['ns_per_access']) for r in rr]);m=float(np.median([float(r['llc_read_misses'])/float(r['operations']) for r in rr]));lo,hi=np.quantile(b[:,0]+m*b[:,1],[.025,.975])
        rows.append(dict(buffer_MiB=size/2**20,measured_ns=float(np.median(y)),measured_q25_ns=float(np.quantile(y,.25)),measured_q75_ns=float(np.quantile(y,.75)),L3_misses_per_read=m,estimated_ns=float(h+m*p),parameter_ci_low=float(lo),parameter_ci_high=float(hi),outside_condition_miss_range=not support[0]<=m<=support[1]))
    stats=dict(method=METHOD,h_ns=float(h),P_ns=float(p),h_ci95_ns=ci[:,0].tolist(),P_ci95_ns=ci[:,1].tolist(),conditions=summaries,leave_one_condition_out=sensitivity,design=design,model='estimated AMAT = h + m P',parameter_definition='Effective regression intercept and additional cost per L3 miss; not pure hardware timings.',uncertainty='95% percentile bootstrap of matched trial blocks, stratified by round; parameter sampling uncertainty only. Excludes miss-ratio uncertainty, model bias, and extrapolation error.',condition_median_miss_range=support,controlled_trials=len(controlled),working_set_trials=len(working))
    return rows,stats

def plot(run):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows,stats=model_rows(read_csv(run/'controlled.csv'),read_csv(run/'raw.csv'))
    (run/'tables').mkdir(exist_ok=True);(run/'plots').mkdir(exist_ok=True)
    write_csv(run/'tables/amat_mixed.csv',rows);write_json(run/'amat-parameters.json',stats)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.labelsize':9,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'legend.frameon':False,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(6.5,3.2),layout='constrained');x=[r['buffer_MiB'] for r in rows]
    ax.fill_between(x,[r['measured_q25_ns'] for r in rows],[r['measured_q75_ns'] for r in rows],color='#24649a',alpha=.14,label='Measured trial IQR')
    ax.plot(x,[r['measured_ns'] for r in rows],'o-',color='#24649a',lw=1.4,ms=3,label='Measured median')
    ax.fill_between(x,[r['parameter_ci_low'] for r in rows],[r['parameter_ci_high'] for r in rows],color='#bb6c16',alpha=.2,label='Parameter-only 95% interval')
    ax.plot(x,[r['estimated_ns'] for r in rows],'s--',color='#bb6c16',lw=1.4,ms=3,label='Estimated AMAT')
    ax.set(xlabel='Buffer size (MiB)',ylabel='Average time per read (ns)',ylim=(0,None));ax.set_xscale('log',base=2);ax.set_xticks([8,16,24,32,64,128,192],[8,16,24,32,64,128,192]);ax.grid(axis='y',color='#dfe3e8',lw=.6);ax.axvline(24,color='#777',ls='--',lw=.7);ax.legend(loc='lower right')
    for ext in ('png','svg','pdf'):fig.savefig(run/f'plots/amat_mixed.{ext}',dpi=240)
    write_json(run/'amat-manifest.json',dict(scope='amat-focused',method=METHOD,parameters=stats,sources={n:digest(run/n) for n in ['controlled.csv','raw.csv']},table='tables/amat_mixed.csv',plot='plots/amat_mixed.png'))
