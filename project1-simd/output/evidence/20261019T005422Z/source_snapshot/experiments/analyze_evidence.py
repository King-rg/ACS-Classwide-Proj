#!/usr/bin/env python3
"""Analyze versioned batched scalar/auto/AVX2 experiments, keeping process repeats distinct."""
import argparse,csv,json,math,statistics
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image,ImageDraw

IMPLEMENTATIONS=('scalar','auto','simd')
COLORS={'scalar':'#24649a','auto':'#bf7d14','simd':'#9c3b67'}
MARKERS={'scalar':'o','auto':'^','simd':'s'}
KEYS='run_id repeat study kernel datatype implementation n stride offset_elements x_mod64 y_mod64 output_mod64 footprint_bytes coefficient warmups calls seed'.split()
COMPARE=[k for k in KEYS if k!='implementation']
CONFIG=[k for k in COMPARE if k not in {'repeat','calls'}]
OPS={'axpy':2,'dot':2,'multiply':1}

def read_raw(directory):
    manifest=json.loads((directory/'manifest.json').read_text())
    rows=[]
    for repeat in range(manifest['repeats']):
        with (directory/f'repeat-{repeat}/raw.csv').open() as f:
            rows.extend(csv.DictReader(f))
    if len(rows)!=manifest['expected_rows']: raise ValueError('Incomplete raw row count')
    seen=set()
    for row in rows:
        if row['implementation'] not in IMPLEMENTATIONS or row['correct']!='pass': raise ValueError('Invalid variant/status')
        for key in ['n','calls','stride','footprint_bytes','elapsed_ns','tsc_ticks','core_cycles','user_instructions','perf_enabled_ns','perf_running_ns']:
            value=float(row[key])
            if not math.isfinite(value) or value<=0: raise ValueError(f'Invalid {key}')
        if row['cpu_start']!=row['cpu_end'] or int(row['cpu_start'])!=manifest['cpu'] or row['aux_start']!=row['aux_end']: raise ValueError('Migration')
        # These perf timing fields accumulate while each group exists. Exact equality
        # proves no multiplexed interval within the group's entire recorded lifetime.
        if row['perf_running_ns']!=row['perf_enabled_ns']: raise ValueError('Multiplexed counts require region-specific scaling')
        for key in ['checksum','max_abs_error','khz_start','khz_end','llc_misses']:
            if not math.isfinite(float(row[key])): raise ValueError(f'Invalid {key}')
        unique=tuple(row[k] for k in KEYS+['trial'])
        if unique in seen: raise ValueError('Duplicate raw trial')
        seen.add(unique)
    return rows,manifest

def write_csv(path,rows):
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def summaries(rows):
    groups=defaultdict(list)
    for row in rows: groups[tuple(row[k] for k in KEYS)].append(row)
    result=[]
    for key,group in groups.items():
        if len(group)!=5 or {int(r['trial']) for r in group}!={0,1,2,3,4}: raise ValueError('Expected five trials/config/repeat')
        fields=dict(zip(KEYS,key));n=int(fields['n']);calls=int(fields['calls'])
        ns=[float(r['elapsed_ns'])/calls for r in group]
        cycles=[float(r['core_cycles'])/calls/n for r in group]
        ticks=[float(r['tsc_ticks'])/calls/n for r in group]
        median=statistics.median(ns);bytes_per_element=(3 if fields['kernel'] in ['axpy','multiply'] else 2)*(4 if fields['datatype']=='float' else 8)
        result.append(dict(fields,trial_count=len(group),median_ns=median,min_ns=min(ns),max_ns=max(ns),
                           median_core_cycles_per_element=statistics.median(cycles),
                           median_tsc_ticks_per_element=statistics.median(ticks),
                           median_instructions_per_element=statistics.median(float(r['user_instructions'])/calls/n for r in group),
                           median_llc_misses_per_1000_elements=statistics.median(float(r['llc_misses'])*1000/calls/n for r in group),
                           gflops=OPS[fields['kernel']]*n/median,
                           logical_gb_s=bytes_per_element*n/median,
                           max_abs_error=max(float(r['max_abs_error']) for r in group),
                           min_sample_khz=min(float(r['khz_start']) for r in group),
                           max_sample_khz=max(float(r['khz_end']) for r in group)))
    return result

