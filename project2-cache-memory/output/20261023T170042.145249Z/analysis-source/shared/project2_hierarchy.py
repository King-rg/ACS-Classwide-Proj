"""Source-resolved full-hierarchy AMAT experiment; never fit missing timings.

Quality failures are retained as flags and never terminate the size/trial sweep.
An absent conditional class remains absent, even in exploratory figures.
"""
from pathlib import Path
import collections
import csv
import gzip
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time

import numpy as np
from report_common import digest, read_csv, write_csv, write_json

SCOPE = 'amat-hierarchy'
LEVELS = ('L1', 'L2', 'L3', 'DRAM', 'FB', 'unknown')
MIN_SAMPLES = 1000
SAMPLE_FIELDS = 'pid,time,ip,addr,weight,data_src,period'


def parse_sample(line):
    """Parse perf's fixed field order; unknown sources are not cache hits."""
    parts = line.split('|')
    if len(parts) < 3:
        return None
    prefix, tail = parts[0].split(), parts[-1].split()
    if len(prefix) != 5 or len(tail) < 4:
        return None
    try:
        seconds, fraction = prefix[1].rstrip(':').split('.')
        level_text = next(p for p in parts if p.startswith('LVL '))
        if level_text == 'LVL L1 hit': level = 'L1'
        elif level_text == 'LVL L2 hit': level = 'L2'
        elif level_text == 'LVL L3 hit': level = 'L3'
        elif level_text in ('LVL RAM hit', 'LVL Local RAM hit'): level = 'DRAM'
        elif 'LFB' in level_text or 'MAB' in level_text: level = 'FB'
        else: level = 'unknown'
        return dict(pid=int(prefix[0]), time_ns=int(seconds)*10**9+int(fraction.ljust(9,'0')),
                    period=int(prefix[2]), address=int(prefix[3],16), data_src=prefix[4],
                    cycles=int(tail[-2]), ip=int(tail[-1],16), level=level)
    except (ValueError, StopIteration):
        return None


def accept_sample(sample, measurement):
    return (sample['pid'] == measurement['pid']
            and sample['ip'] == measurement['load_ip']
            and measurement['data_start'] <= sample['address'] < measurement['data_end']
            and (sample['address']-measurement['data_start']) % 64 == 0
            and measurement['start_ns'] <= sample['time_ns'] <= measurement['end_ns']
            and sample['cycles'] > 0 and sample['period'] > 0)


def decode(data_path, measurement):
    args = ['perf','script','-i',str(data_path),'--ns','--show-lost-events','-F',SAMPLE_FIELDS]
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stats = {level: dict(n=0, weight=0, weighted_cycles=0, minimum=None, maximum=None)
             for level in LEVELS}
    counts = collections.Counter()
    decoded = data_path.with_suffix('.samples.csv.gz')
    with gzip.open(decoded,'wt',newline='') as stream:
        fields=['pid','time_ns','period','address','data_src','cycles','ip','level']
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for line in process.stdout:
            if 'LOST' in line.upper(): counts['lost_records'] += 1
            sample=parse_sample(line)
            if sample is None:
                if line.strip(): counts['unparsed_lines'] += 1
                continue
            counts['decoded_samples'] += 1
            if not accept_sample(sample,measurement):
                counts['excluded_samples'] += 1;continue
            writer.writerow(sample);counts['retained_samples'] += 1
            stat=stats[sample['level']];n=sample['cycles'];w=sample['period']
            stat['n']+=1;stat['weight']+=w;stat['weighted_cycles']+=n*w
            stat['minimum']=n if stat['minimum'] is None else min(n,stat['minimum'])
            stat['maximum']=n if stat['maximum'] is None else max(n,stat['maximum'])
    stderr=process.stderr.read();process.wait()
    data_path.with_suffix('.decode.log').write_text(stderr)
    if 'lost' in stderr.lower():counts['lost_records']+=1
    return dict(levels=stats, **counts, decode_returncode=process.returncode)


def ns_per_cycle(measurement):
    if not measurement.get('counters_available') or not measurement.get('cycles'):
        return None
    # Unhalted reference cycles avoid treating descheduled wall time as frequency.
    return measurement['ref_cycles']/measurement['cycles']*1e9/measurement['tsc_hz']


