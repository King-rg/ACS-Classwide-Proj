"""Project 2: one fresh dense report campaign and standalone figures."""
from pathlib import Path
import collections
import json
import os
import random
import shutil
import subprocess
import sys
import numpy as np
from report_common import (Figures, command, digest, load_module, point,
                           read_csv, write_csv, write_json)


def modules(root):
    acquisition = load_module(root/'scripts/run.py', 'memory_acquisition')
    analysis = load_module(root/'scripts/analysis.py', 'memory_analysis')
    return acquisition, analysis


def build_cases(cpus):
    cases = []
    def add(study, mode='latency', span=96*2**20, spacing=64, block=8,
            read=100, order=1, huge=0, streams=1, threads=1):
        cases.append(dict(study=study, mode=mode, bytes=span, spacing=spacing,
                          block=block, read_pct=read, random=order, huge=huge,
                          streams=streams, threads=threads))
    sizes = [4,8,16,24,32,40,48,56,64,96,128,256,512,768,1024,1152,1280,
             1536,2048,4096,8192,12288,16384,20480,24576,28672,32768,
             49152,65536,98304,131072,196608]
    for size in sizes:
        for order in [0,1]:
            add('working_set', span=size*1024, order=order)
    for spacing in [64,96,128,160,192,224,256,320,384,512,640,768,1024]:
        for order in [0,1]:
            add('pattern_latency', spacing=spacing, order=order)
    for block in [8,16,24,32,48,64,96,128,160,192,224,256,320,384,512,768,1024]:
        for gap in [1,4]:
            for order in [0,1]:
                add('pattern_bandwidth', 'bandwidth', spacing=block*gap, block=block, order=order)
    for read in range(0,101,10):
        for order in [0,1]:
            add('mix', 'bandwidth', spacing=1024, block=1024, read=read, order=order)
    for threads in range(1,len(cpus)+1):
        add('intensity_threads', threads=threads)
    for streams in [1,2,3,4,6,8,10,12,16,20,24,28,32,40,48,56,64]:
        add('intensity_streams', streams=streams)
    for size in [4,8,12,16,24,32,48,64,96,128,192]:
        for order in [0,1]:
            for huge in [0,1]:
                add('tlb', span=size*2**20, spacing=4096, order=order, huge=huge)
    for size in [32*1024,192*2**20]:
        add('pitfall', 'bandwidth', span=size, spacing=1024, block=1024, order=0)
    return cases


def arguments(root, case, cpus, target):
    return [str(root/'build/memory_bench'), case['mode'],
            *[str(case[k]) for k in ['bytes','spacing','block','read_pct','random','huge','streams']],
            str(target), ','.join(map(str, cpus[:case['threads']]))]


def require_evidence(row):
    if row['check'] != 'pass' or float(row['elapsed_ns']) <= 0:
        raise ValueError('Benchmark correctness or timing check failed')
    counter_required = row.get('study') in [None, 'tlb'] or (row.get('study')=='working_set' and int(row['random'])==1)
    if counter_required and str(row['counters_available']).lower() != 'true':
        raise ValueError('Required hardware counters unavailable or multiplexed; executable needs existing perf access.')
    if int(row['huge']) and int(row['huge_bytes']) < int(row['bytes'])*int(row['threads']):
        raise ValueError('Required huge-page backing was not verified')


def preflight(root):
    for name in ['make', os.environ.get('CC','cc')]:
        if not shutil.which(name):
            raise ValueError(f'Missing dependency: {name}')
    command(['make','-f','build.mk', f'PYTHON={sys.executable}', 'all','check'], cwd=root)
    acquisition, _ = modules(root)
    cpus = acquisition.select_cpus()
    # Probe the actual executable, retaining existing file capabilities when up-to-date.
    for huge in [0,1]:
        case = dict(mode='latency', bytes=4*2**20, spacing=4096, block=8,
                    read_pct=100, random=1, huge=huge, streams=1, threads=1)
        row = dict(case, **json.loads(subprocess.check_output(arguments(root,case,cpus,15), text=True)))
        require_evidence(row)