def compare(summary):
    groups=defaultdict(dict)
    for row in summary: groups[tuple(row[k] for k in COMPARE)][row['implementation']]=row
    result=[]
    for key,members in groups.items():
        if set(members)!=set(IMPLEMENTATIONS): raise ValueError('Missing exact variant/call-count match')
        fields=dict(zip(COMPARE,key));scalar=members['scalar']
        for impl in ['auto','simd']:
            row=members[impl]
            result.append(dict(fields,implementation=impl,speedup=scalar['median_ns']/row['median_ns'],
                               trial_range_low=scalar['min_ns']/row['max_ns'],trial_range_high=scalar['max_ns']/row['min_ns']))
    return result

def collapse_repeats(rows,value,identity):
    groups=defaultdict(list)
    for row in rows: groups[tuple(row[k] for k in identity)].append(row)
    result=[]
    for key,members in groups.items():
        repeats={r['repeat'] for r in members}
        if len(members)!=len(repeats): raise ValueError('Mixed configuration within repeat')
        vals=[float(r[value]) for r in members]
        result.append(dict(zip(identity,key),median=statistics.median(vals),low=min(vals),high=max(vals),repeat_count=len(vals)))
    return result

def setup_axes(ax,xlabel,ylabel):
    ax.set_xlabel(xlabel);ax.set_ylabel(ylabel);ax.grid(color='#e1e5e8');ax.spines[['top','right']].set_visible(False)

def finish(fig,path,title,note):
    fig.suptitle(title,x=.07,ha='left',fontsize=17,y=.99,fontweight='bold')
    fig.text(.07,.025,note,fontsize=9,color='#485963')
    fig.tight_layout(rect=(.02,.09,.99,.90));fig.savefig(path.with_suffix('.png'),dpi=160);fig.savefig(path.with_suffix('.svg'));plt.close(fig)

def error_series(ax,rows,impl,xkey,scale=1):
    points=sorted([r for r in rows if r['implementation']==impl],key=lambda r:float(r[xkey]))
    if not points:return
    x=[float(r[xkey])*scale for r in points];y=[r['median'] for r in points]
    ax.errorbar(x,y,yerr=[[r['median']-r['low'] for r in points],[r['high']-r['median'] for r in points]],
                label=impl,color=COLORS[impl],marker=MARKERS[impl],capsize=3,linewidth=1.5)

def working_plots(summary,speedups,out):
    idkeys=CONFIG+['implementation']
    paths=[]
    for kernel in OPS:
        for value,label,source in [('median_ns','Runtime (ns per call)',summary),('median_llc_misses_per_1000_elements','LLC-miss events / 1000 elements',summary),('gflops','GFLOP/s',summary),('median_core_cycles_per_element','User core cycles / element',summary),('speedup','Scalar / variant median time (×)',speedups)]:
            rows=[r for r in source if r['study']=='working_set' and r['kernel']==kernel]
            grouped=collapse_repeats(rows,value,idkeys)
            fig,axes=plt.subplots(1,2,figsize=(12,5.5),sharey=True)
            for ax,dtype in zip(axes,['float','double']):
                chosen=[r for r in grouped if r['datatype']==dtype]
                for impl in IMPLEMENTATIONS:error_series(ax,chosen,impl,'footprint_bytes',1/1024)
                for size,name in [(48,'L1D'),(1280,'L2'),(24576,'LLC')]:
                    ax.axvline(size,color='#89949c',linestyle=':',linewidth=.8)
                    ax.text(size,.98,name,transform=ax.get_xaxis_transform(),rotation=90,va='top',ha='right',fontsize=8)
                if value=='speedup':ax.axhline(1,color='#485963',linestyle='--',linewidth=1)
                ax.set_xscale('log',base=2);ax.set_title(dtype);ax.legend(frameon=False)
                if value not in ['speedup','median_llc_misses_per_1000_elements']:ax.set_yscale('log')
                if value=='median_llc_misses_per_1000_elements':ax.set_ylim(0,max(r['high'] for r in grouped)*1.08+0.001)
                setup_axes(ax,'Active physical footprint (KiB, all kernel arrays)',label)
            path=out/f'{kernel}_working_{value}';finish(fig,path,f'{kernel.upper()}: working-set sweep',
              'Median of process medians; whiskers span process medians (5 trials/process). CPU 0; variable DVFS, SMT not isolated.\n'
              'Dotted capacities are topology references, not proof of residency. Hardware cycle counts exclude kernel/hypervisor, include batch-wrapper overhead.')
            paths.append(path.with_suffix('.png'))
    return paths