def analyze_pair(unprofiled, sampled, samples):
    row={}; flags=[]; hf=[];pf=[];mf=[]
    levels=samples.get('levels',{})
    for level in LEVELS:
        stat=levels.get(level,{})
        row[level+'_samples']=stat.get('n',0)
        row[level+'_mean_cycles']=(stat['weighted_cycles']/stat['weight']
                                   if stat.get('weight') else None)
        row[level+'_min_cycles']=stat.get('minimum')
        row[level+'_max_cycles']=stat.get('maximum')
    ratio=ns_per_cycle(sampled)
    row['sample_ns_per_cycle']=ratio
    row['sample_core_GHz']=1/ratio if ratio else None
    row['measured_ns']=unprofiled.get('ns_per_access')
    row['profiled_ns']=sampled.get('ns_per_access')
    row['h_ns']=row['p_ns']=row['amat_ns']=row['m']=None
    row['h_cycles']=row['p_cycles']=row['dram_ns']=None
    row['hit_samples']=sum(row[k+'_samples'] for k in ('L1','L2','L3'))
    if samples.get('lost_records'):flags.append('sample_loss')
    if samples.get('decode_returncode'):flags.append('decode_failure')
    if not ratio:flags.append('sample_frequency_unavailable')
    total_weight=sum(v.get('weight',0) for v in levels.values())
    unknown_weight=sum(levels.get(k,{}).get('weight',0) for k in ('FB','unknown'))
    row['other_sample_fraction']=unknown_weight/total_weight if total_weight else None
    if total_weight and unknown_weight/total_weight>.01:flags.append('unclassified_or_fill_buffer_above_1pct')
    if unprofiled.get('counters_available') and unprofiled.get('operations'):
        ops=unprofiled['operations']
        counts=[unprofiled[k] for k in ('l1_hits','l2_hits','l3_hits')]
        hit_count=sum(counts);dram=unprofiled['dram_reads']
        row['m']=dram/ops
        row['counter_classified_fraction']=(hit_count+dram)/ops
        if not 0<=row['m']<=1:mf.append('counter_m_outside_probability_range')
        if not .98<=row['counter_classified_fraction']<=1.02:
            flags.append('counter_coverage_outside_2pct')
        represented=0;weighted=0
        for level,count in zip(('L1','L2','L3'),counts):
            row[level+'_counter_fraction']=count/ops
            value=row[level+'_mean_cycles']
            if value is not None:
                represented+=count;weighted+=count*value
        row['unrepresented_hit_fraction']=1-represented/hit_count if hit_count else None
        if represented and ratio:
            row['h_cycles']=weighted/represented
            row['h_ns']=row['h_cycles']*ratio
            if represented<hit_count:hf.append('some_cache_levels_unsampled')
        if row['hit_samples']<MIN_SAMPLES:hf.append('fewer_than_1000_hit_samples')
        if total_weight:
            source_fractions=[levels.get(k,{}).get('weight',0)/total_weight for k in ('L1','L2','L3','DRAM')]
            counter_fractions=[c/ops for c in counts+[dram]]
            row['max_source_fraction_difference']=max(abs(a-b) for a,b in zip(source_fractions,counter_fractions))
            if row['max_source_fraction_difference']>.05:flags.append('sampling_counter_disagreement_above_5pp')
    else:
        flags.append('unprofiled_counters_unavailable')
    dram_cycles=row['DRAM_mean_cycles']
    if dram_cycles is not None and ratio:
        row['dram_ns']=dram_cycles*ratio
        if row['h_ns'] is not None:
            row['p_cycles']=dram_cycles-row['h_cycles']
            row['p_ns']=row['dram_ns']-row['h_ns']
            if row['p_ns']<0:pf.append('negative_observed_penalty')
    if row['DRAM_samples']<MIN_SAMPLES:pf.append('fewer_than_1000_DRAM_samples')
    if row['p_ns'] is not None and row['m'] is not None and 0<=row['m']<=1:
        row['amat_ns']=row['h_ns']+row['m']*row['p_ns']
    if row['profiled_ns'] and row['measured_ns']:
        row['profiled_time_ratio']=row['profiled_ns']/row['measured_ns']
        if abs(row['profiled_time_ratio']-1)>.10:flags.append('paired_timing_difference_above_10pct')
    for name,measurement in [('unprofiled',unprofiled),('sampled',sampled)]:
        if measurement.get('elapsed_ns'):
            fraction=measurement.get('thread_cpu_ns',0)/measurement['elapsed_ns']
            row[name+'_scheduled_fraction']=fraction
            if fraction<.95:flags.append(name+'_descheduled_above_5pct')
    row['quality_flags']=';'.join(flags)
    row['h_flags']=';'.join(flags+hf)
    row['p_flags']=';'.join(flags+hf+pf)
    row['m_flags']=';'.join(mf+(['unprofiled_counters_unavailable'] if row['m'] is None else []))
    row['h_supported']=row['h_ns'] is not None and not row['h_flags']
    row['p_supported']=row['p_ns'] is not None and not row['p_flags']
    row['amat_supported']=row['amat_ns'] is not None and not (row['p_flags'] or row['m_flags'])
    return row


