"""Focused controlled-access acquisition, invoked by the existing Project 2 adapter."""
from pathlib import Path
import csv,json,os,random,subprocess,shutil
import numpy as np
from report_common import digest,write_json,write_csv,read_csv

SCOPE='amat-focused'

def controlled_args(root,cpu,preparation,eviction,target=250):
    args=[str(root/'build/memory_bench'),'latency',str(8*2**20),'64','8','100','1','0','1',str(target),str(cpu),preparation]
    if preparation=='l3-resident':args.append(str(eviction))
    return args

def controlled_errors(r):
    errors=[]
    if not r.get('counters_available'):errors.append('counter access unavailable or multiplexed')
    if r.get('check')!='pass':errors.append('benchmark validation failed')
    if not r.get('operations',0):return errors+['missing completed reads']
    n=float(r['operations']);hit=float(r['l3_hits'])/n;miss=float(r['l3_misses'])/n
    if r['preparation']=='l3-resident' and (hit<.95 or miss>.05):errors.append('L3 hit residency below 95%')
    if r['preparation']=='cache-flushed' and miss<.95:errors.append('L3 miss residency below 95%')
    if not .95<=hit+miss<=1.05:errors.append('L3 event total differs from reads by over 5%')
    if not .95<=float(r['l2_misses'])/n<=1.05:errors.append('L2 miss total differs from reads by over 5%')
    if int(r['invalid_residency_passes']):errors.append('one or more passes failed residency')
    if float(r['max_overhead_fraction'])>=.01:errors.append('measurement overhead reaches 1%')
    if int(r['operations'])!=int(r['passes'])*(8*2**20//64):errors.append('incomplete traversal')
    return errors

def acquire(root,output,adapter):
    acquisition,_=adapter.modules(root);cpus=acquisition.select_cpus();cpu=cpus[0]
    meta=acquisition.collect_metadata(SCOPE,45,250,[cpu],os.environ.get('CC','cc'),os.environ.get('CFLAGS','-O3 -march=native -std=c11 -Wall -Wextra -Wpedantic'),[])
    meta.update(scope=SCOPE,rounds=3,trials_per_round=15,benchmark_sha256=digest(root/'build/memory_bench'),protocol='Prepared single traversals; >=250 ms summed traversal envelopes per trial; preparation excluded. Three rounds of fifteen paired trials. Working-set pairs use original warm protocol.',historical_report_run='20261022T203612.685890Z',pilot_results=[])
    acquisition.snapshot_sources(output)
    shutil.copy2(root/'build.mk',output/'source/build.mk')
    (output/'disassembly.txt').write_text(subprocess.check_output(['objdump','-d',str(root/'build/memory_bench')],text=True))
    (output/'event-catalog.txt').write_text(subprocess.run(['perf','list','--details','mem_load_retired*'],capture_output=True,text=True).stdout)
    def call(prep,eviction,phase,trial):
        args=controlled_args(root,cpu,prep,eviction)
        p=subprocess.run(args,capture_output=True,text=True)
        try:r=json.loads(p.stdout)
        except json.JSONDecodeError:r={'check':'fail','reason':'invalid or absent JSON'}
        record=dict(phase=phase,trial=trial,preparation=prep,eviction_bytes=eviction,command=args,returncode=p.returncode,stderr=p.stderr,result=r)
        with (output/'controlled-attempts.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
        meta['commands'].append(args)
        return r,p.returncode
    try:
        selected=None
        # Validate every candidate with three pilots. Never select by latency.
        for eviction in [2*2**20,4*2**20,8*2**20]:
            results=[]
            for trial in range(3):
                r,rc=call('l3-resident',eviction,'pilot',trial)
                errors=controlled_errors(r)
                results.append(dict(trial=trial,errors=errors,returncode=rc,result=r))
                print(f'AMAT pilot: eviction={eviction//2**20} MiB trial={trial+1}: {errors or "pass"}',flush=True)
                if r.get('reason')=='counter_open':
                    meta['pilot_results'].append(dict(eviction_bytes=eviction,results=results))
                    raise ValueError('Prepared PMU counters unavailable; see controlled-attempts.jsonl. No permissions changed.')
            meta['pilot_results'].append(dict(eviction_bytes=eviction,results=results))
            if selected is None and all(not r['errors'] and not r['returncode'] for r in results):selected=eviction
        flushed=[]
        for trial in range(3):
            r,rc=call('cache-flushed',0,'pilot',trial)
            flushed.append(dict(trial=trial,errors=controlled_errors(r),returncode=rc,result=r))
        meta['flush_pilots']=flushed
        meta['selected_eviction_bytes']=selected
        if selected is None:raise ValueError('L3 isolation failed: none of the 2, 4, or 8 MiB eviction buffers passed all residency/overhead checks. No experimental AMAT parameters published.')
        if any(r['errors'] or r['returncode'] for r in flushed):raise ValueError('Cache-flushed pilot failed residency or timing validation.')
        cases=[c for c in adapter.build_cases([cpu]) if c['study']=='working_set']
        meta['cases']=cases
        controlled=[];warm=[];rng=random.Random(4320)
        for trial in range(45):
            for prep,eviction in ([('l3-resident',selected),('cache-flushed',0)][::(-1 if trial%2 else 1)]):
                r,rc=call(prep,eviction,'measurement',trial)
                row=dict(trial=trial,round=trial//15+1,**r);controlled.append(row)
                write_csv(output/'controlled.csv',controlled)
                if rc or controlled_errors(r):raise ValueError(f'Controlled trial {trial} failed: {controlled_errors(r)}')
            groups=[cases[i:i+2] for i in range(0,len(cases),2)];rng.shuffle(groups)
            for pair in groups:
                for c in pair[::(-1 if trial%2 else 1)]:
                    args=adapter.arguments(root,c,[cpu],250)
                    p=subprocess.run(args,capture_output=True,text=True)
                    with (output/'working-set-attempts.jsonl').open('a') as f:f.write(json.dumps(dict(command=args,stdout=p.stdout,stderr=p.stderr,returncode=p.returncode))+'\n')
                    p.check_returncode();row=dict(c,trial=trial,round=trial//15+1,trial_in_round=trial%15,**json.loads(p.stdout))
                    warm.append(row);write_csv(output/'raw.csv',warm)
                    meta['commands'].append(args);adapter.require_evidence(row)
            print(f'AMAT focused acquisition: round {trial//15+1}, trial {trial%15+1}/15',flush=True)
    finally:
        meta['raw_sha256']=digest(output/'raw.csv') if (output/'raw.csv').exists() else None
        meta['controlled_sha256']=digest(output/'controlled.csv') if (output/'controlled.csv').exists() else None
        meta['attempt_sha256']={p.name:digest(p) for p in output.glob('*attempts.jsonl')}
        write_json(output/'metadata.json',meta)

def validate(run):
    meta=json.loads((run/'metadata.json').read_text())
    if not meta.get('controlled_sha256') or digest(run/'controlled.csv')!=meta['controlled_sha256']:raise ValueError('Missing or changed controlled data')
    rows=read_csv(run/'controlled.csv');seen=set()
    for row in rows:
        # CSV boolean conversion must not treat the string "false" as true.
        row['counters_available']=str(row['counters_available']).lower()=='true'
        errors=controlled_errors(row)
        if errors:raise ValueError(str(errors))
        key=(int(row['trial']),row['preparation'])
        if key in seen:raise ValueError('Duplicate controlled trial')
        seen.add(key)
        if float(row['elapsed_ns'])<250e6:raise ValueError('Short prepared trial')
    if seen!={(t,p) for t in range(45) for p in ['l3-resident','cache-flushed']}:raise ValueError('Missing controlled trials')

def model_rows(controlled,working):
    pairs={}
    for r in controlled:pairs.setdefault(int(r['trial']),{})[r['preparation']]=float(r['ns_per_access'])
    h=np.array([pairs[t]['l3-resident'] for t in sorted(pairs)])
    penalty=np.array([pairs[t]['cache-flushed']-pairs[t]['l3-resident'] for t in sorted(pairs)])
    if np.any(penalty<=0):raise ValueError('Nonpositive paired miss penalty')
    H=float(np.median(h));P=float(np.median(penalty))
    # Bootstrap parameter uncertainty only. Keep measured trial IQR separate.
    rng=np.random.default_rng(4320);indices=rng.integers(0,len(h),(5000,len(h)))
    hb=np.median(h[indices],axis=1);pb=np.median(penalty[indices],axis=1)
    rows=[]
    sizes=sorted({int(r['bytes']) for r in working if int(r['random'])==1 and int(r['bytes'])>=8*2**20})
    for size in sizes:
        rr=[r for r in working if int(r['random'])==1 and int(r['bytes'])==size]
        y=np.array([float(r['ns_per_access']) for r in rr]);m=float(np.median([float(r['llc_read_misses'])/float(r['operations']) for r in rr]))
        predicted=H+m*P;lo,hi=np.quantile(hb+m*pb,[.025,.975])
        rows.append(dict(buffer_MiB=size/2**20,measured_ns=float(np.median(y)),measured_q25_ns=float(np.quantile(y,.25)),measured_q75_ns=float(np.quantile(y,.75)),L3_misses_per_read=m,estimated_ns=predicted,parameter_ci_low=float(lo),parameter_ci_high=float(hi),estimate_minus_measured_ns=predicted-float(np.median(y))))
    stats=dict(hit_ns=H,hit_iqr_ns=np.quantile(h,[.25,.75]).tolist(),paired_penalty_ns=P,paired_penalty_iqr_ns=np.quantile(penalty,[.25,.75]).tolist(),model='h + m * P',uncertainty='95% paired bootstrap interval for parameter estimation only; miss-ratio uncertainty and model error excluded',MAE_ns=float(np.mean([abs(r['estimate_minus_measured_ns']) for r in rows])))
    return rows,stats

def plot(run):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows,stats=model_rows(read_csv(run/'controlled.csv'),read_csv(run/'raw.csv'))
    (run/'tables').mkdir(exist_ok=True);(run/'plots').mkdir(exist_ok=True)
    write_csv(run/'tables/amat_experimental.csv',rows);write_json(run/'amat-parameters.json',stats)
    x=[r['buffer_MiB'] for r in rows]
    fig,(ax,err)=plt.subplots(2,1,figsize=(8,6),sharex=True,gridspec_kw={'height_ratios':[3,1]})
    ax.plot(x,[r['measured_ns'] for r in rows],'o-',color='#24649a',label='Measured median')
    ax.fill_between(x,[r['measured_q25_ns'] for r in rows],[r['measured_q75_ns'] for r in rows],color='#24649a',alpha=.15,label='Measured trial IQR')
    ax.plot(x,[r['estimated_ns'] for r in rows],'s--',color='#bb6c16',label='AMAT from measured parameters')
    ax.fill_between(x,[r['parameter_ci_low'] for r in rows],[r['parameter_ci_high'] for r in rows],color='#bb6c16',alpha=.2,label='Parameter-only 95% interval')
    ax.set_ylabel('Average time per read (ns)');ax.legend(fontsize=8)
    err.plot(x,[r['estimate_minus_measured_ns'] for r in rows],'o-',color='#6b517f');err.axhline(0,color='#555',lw=1)
    err.set_ylabel('Estimate −\nmeasured (ns)');err.set_xlabel('Buffer size (MiB)')
    for a in (ax,err):
        a.set_xscale('log',base=2);a.grid(axis='y',alpha=.2);a.axvline(24,color='#888',ls=':',lw=1)
    err.set_xticks([8,16,24,32,64,128,192],[8,16,24,32,64,128,192])
    fig.tight_layout()
    for ext in ('png','svg','pdf'):fig.savefig(run/f'plots/amat_experimental.{ext}',dpi=220)
    write_json(run/'amat-manifest.json',dict(scope=SCOPE,parameters=stats,sources={n:digest(run/n) for n in ['controlled.csv','raw.csv']},table='tables/amat_experimental.csv',plot='plots/amat_experimental.png'))