def alignment_plots(summary,out):
    paths=[]
    for kernel in OPS:
        chosen=[dict(r,ns_per_element=r['median_ns']/int(r['n'])) for r in summary if r['kernel']==kernel and r['study']=='alignment_tail']
        grouped=collapse_repeats(chosen,'ns_per_element',CONFIG+['implementation'])
        fig,axes=plt.subplots(2,2,figsize=(12,8),sharey=True)
        for i,dtype in enumerate(['float','double']):
            for j,offset in enumerate(['0','1']):
                ax=axes[i,j];rows=[dict(r,tail=int(r['n'])-4096) for r in grouped if r['datatype']==dtype and r['offset_elements']==offset]
                for impl in IMPLEMENTATIONS:error_series(ax,rows,impl,'tail')
                ax.set_title(f'{dtype} · offset {offset} element(s)');ax.legend(frameon=False);ax.set_xticks([0,1,3,7])
                setup_axes(ax,'Extra elements beyond N=4096','ns / element')
        path=out/f'{kernel}_alignment_tails';finish(fig,path,f'{kernel.upper()}: controlled alignment and tails',
            'Allocation bases are 64-byte aligned; offset 1 shifts every participating pointer by one element. N=4096 is vector-multiple.\n'
            'Median and range of process medians; no arbitrary-alignment pooling. The same repeated-update AXPY batch policy applies.')
        paths.append(path.with_suffix('.png'))
    return paths

def stride_plots(summary,out):
    paths=[]
    for kernel in OPS:
        rows=[r for r in summary if r['kernel']==kernel and r['study']=='stride']
        grouped=collapse_repeats(rows,'logical_gb_s',CONFIG+['implementation'])
        fig,axes=plt.subplots(2,2,figsize=(12,8),sharey='row')
        footprints=['cache','streaming']
        for i,dtype in enumerate(['float','double']):
            for j,footprint in enumerate(footprints):
                ax=axes[i,j];selected=[r for r in grouped if r['datatype']==dtype and ('cache' if int(r['footprint_bytes'])<1024**2 else 'streaming')==footprint]
                for impl in IMPLEMENTATIONS:error_series(ax,selected,impl,'stride')
                ax.set_title(f"{dtype} · {'~0.25' if footprint=='cache' else '96'} MiB physical footprint");ax.legend(frameon=False);ax.set_xticks([1,2,4,8])
                setup_axes(ax,'Stride (elements)','Useful algorithmic GB/s')
        path=out/f'{kernel}_stride';finish(fig,path,f'{kernel.upper()}: unit and non-unit stride',
            'Physical footprint held approximately constant; logical N decreases as stride grows. Useful bytes count touched elements, not full cache lines.\n'
            'Not measured DRAM-controller bandwidth. Median/range of process medians. AVX2 gather plus scalar scatter for strided outputs.')
        paths.append(path.with_suffix('.png'))
    return paths

def calibration_summary(directory,manifest):
    rows=[]
    for repeat in range(manifest['repeats']):
        with (directory/f'repeat-{repeat}/calibration.csv').open() as f:
            for r in csv.DictReader(f):
                r['repeat']=str(repeat);r['rate']=float(r['work'])/float(r['elapsed_ns']);rows.append(r)
    result=[]
    for kind in ['nt_triad','cached_copy','fma_f32','fma_f64']:
        selected=[r for r in rows if r['kind']==kind];medians=[]
        for repeat in range(manifest['repeats']):
            vals=[r['rate'] for r in selected if int(r['repeat'])==repeat]
            if len(vals)!=7:raise ValueError('Calibration trial count')
            medians.append(statistics.median(vals))
        result.append(dict(kind=kind,median_rate=statistics.median(medians),min_process_median=min(medians),max_process_median=max(medians),
                           unit='GFLOP/s' if kind.startswith('fma') else 'logical GB/s',trial_count=len(selected)))
    return result