def acquisition_pair(root, directory, size, duration, period, threshold, reverse=False):
    directory.mkdir(parents=True,exist_ok=True)
    base=[str(root/'build/memory_bench'),'hierarchy',str(size),str(duration),'0']
    result={};attempts=[]
    for name in (['sampled','unprofiled'] if reverse else ['unprofiled','sampled']):
        env=os.environ.copy();env.pop('PROJECT2_HIERARCHY_SAMPLED',None)
        args=base
        if name=='sampled':
            env['PROJECT2_HIERARCHY_SAMPLED']='1'
            args=['perf','mem','record','-t','load','--ldlat='+str(threshold),'-U','-k','mono',
                  '-o',str(directory/'sampled.data'),'-c',str(period),'--',*base]
        started=time.time()
        with (directory/(name+'.log')).open('w') as log:
            process=subprocess.run(args,stdout=subprocess.PIPE,stderr=log,text=True,env=env)
        (directory/(name+'.json')).write_text(process.stdout)
        try: measurement=json.loads(process.stdout)
        except json.JSONDecodeError:measurement={}
        result[name]=measurement
        attempts.append(dict(command=args,returncode=process.returncode,started_unix=started,elapsed_seconds=time.time()-started))
    write_json(directory/'commands.json',attempts)
    samples={}
    if result['sampled'] and (directory/'sampled.data').exists():
        try:samples=decode(directory/'sampled.data',result['sampled'])
        except (OSError,ValueError) as error:samples={'decode_error':str(error),'decode_returncode':1}
    write_json(directory/'sample-summary.json',samples)
    analysis=analyze_pair(result['unprofiled'],result['sampled'],samples)
    analysis.update(bytes=size,duration_ms=duration,sampling_period=period,latency_threshold=threshold)
    write_json(directory/'analysis.json',analysis)
    return analysis