def acquire(root, output):
    acquisition, _ = modules(root)
    cpus = acquisition.select_cpus()
    cases = build_cases(cpus)
    meta = acquisition.collect_metadata('report-full',45,250,cpus,
        os.environ.get('CC','cc'), os.environ.get('CFLAGS','-O3 -march=native -std=c11 -Wall -Wextra -Wpedantic'),cases)
    meta.update(rounds=3,trials_per_round=15,
                benchmark_sha256=digest(root/'build/memory_bench'),
                protocol='Three rounds of fifteen trials; 250 ms each. Paired access orders alternate. Condition groups shuffled each trial. Fresh process and allocation; warm-up outside timing.')
    acquisition.snapshot_sources(output)
    shutil.copy2(root/'build.mk',output/'source/build.mk')
    write_json(output/'metadata.json',meta)
    # Keep pattern/mix/working-set comparisons paired and alternate pair order.
    groups = collections.defaultdict(list)
    for c in cases:
        key = tuple((k,v) for k,v in c.items() if k != 'random' and not (c['study']=='pitfall' and k=='bytes'))
        groups[key].append(c)
    import csv
    rng = random.Random(4320)
    count = 0
    with (output/'raw.csv').open('w',newline='') as stream:
        writer = None
        try:
            for trial in range(45):
                batches = list(groups.values())
                rng.shuffle(batches)
                for batch in batches:
                    for case in batch[::(-1 if trial%2 else 1)]:
                        args = arguments(root,case,cpus,250)
                        result = json.loads(subprocess.check_output(args,text=True))
                        row = dict(case,trial=trial,round=trial//15+1,trial_in_round=trial%15,**result)
                        if writer is None:
                            writer = csv.DictWriter(stream,fieldnames=list(row))
                            writer.writeheader()
                        writer.writerow(row)
                        stream.flush()
                        count += 1
                        meta['commands'].append(args)
                        require_evidence(row)
                print(f'Project 2: round {trial//15+1}/3, trial {trial%15+1}/15 ({count} observations)',flush=True)
        finally:
            meta['observations']=count
            meta['raw_sha256']=digest(output/'raw.csv')
            write_json(output/'metadata.json',meta)


def validate(root, run):
    rows = read_csv(run/'raw.csv')
    meta = json.loads((run/'metadata.json').read_text())
    fields = ['study','mode','bytes','spacing','block','read_pct','random','huge','streams','threads']
    def key(r): return tuple(str(r[k]) for k in fields)
    expected = {key(c) for c in meta['cases']}
    observed = collections.defaultdict(list)
    if meta.get('raw_sha256') and digest(run/'raw.csv') != meta['raw_sha256']:
        raise ValueError('Raw CSV checksum mismatch')
    for row in rows:
        require_evidence(row)
        observed[key(row)].append(int(row['trial']))
        for metric in ['ns_per_access','chain_latency_ns','million_accesses_s','gib_s']:
            if not np.isfinite(float(row[metric])) or float(row[metric]) <= 0:
                raise ValueError(f'Invalid {metric}')
    if set(observed) != expected or any(sorted(v)!=list(range(meta['trials'])) for v in observed.values()):
        raise ValueError('Missing/duplicate configurations or trials')


def plot(root, run):
    _, analysis = modules(root)
    raw = read_csv(run/'raw.csv')
    meta = json.loads((run/'metadata.json').read_text())
    ss = analysis.summarize_rows(raw,meta)
    write_csv(run/'summary.csv',ss)
    if meta.get('rounds'):
        rounds=[]
        for n in range(1,meta['rounds']+1):
            rr=[dict(r,trial=r['trial_in_round']) for r in raw if int(r['round'])==n]
            rounds.extend(dict(round=n,**s) for s in analysis.summarize_rows(rr,dict(meta,trials=meta['trials_per_round'])))
        write_csv(run/'round_summary.csv',rounds)
    baselines=analysis.baseline_rows(ss)
    coverage=analysis.write_tables(run,meta,raw,ss,baselines)
    coverage['hardware_counters']=all(s['counters_available'] for s in ss if s['study']=='tlb' or (s['study']=='working_set' and s['random']==1))
    coverage['missing_required_evidence']=[] if coverage['hardware_counters'] else ['Required cache/TLB counters or baseline cycles']
    write_json(run/'coverage.json',coverage)
    f=Figures(run,[dict(path='raw.csv',sha256=digest(run/'raw.csv'))])
    def select(study,**kw):
        return [s for s in ss if s['study']==study and all(s[k]==v for k,v in kw.items())]
    def pts(rows,key,metric,label,scale=1):
        return [dict(series=label,x=s[key]*scale,y=s[metric],y_q25=s[metric+'_q25'],y_q75=s[metric+'_q75']) for s in sorted(rows,key=lambda s:s[key])]
    def chart(name,study,key,metric,xlabel,ylabel,series,**kwargs):
        data=[]
        for label,filters in series:
            data+=pts(select(study,**filters),key,metric,label,kwargs.pop('scale',1) if len(series)==1 else 1)
        f.lines(name,data,xlabel,ylabel,kwargs.pop('caption',name.replace('_',' ')),**kwargs)
    rows=[]
    for i,s in enumerate(baselines):
        rows.append(dict(series='Dependent loads',x=i,y=s['ns_per_access'],y_q25=s['ns_per_access_q25'],y_q75=s['ns_per_access_q75']))
    f.bars('01_baseline',rows,['16 KiB','512 KiB','8 MiB','192 MiB'],'Dependent-load latency (ns)',
           'Unloaded random pointer-chain baseline; nominal L1/L2/LLC/DRAM-sized spans.')
    orders=[('Sequential',{'random':0}),('Random',{'random':1})]
    chart('02_pattern_latency','pattern_latency','spacing','ns_per_access','Pointer spacing (bytes)','Dependent-load latency (ns)',orders,logx=True,settings={'span_MiB':96})
    data=[]
    for order,label in [(0,'Sequential'),(1,'Random')]:
        for gap in [1,4]:
            data += [dict(r,color='#24649a' if order==0 else '#bb6c16',marker='o' if order==0 else 's',linestyle='-' if gap==1 else '--') for r in pts([s for s in select('pattern_bandwidth',random=order) if s['spacing']==gap*s['block']], 'block','gib_s',f'{label}, {gap}× spacing')]
    f.lines('03_granularity_bandwidth',data,'Useful bytes per transfer','Useful bandwidth (GiB/s)',
            'Sequential/random transfers across a fixed 96 MiB span.',logx=True)
    for metric,label in [('gib_s','Useful bandwidth (GiB/s)'),('ns_per_access','Average block processing time (ns)')]:
        data=[]
        for order,name in [(0,'Sequential'),(1,'Random')]:
            data+=sorted([dict(r,x=100-r['x']) for r in pts(select('mix',random=order),'read_pct',metric,name)],key=lambda r:r['x'])
        f.lines('04_mix_'+metric,data,'Writes (%)',label,'96 MiB span; 1 KiB blocks. Block processing time is throughput-derived, not isolated load latency.')
    for study,key,title in [('intensity_streams','streams','Independent chains on one core'),('intensity_threads','threads','Physical cores, one chain per core')]:
        for metric,label in [('million_accesses_s','Completed dependent loads (million/s)'),('chain_latency_ns','Mean chain round-trip time (ns)')]:
            chart('05_'+study+'_'+metric,study,key,metric,'Independent chains' if key=='streams' else 'Physical cores',label,[(title,{})],settings={'span_MiB_per_worker':96})
    data=[]
    for study,key,label in [('intensity_streams','streams','Independent chains on one core'),('intensity_threads','threads','Physical cores, one chain per core')]:
        for s in sorted(select(study),key=lambda s:s[key]):
            data.append(dict(series=label,x=s['chain_latency_ns'],x_q25=s['chain_latency_ns_q25'],x_q75=s['chain_latency_ns_q75'],y=s['million_accesses_s'],y_q25=s['million_accesses_s_q25'],y_q75=s['million_accesses_s_q75'],concurrency=s[key]))
    f.lines('06_throughput_latency',data,'Mean chain round-trip time (ns)','Completed dependent loads (million/s)',
            'Concurrency sweep. Chain round-trip time includes interleaved software work; it is not isolated hardware latency.')
    caches=[('L'+str(c['level']),c['bytes']) for c in meta['caches']]
    for metric,label in [('ns_per_access','Dependent-load latency (ns)'),('million_accesses_s','Completed dependent loads (million/s)')]:
        chart('07_working_set_'+metric,'working_set','bytes',metric,'Mapped working-set span (bytes)',label,orders,logx=True,caches=caches)
    for metric,label in [('ns_per_access','Dependent-load latency (ns)'),('llc_misses_per_1000','LLC read misses per 1,000 loads')]:
        chart('08_cache_'+metric,'working_set','bytes',metric,'Mapped working-set span (bytes)',label,[('Random dependent chain',{'random':1})],logx=True,caches=caches)
    for order,label in [(0,'Sequential'),(1,'Random')]:
        for metric,ylabel in [('ns_per_access','Dependent-load latency (ns)'),('dtlb_misses_per_1000','dTLB read misses per 1,000 loads')]:
            data=[]
            for huge,name in [(0,'4 KiB pages'),(1,'Verified huge pages')]:
                data+=pts(select('tlb',random=order,huge=huge),'bytes',metric,name,1/2**20)
            f.lines(f'09_tlb_{order}_{metric}',data,f'{label} page access: span (MiB)',ylabel,
                    f'{label} page order; one access per 4 KiB.',logx=True)
    rows=[]
    for i,s in enumerate(sorted(select('pitfall'),key=lambda s:s['bytes'])):
        rows.append(dict(series='Sequential reads',x=i,y=s['gib_s'],y_q25=s['gib_s_q25'],y_q75=s['gib_s_q75']))
    f.bars('10_cache_reuse',rows,['32 KiB','192 MiB'],'Useful read bandwidth (GiB/s)',
           'Same sequential 1 KiB read kernel; the cache-sized buffer does not measure DRAM bandwidth.')
    pairs=[]
    for block in sorted({r['block'] for r in raw if r['study']=='pattern_bandwidth'}):
        rr=[r for r in raw if r['study']=='pattern_bandwidth' and r['block']==block and r['spacing']==4*block]
        lookup={(int(r['trial']),r['random']):r['gib_s'] for r in rr}
        ratios=np.array([lookup[t,1]/lookup[t,0] for t in range(meta['trials'])])
        pairs.append(point('All trials',block,ratios,block_bytes=block))
        for number in range(1,meta.get('rounds',1)+1):
            start=(number-1)*meta.get('trials_per_round',meta['trials'])
            stop=number*meta.get('trials_per_round',meta['trials'])
            pairs.append(dict(series=f'Round {number}',x=block*1.025**(number-(meta.get('rounds',1)+1)/2),y=float(np.median(ratios[start:stop])),block_bytes=block))
    fig,ax=f.new('Useful bytes per transfer (four-times spacing)','Random / sequential useful bandwidth (×)')
    for i,label in enumerate(dict.fromkeys(r['series'] for r in pairs)):
        rr=[r for r in pairs if r['series']==label]
        x=np.array([r['x'] for r in rr]);y=np.array([r['y'] for r in rr])
        if i==0:
            ax.errorbar(x,y,yerr=[y-[r['y_q25'] for r in rr],[r['y_q75'] for r in rr]-y],fmt='o',color='#24649a',capsize=4,label=label)
        else:
            ax.scatter(x,y,facecolors='none',edgecolors='#bb6c16',marker=['s','^','D'][(i-1)%3],s=30,label=label)
    ax.set_xscale('log',base=2)
    ax.set_xticks([8,32,64,128,256,512,1024],['8','32','64','128','256','512','1024'])
    ax.axhline(1,color='#555',ls='--',lw=1)
    ax.set_ylim(bottom=0)
    f.finish(fig,ax,'11_paired_bandwidth_ratio',pairs,'Ratios paired by trial; pooled median and IQR, with per-round medians slightly offset horizontally for readability.')
    f.complete()
