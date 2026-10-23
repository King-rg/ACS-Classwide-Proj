"""Run all SIMD report studies and export independent panels."""
from pathlib import Path
import collections
import json
import os
import shutil
import subprocess
import sys
import numpy as np
from report_common import (Figures, COLORS, command, digest, point, read_csv,
                           samples, stats, write_csv, write_json)

STUDIES={
    'working-set': ('experiments/run_auto_comparison.py',['--extended','--aligned']),
    'alignment': ('experiments/alignment-sweep/run.py',[]),
    'supplemental': ('experiments/supplemental-c/run.py',[]),
    'native': ('experiments/native-comparison/run.py',[]),
    'cycles': ('experiments/cycles/run.py',[]),
}
KERNELS=['axpy','dot','multiply']
TYPES=['float','double']


def preflight(root):
    for name in ['gcc','make','taskset','objdump','perf']:
        if not shutil.which(name):raise ValueError(f'Missing dependency: {name}')
    flags=Path('/proc/cpuinfo').read_text()
    if ' avx ' not in flags or ' fma ' not in flags:
        raise ValueError('The current SIMD report kernels require AVX and FMA support')
    command(['make','-f','build.mk','AUTO=1','all','check'],cwd=root)
    probe=root/'build/report-counter-probe'
    probe.parent.mkdir(exist_ok=True)
    source='#include "counter.h"\nint main(void){cycle_start();for(volatile int i=0;i<100000;i++){}cycle_stop();return cycle_value?0:2;}\n'
    command(['gcc','-x','c','-D_GNU_SOURCE','-I'+str(root/'experiments/cycles'),'-o',probe,'-'],input=source,text=True)
    result=subprocess.run(['taskset','-c',str(min(os.sched_getaffinity(0))),str(probe)],capture_output=True,text=True)
    if result.returncode:
        raise ValueError('Required core-cycle counter unavailable: '+result.stderr.strip())