def acquire(root, output, adapter):
    acquisition,_=adapter.modules(root)
    sizes=sorted({c['bytes'] for c in adapter.build_cases([0]) if c['study']=='working_set'})
    trials=int(os.environ.get('PROJECT2_HIERARCHY_TRIALS','45'))
    if trials < 1: raise ValueError('PROJECT2_HIERARCHY_TRIALS must be positive')
    meta=acquisition.collect_metadata(SCOPE,trials,250,[0],os.environ.get('CC','cc'),
        os.environ.get('CFLAGS','-O3 -march=native -std=c11 -Wall -Wextra -Wpedantic'),[])
    meta.update(scope=SCOPE,hierarchy_trials=trials,rounds=math.ceil(trials/15),sizes=sizes,minimum_class_samples=MIN_SAMPLES,
        protocol=f'{trials} paired source-sampled and unsampled trials per size; fresh process; random pointer ring; CPU 0; 64-byte lines; 4 KiB pages. Extend sparse pairs from 250 to 1000 ms. Keep all validation failures; no fitted parameters.',
        continuation_policy='Complete every configuration even when quality checks fail; preserve flags and exploratory values; absent classes remain missing.',
        sampling_period=101,latency_threshold=3,benchmark_sha256=digest(root/'build/memory_bench'),
        frequency_conversion='sample core cycles -> ns using concurrent unhalted reference/core cycles and CPUID/calibrated TSC frequency; interval-average approximation',
        parameter_definition='m=unsampled DRAM counter/completed loads; h=source-counter-weighted sampled cache-hit means; p=sampled DRAM mean-h; AMAT=h+m*p')
    meta['tool_versions']=dict(perf=subprocess.check_output(['perf','--version'],text=True).strip(),
                              python=sys.version,numpy=np.__version__)
    meta['source_events']=dict(L1='cpu_core/event=0xd1,umask=0x01/',L2='cpu_core/event=0xd1,umask=0x02/',
                              L3='cpu_core/event=0xd1,umask=0x04/',DRAM='cpu_core/event=0xd3,umask=0x01/')
    acquisition.snapshot_sources(output);shutil.copy2(root/'build.mk',output/'source/build.mk')
    shutil.copy2(root/'build/memory_bench',output/'source/memory_bench')
    (output/'disassembly.txt').write_text(subprocess.check_output(['objdump','-d',str(root/'build/memory_bench')],text=True))
    write_json(output/'metadata.json',meta)
    started=time.time()
    pilots=[];rows=[];rng=random.Random(4320);durations={size:250 for size in sizes}
    try:
        for size in [16*1024,512*1024,8*2**20,192*2**20]:
            for threshold,period in [(3,101),(3,503),(4,101)]:
                for repeat in range(2):
                    relative=Path('pilots')/f'{size}-t{threshold}-p{period}-{repeat}'
                    row=acquisition_pair(root,output/relative,size,250,period,threshold,repeat%2==1)
                    row.update(repeat=repeat,evidence_directory=str(relative));pilots.append(row)
                    write_csv(output/'pilots.csv',pilots)
            print(f'Hierarchy pilots: {size/1024:g} KiB complete; quality flags retained, continuing.',flush=True)
        write_json(output/'pilot-review.json',pilot_review(pilots))
        for trial in range(trials):
            order=sizes.copy();rng.shuffle(order)
            for size in order:
                duration=durations[size];relative=Path('trials')/f'{trial:02d}-{size}'
                row=acquisition_pair(root,output/relative,size,duration,101,3,trial%2==1)
                if duration==250 and (row['hit_samples']<MIN_SAMPLES or row['DRAM_samples']<MIN_SAMPLES):
                    relative=Path('trials')/f'{trial:02d}-{size}-extended'
                    row=acquisition_pair(root,output/relative,size,1000,101,3,trial%2==1)
                    durations[size]=1000
                row.update(trial=trial,round=trial//15+1,evidence_directory=str(relative))
                rows.append(row);write_csv(output/'raw.csv',rows)
                write_json(output/'progress.json',dict(completed_pairs=len(rows),total_pairs=trials*len(sizes),trial=trial,
                    last_size=size,elapsed_seconds=time.time()-started,quality_flagged_pairs=sum(bool(r['quality_flags']) for r in rows)))
            print(f'Hierarchy acquisition: {trial+1}/{trials} blocks; {len(rows)}/{trials*len(sizes)} pairs; quality flags retained.',flush=True)
    finally:
        meta['observations']=len(rows)
        meta['raw_sha256']=digest(output/'raw.csv') if rows else None
        write_json(output/'metadata.json',meta)


def pilot_review(rows):
    result=[]
    for size in sorted({r['bytes'] for r in rows}):
        reference=[r for r in rows if r['bytes']==size and r['latency_threshold']==3 and r['sampling_period']==101]
        entry=dict(bytes=size,conditions=[])
        for threshold,period in [(3,101),(3,503),(4,101)]:
            selected=[r for r in rows if r['bytes']==size and r['latency_threshold']==threshold and r['sampling_period']==period]
            summary=dict(threshold=threshold,period=period)
            for key in ['h_ns','dram_ns','max_source_fraction_difference','profiled_time_ratio']:
                vals=[r[key] for r in selected if r.get(key) is not None]
                ref=[r[key] for r in reference if r.get(key) is not None]
                summary[key]=float(np.median(vals)) if vals else None
                if vals and ref and np.median(ref):summary[key+'_relative_to_default']=float(np.median(vals)/np.median(ref))
            entry['conditions'].append(summary)
        result.append(entry)
    return dict(note='Pilot results diagnose source bias, threshold sensitivity and perturbation; user requested full acquisition despite failed quality checks.',sizes=result)


def validate(run):
    meta=json.loads((run/'metadata.json').read_text());rows=read_csv(run/'raw.csv')
    expected={(t,size) for t in range(meta.get('hierarchy_trials',45)) for size in meta['sizes']}
    observed=[(int(r['trial']),int(r['bytes'])) for r in rows]
    structural=[]
    if len(observed)!=len(set(observed)) or set(observed)!=expected:structural.append('missing_or_duplicate_pairs')
    if digest(run/'raw.csv')!=meta['raw_sha256']:structural.append('raw_checksum_mismatch')
    flags=collections.Counter(flag for r in rows for flag in r['quality_flags'].split(';') if flag)
    write_json(run/'validation.json',dict(structural_errors=structural,quality_flags=dict(flags),pairs=len(rows),
        complete=len(observed)==len(expected) and set(observed)==expected,
        policy='Quality failures do not discard trials or terminate acquisition. Exploratory points remain labeled.'))
    if structural:raise ValueError(str(structural))


def summarize(rows):
    summaries=[]
    for size in sorted({int(r['bytes']) for r in rows}):
        group=[r for r in rows if int(r['bytes'])==size]
        item=dict(bytes=size,working_set_KiB=size/1024,trials=len(group))
        for key in ['m','h_ns','p_ns','amat_ns','measured_ns','dram_ns','L1_mean_cycles','L2_mean_cycles','L3_mean_cycles','DRAM_mean_cycles']:
            vals=[float(r[key]) for r in group if r.get(key) not in ('',None)]
            q=np.quantile(vals,[.25,.5,.75]) if vals else [None]*3
            item.update({key:q[1],key+'_q25':q[0],key+'_q75':q[2],key+'_n':len(vals)})
        for key in ['h','p','amat']:
            item[key+'_supported_trials']=sum(str(r.get(key+'_supported')).lower()=='true' for r in group)
        for key in ['hit_samples','DRAM_samples']:
            vals=[int(r[key]) for r in group];item[key+'_median']=float(np.median(vals))
        summaries.append(item)
    return summaries


def plot(run):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=read_csv(run/'raw.csv');summary=summarize(rows)
    (run/'plots').mkdir(exist_ok=True);(run/'tables').mkdir(exist_ok=True)
    write_csv(run/'tables/hierarchy-summary.csv',summary)
    write_csv(run/'tables/hierarchy-trials.csv',rows)
    x=np.array([r['working_set_KiB'] for r in summary])
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.labelsize':10,'axes.titlesize':11,
        'xtick.labelsize':9,'ytick.labelsize':9,'legend.fontsize':9,'legend.frameon':False,
        'axes.spines.top':False,'axes.spines.right':False,'svg.hashsalt':'acs-hierarchy'})
    def save_figure(fig,stem):
        for ext in ['png','svg','pdf']:
            metadata=({'Date':None} if ext=='svg' else
                      {'CreationDate':None,'ModDate':None} if ext=='pdf' else {})
            fig.savefig(run/f'plots/{stem}.{ext}',dpi=240,metadata=metadata)
    def decorate(ax):
        ax.set_xscale('log',base=2);ax.set_xlim(3.5,230000)
        ax.set_xticks([4,16,64,256,1024,4096,16384,65536,196608],['4K','16K','64K','256K','1M','4M','16M','64M','192M'])
        ax.grid(axis='y',color='#dfe3e8',linewidth=.6);ax.set_axisbelow(True)
        for size,label in [(48,'L1'),(1280,'L2'),(24576,'L3')]:
            ax.axvline(size,color='#888',ls=':',lw=.8)
            ax.text(size,1.01,label,ha='center',va='bottom',transform=ax.get_xaxis_transform(),fontsize=8,color='#666')
    def curve(ax,key,color,label,support=None):
        def vals(suffix=''):
            return np.array([np.nan if r[key+suffix] is None else r[key+suffix] for r in summary],float)
        y=vals();ax.plot(x,y,color=color,lw=1.3,label=label)
        ax.fill_between(x,vals('_q25'),vals('_q75'),color=color,alpha=.18)
        valid=np.isfinite(y)
        solid=np.array([r[support]>=math.ceil(.8*r['trials']) for r in summary]) if support else np.ones(len(x),dtype=bool)
        ax.scatter(x[valid&solid],y[valid&solid],s=18,color=color,zorder=3)
        ax.scatter(x[valid&~solid],y[valid&~solid],s=22,facecolors='white',edgecolors=color,zorder=3)
        return int(valid.sum())
    fig,axs=plt.subplots(3,1,figsize=(7.2,7.4),sharex=True,layout='constrained')
    for ax,key,color,label,ylabel,support in [
        (axs[0],'m','#477d62','DRAM-served reads / completed reads','Miss fraction m',None),
        (axs[1],'h_ns','#24649a','Effective cache-hit latency','Hit time h (ns)','h_supported_trials'),
        (axs[2],'p_ns','#bb6c16','DRAM latency − cache-hit latency','Extra miss cost p (ns)','p_supported_trials')]:
        count=curve(ax,key,color,label,support);decorate(ax);ax.set_ylabel(ylabel);ax.legend(loc='upper left')
        if not count:ax.text(.5,.5,'No source-resolved observations',transform=ax.transAxes,ha='center')
    axs[0].set_ylim(-.03,1.08);axs[2].set_xlabel('Working-set size (K = KiB; M = MiB)')
    fig.suptitle('Figure 6a. Measured full-hierarchy AMAT parameters',fontsize=12)
    fig.get_layout_engine().set(rect=(0,.055,1,.92))
    fig.text(.5,.012,'Bands: trial IQR. Open markers: exploratory. Gaps: no measurable class.\nh is the changing mix of L1/L2/L3 hits; p is an observed difference, not a fitted constant.',ha='center',fontsize=8)
    save_figure(fig,'fig6a-parameters')
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(7.2,4.6),layout='constrained')
    curve(ax,'measured_ns','#24649a','Independently timed access time')
    curve(ax,'amat_ns','#bb6c16','Reconstructed h + mp','amat_supported_trials');decorate(ax)
    ax.set(xlabel='Working-set size (K = KiB; M = MiB)',ylabel='Average time per read (ns)')
    fig.suptitle('Figure 6b. Full-hierarchy AMAT and timed access',fontsize=12)
    ax.legend(loc='upper left');fig.get_layout_engine().set(rect=(0,.10,1,.87))
    fig.text(.5,.015,'Bands: trial IQR. Open markers: exploratory; absent hit/miss classes leave gaps.\nHardware-sampled effective load latency and timed loop latency have different measurement envelopes.',ha='center',fontsize=8)
    save_figure(fig,'fig6b-amat')
    plt.close(fig)
    trial_counts=sorted({r['trials'] for r in summary})
    trial_label=str(trial_counts[0]) if len(trial_counts)==1 else f'{min(trial_counts)}–{max(trial_counts)}'
    captions=(f'Figure 6a. Full-hierarchy parameters versus working-set size. m is processor-specific local-DRAM read events per completed benchmark load from the unsampled trial. h weights the sampled mean L1/L2/L3 load latencies by matched unsampled source counts; p is the sampled DRAM mean minus h. Each point summarizes per-trial arithmetic means using the median and IQR across {trial_label} trials. Timings are effective dispatch-to-completion latencies, including pipeline effects, converted using concurrent reference/core-cycle counts. Hollow markers indicate fewer than 80% of trials meet all support checks, including 1,000 observations per required class. Missing classes are not imputed.\n\n'
        'Figure 6b. AMAT reconstructed as h + mp from each paired trial, compared with independently timed pointer-chain access. Bands show trial IQR, not confidence intervals. This is a measured-component reconstruction, not a fitted predictive model. Hardware samples and whole-loop timing have distinct measurement envelopes; disagreement is retained. Vertical lines mark nominal L1 (48 KiB), L2 (1.25 MiB), and L3 (24 MiB) capacities.\n')
    (run/'captions.txt').write_text(captions)
    write_json(run/'figure-manifest.json',dict(scope=SCOPE,raw_sha256=digest(run/'raw.csv'),
        summary_sha256=digest(run/'tables/hierarchy-summary.csv'),figures=['plots/fig6a-parameters.png','plots/fig6b-amat.png'],
        status='review drafts; no Google Doc changes',missing_policy='No fitting, constants, or interpolation; exploratory measured values retained with flags.'))