def roofline(summary,calibration,out):
    references={r['kind']:r['median_rate'] for r in calibration};bandwidth=references['nt_triad']
    fig,axes=plt.subplots(1,2,figsize=(12,5.6))
    rows=[r for r in summary if r['study']=='working_set' and int(r['footprint_bytes'])>=95*1024**2]
    grouped=collapse_repeats(rows,'gflops',CONFIG+['implementation'])
    for ax,dtype,empirical,theoretical in zip(axes,['float','double'],['fma_f32','fma_f64'],[166.4,83.2]):
        intensity=np.logspace(-2,2,200);peak=references[empirical]
        ax.plot(intensity,np.minimum(bandwidth*intensity,peak),color='#485963',label='Independent NT-triad + empirical FMA reference')
        ax.plot(intensity,np.minimum(bandwidth*intensity,theoretical),color='#89949c',linestyle='--',label='Architectural/max-turbo upper estimate')
        for kernel in OPS:
            points=[r for r in grouped if r['datatype']==dtype and r['kernel']==kernel and r['implementation']=='auto']
            if len(points)!=1:raise ValueError('Roofline configuration count')
            r=points[0];bytes_per=(3 if kernel!='dot' else 2)*(4 if dtype=='float' else 8)
            ai=OPS[kernel]/bytes_per
            ax.errorbar(ai,r['median'],yerr=[[r['median']-r['low']],[r['high']-r['median']]],fmt='o',color='#24649a',capsize=3)
            ax.annotate(kernel,(ai,r['median']),xytext=(5,6),textcoords='offset points',fontsize=9)
        ax.set_xscale('log');ax.set_yscale('log');ax.set_title(dtype);ax.legend(fontsize=7,frameon=False)
        setup_axes(ax,'Algorithmic FLOP / useful byte','GFLOP/s')
    path=out/'roofline_references';finish(fig,path,'Roofline interpretation: measured streaming/compute references',
        f'Auto variants, ~96 MiB footprint; 2-read/1-write NT-triad reference {bandwidth:.2f} logical GB/s. Points: process-median ranges.\n'
        'NT stores avoid RFO; assignment cached stores/read-only dot have different traffic. These are modeled references, not measured DRAM roofs.')
    return path.with_suffix('.png')

def gallery(paths,out):
    width=1400;cell_height=440;sheet=Image.new('RGB',(width,math.ceil(len(paths)/2)*cell_height),'#e7edf0')
    for i,p in enumerate(paths):
        im=Image.open(p).convert('RGB');im.thumbnail((680,405));x=i%2*700;y=i//2*cell_height
        sheet.paste(im,(x,y));ImageDraw.Draw(sheet).text((x+8,y+410),p.name,fill='black')
    sheet.save(out/'gallery.png')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);args=parser.parse_args()
    rows,manifest=read_raw(args.directory);summary=summaries(rows);comparisons=compare(summary)
    out=args.directory/'analysis';out.mkdir(exist_ok=False)
    write_csv(out/'per_repeat_summary.csv',summary);write_csv(out/'per_repeat_speedups.csv',comparisons)
    calibration=calibration_summary(args.directory,manifest);write_csv(out/'calibration_summary.csv',calibration)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none','axes.axisbelow':True})
    paths=working_plots(summary,comparisons,out)+alignment_plots(summary,out)+stride_plots(summary,out)
    paths.append(roofline(summary,calibration,out));gallery(paths,out)
    evidence=dict(raw_rows=len(rows),groups=len(summary),comparisons=len(comparisons),calibration=calibration,
                  core_cycles_available=True,perf_running_equals_enabled=True,process_repeats=manifest['repeats'],plots=len(paths))
    (out/'validation.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence,indent=2))
if __name__=='__main__':main()