def acquire(root, output):
    source=output/'source'
    shutil.copytree(root/'src',source/'src')
    shutil.copytree(root/'experiments',source/'experiments',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(root/'build.mk',source/'build.mk')
    shutil.copy2(root/'Makefile',source/'Makefile')
    write_json(output/'metadata.json',dict(profile='report-full',studies=list(STUDIES),cpu=min(os.sched_getaffinity(0))))
    for name,(script,args) in STUDIES.items():
        print(f'Project 1: {name}',flush=True)
        env=os.environ.copy()
        env['REPORT_RUN_DIR']=str(output/'studies'/name)
        command([sys.executable,root/script,*args],env=env,cwd=root)


def read_studies(run):
    result={}
    for name in STUDIES:
        path=run/'studies'/name
        meta=json.loads((path/'metadata.json').read_text())
        files={p.name:read_csv(p) for p in path.glob('*.csv') if p.name in ['raw.csv',*[k+'.csv' for k in KERNELS],*[k+'-cycles.csv' for k in KERNELS]]}
        result[name]=(meta,files)
    return result


def grouped(rows,keys):
    groups=collections.defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    return groups


def validate(root, run):
    studies=read_studies(run)
    for name,(meta,files) in studies.items():
        count=int(meta['trials'])
        for filename,rows in files.items():
            if not rows:raise ValueError(f'Empty {name}/{filename}')
            for row in rows:
                if row.get('correct',row.get('check','pass'))!='pass':raise ValueError('SIMD correctness failure')
                if 'cpu' in row and int(row['cpu'])!=int(meta['cpu']):raise ValueError('CPU differs from run metadata')
            if name=='supplemental':
                keys=['study','type','n','stride','offset','variant'];metric='ns_per_call'
                expected=set()
                for study,typ,n,stride,offset,calls in meta['cases']:
                    variants=['calibration'] if study in ['stream','compute'] else ['scalar','strict','auto'] if study=='dot' else ['scalar','auto']
                    expected.update((study,typ,str(n),str(stride),str(offset),v) for v in variants)
            elif name=='alignment':
                keys=['kernel','datatype','base','condition','implementation'];metric='elapsed_ns'
                expected={(k,t,str(b),c,v) for k in KERNELS for t in TYPES for b in meta['bases'] for c in ['clean','shifted','tail','combined'] for v in ['scalar','auto']}
            else:
                keys=['kernel','datatype','n','implementation'];metric='cycles' if '-cycles' in filename else 'elapsed_ns'
                kernel=filename.split('-')[0].split('.')[0]
                variants=['avx','native'] if name=='native' else ['scalar','auto']
                expected={(kernel,t,str(n),v) for t in TYPES for n in meta['sizes'] for v in variants}
            groups=grouped(rows,keys)
            if set(groups)!=expected:raise ValueError(f'Missing/extra conditions in {name}/{filename}')
            for rr in groups.values():samples(rr,metric,count)
        required={'raw.csv'} if name in ['supplemental','alignment'] else {k+'.csv' for k in KERNELS}
        if name=='cycles':required|={k+'-cycles.csv' for k in KERNELS}
        if not required.issubset(files):raise ValueError(f'Missing raw CSVs for {name}')


def plot(root, run):
    studies=read_studies(run)
    sources=[dict(path=str(p.relative_to(run)),sha256=digest(p)) for name in STUDIES for p in (run/'studies'/name).glob('*.csv') if p.name in studies[name][1]]
    f=Figures(run,sources)
    meta,files=studies['working-set']
    cache=json.loads((run/'studies/working-set/cache_metadata.json').read_text())
    caches=[(c['level'],c['capacity_kib']*1024) for c in cache['caches']]
    summary=[]
    for kernel in KERNELS:
        data=grouped(files[kernel+'.csv'],['datatype','n','implementation'])
        speed=[]
        for typ in TYPES:
            throughput=[]
            for n in meta['sizes']:
                arrays={v:samples(data[typ,str(n),v],'elapsed_ns',meta['trials']) for v in ['scalar','auto']}
                span=n*(4 if typ=='float' else 8)*(3 if kernel=='multiply' else 2)
                ratio=point(typ,span,arrays['scalar']/arrays['auto'],kernel=kernel,datatype=typ,n=n)
                speed.append(ratio)
                entry=dict(ratio)
                for v,label in [('scalar','Scalar baseline'),('auto','Auto-vectorized')]:
                    rate=(1 if kernel=='multiply' else 2)*n/arrays[v]
                    throughput.append(point(label,span,rate,kernel=kernel,datatype=typ,n=n))
                    entry[v+'_ns'],entry[v+'_ns_q25'],entry[v+'_ns_q75']=stats(arrays[v])
                    entry[v+'_gflops'],entry[v+'_gflops_q25'],entry[v+'_gflops_q75']=stats(rate)
                summary.append(entry)
            f.lines(f'02_throughput_{kernel}_{typ}',throughput,'Kernel working set (bytes)','Achieved throughput (GFLOP/s)',
                    f'{kernel}, {typ}: scalar and auto-vectorized loops; nominal cache capacities, not measured residency boundaries.',logx=True,caches=caches)
        f.lines(f'01_speedup_{kernel}',speed,'Kernel working set (bytes)','Scalar / auto-vectorized time (×)',
                f'{kernel}: matched trial ratios, float32 and float64. SIMD gains may compress beyond nominal cache capacities.',logx=True,caches=caches,reference=1)
    write_csv(run/'tables/working_set_summary.csv',summary)

    meta,files=studies['alignment']
    data=grouped(files['raw.csv'],['kernel','datatype','base','condition','implementation'])
    labels={'clean':'Aligned baseline','shifted':'Shifted one element','tail':'Tail only','combined':'Shifted + tail'}
    align_summary=[]
    for typ in TYPES:
        aggregate=[]
        for condition,label in labels.items():
            for base in meta['bases']:
                ratios=[]
                for kernel in KERNELS:
                    rr={v:data[kernel,typ,str(base),condition,v] for v in ['scalar','auto']}
                    a={v:samples(rr[v],'elapsed_ns',meta['trials']) for v in rr}
                    ratio=float(np.median(a['scalar'])/np.median(a['auto']))
                    ratios.append(ratio)
                    align_summary.append(dict(kernel=kernel,datatype=typ,base=base,condition=condition,speedup=ratio))
                aggregate.append(dict(series=label,x=base,y=float(np.exp(np.mean(np.log(ratios))))))
        f.lines(f'03_alignment_{typ}',aggregate,'Base array length (elements)','Scalar / auto-vectorized time (×)',
                f'{typ}: equal-kernel geometric mean of per-kernel ratios of median runtimes. No aggregate uncertainty interval is asserted.',logx=True,reference=1)
        representative=[dict(r,x=list(labels.values()).index(r['series']),series=typ,y_q25=r['y'],y_q75=r['y']) for r in aggregate if r['x']==32768]
        f.bars(f'04_alignment_representative_{typ}',representative,list(labels.values()),'Scalar / auto-vectorized time (×)',
               f'{typ}, base N=32,768; equal-kernel geometric mean; tails add seven elements, shifts add one element. No uncertainty interval is asserted.')
    write_csv(run/'tables/alignment_summary.csv',align_summary)

    meta,files=studies['supplemental']
    data=grouped(files['raw.csv'],['study','type','n','stride','offset','variant'])
    def values(study,typ,n,stride,offset,variant):
        return samples(data[study,typ,str(n),str(stride),str(offset),variant],'ns_per_call',meta['trials'])
    for footprint in [256*1024,192*2**20]:
        speed=[]
        for typ in TYPES:
            size=4 if typ=='float' else 8
            bandwidth=[]
            for stride in [1,2,4,8]:
                n=footprint//(2*size*stride)
                a={v:values('stride',typ,n,stride,0,v) for v in ['scalar','auto']}
                speed.append(point(typ,stride,a['scalar']/a['auto']))
                for v,label in [('scalar','Scalar'),('auto','Auto-vectorized')]:
                    bandwidth.append(point(label,stride,3*n*size/a[v]*1e9/2**30))
            f.lines(f'05_stride_bandwidth_{footprint}_{typ}',bandwidth,'Stride (elements)','Useful bandwidth (GiB/s)',
                    f'AXPY {typ}, {footprint} byte footprint. Useful payload excludes unused cache-line bytes.',ticks=([1,2,4,8],['1','2','4','8']))
        f.lines(f'05_stride_speedup_{footprint}',speed,'Stride (elements)','Scalar / auto-vectorized time (×)',
                f'AXPY, {footprint} byte footprint; matched scalar/auto trials.',reference=1,ticks=([1,2,4,8],['1','2','4','8']))
    for typ in TYPES:
        for base in [32,4096]:
            rows=[]
            for variant,label in [('scalar','Scalar'),('auto','Auto-vectorized')]:
                for offset in [0,1]:
                    for tail in range(8):
                        rows.append(point(label+(' aligned' if offset==0 else ' shifted'),tail,
                                          values('alignment',typ,base+tail,1,offset,variant)/(base+tail)))
            f.lines(f'04_tail_cost_{typ}_{base}',rows,'Added elements','Time per element (ns)',
                    f'AXPY {typ}, base N={base}; batched calls, aligned versus shifted one element.')
        rows=[]
        for v,label in [('scalar','Scalar, relaxed FP'),('strict','Auto, strict FP'),('auto','Auto, relaxed FP')]:
            for i,n in enumerate([4096,65536]):
                rows.append(point(label,i,values('dot',typ,n,1,0,v)/n))
        f.bars(f'06_strict_dot_{typ}',rows,['4,096 elements','65,536 elements'],'Time per element (ns)',
               f'{typ} dot product: strict versus relaxed floating-point reassociation; compiler/disassembly evidence retained.')
    stream=values('stream','float',16777216,1,0,'calibration')
    compute=values('compute','float',1000000,1,0,'calibration')
    bandwidth=16*16777216/stream
    peak=128e6/compute
    fig,ax=f.new('Estimated arithmetic intensity (FLOP/byte)','Achieved throughput (GFLOP/s)')
    xx=np.logspace(-2,2,200)
    roof=np.minimum(np.median(peak),np.median(bandwidth)*xx)
    lo=np.minimum(np.percentile(peak,25),np.percentile(bandwidth,25)*xx)
    hi=np.minimum(np.percentile(peak,75),np.percentile(bandwidth,75)*xx)
    ax.loglog(xx,roof,color='#707982',label='Estimated DRAM roof')
    ax.fill_between(xx,lo,hi,color='#707982',alpha=.13)
    ax.axhline(np.median(peak),color='#707982',ls=':',label='Measured register-FMA peak estimate')
    rows=[dict(series='Estimated DRAM roof',x=x,y=y,y_q25=l,y_q75=h) for x,y,l,h in zip(xx,roof,lo,hi)]
    for i,v in enumerate(['scalar','auto']):
        n=192*2**20//8
        r=point('AXPY float '+v,2/12,2*n/values('roofline','float',n,1,0,v))
        rows.append(r)
        ax.errorbar(r['x'],r['y'],yerr=[[r['y']-r['y_q25']],[r['y_q75']-r['y']]],fmt='o' if i==0 else 's',color=COLORS[i],capsize=4,label=r['series'])
    f.finish(fig,ax,'07_roofline',rows,'Measured bandwidth with a write-allocation model and an empirical register-FMA peak; AXPY float32. Calibration IQR bands are not confidence intervals.')
    write_csv(run/'tables/roofline_calibration.csv',[dict(trial=i,stream_useful_GB_s=12*16777216/stream[i],estimated_physical_GB_s=bandwidth[i],peak_gflops=peak[i]) for i in range(len(stream))])

    meta,files=studies['cycles']
    for kernel in KERNELS:
        data=grouped(files[kernel+'-cycles.csv'],['datatype','n','implementation'])
        for typ in TYPES:
            rows=[]
            for variant,label in [('scalar','Scalar'),('auto','Auto-vectorized')]:
                for n in meta['sizes']:
                    rows.append(point(label,n,samples(data[typ,str(n),variant],'cycles',meta['trials'])/n))
            f.lines(f'08_cycles_{kernel}_{typ}',rows,'Array length (elements)','Core cycles per element',
                    f'{kernel}, {typ}: measured user-space cycles, continuously scheduled counter; timer/dispatch overhead included.',logx=True)
    meta,files=studies['native']
    rows=[]
    for kernel in KERNELS:
        data=grouped(files[kernel+'.csv'],['datatype','n','implementation'])
        for typ in TYPES:
            for n in meta['sizes']:
                a={v:samples(data[typ,str(n),v],'elapsed_ns',meta['trials']) for v in ['avx','native']}
                median,low,high=stats(a['avx']/a['native'])
                rows.append(dict(kernel=kernel,datatype=typ,n=n,avx_to_native_ratio=median,q25=low,q75=high))
    write_csv(run/'tables/native_comparison.csv',rows)
    f.complete()
