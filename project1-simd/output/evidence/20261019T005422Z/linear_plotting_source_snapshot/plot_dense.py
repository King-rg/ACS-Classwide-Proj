#!/usr/bin/env python3
"""Render local high-resolution line charts from one complete, dense measured run."""
import argparse,csv,hashlib,json,math,statistics
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import LogLocator
import numpy as np
import analyze_evidence as analysis

COLORS=analysis.COLORS
MARKERS=analysis.MARKERS
LABELS={'scalar':'Optimized scalar','auto':'Compiler auto-vectorized','simd':'Explicit AVX2 intrinsics'}
TITLES={'axpy':'AXPY','dot':'Dot product','multiply':'Elementwise multiply'}
CACHE=[(48*1024,'L1D 48 KiB'),(1280*1024,'L2 1.25 MiB'),(24*1024**2,'LLC 24 MiB')]


def checked_points(rows,summary,comparisons,manifest):
    """Confirm every plotted configuration has all raw observations and variants."""
    runtime=analysis.collapse_repeats(summary,'median_ns',analysis.CONFIG+['implementation'])
    speedup=analysis.collapse_repeats(comparisons,'speedup',analysis.CONFIG+['implementation'])
    repeats=manifest['repeats'];expected_points=len(manifest['target_footprints_kib'])
    if manifest.get('sweep')!='dense':raise ValueError('Use a complete --sweep dense run')
    if repeats!=3:raise ValueError('These charts require three completed process repeats')
    if any(r['study']!='working_set' for r in rows):raise ValueError('Mixed studies are not pooled')
    for kernel in TITLES:
        for dtype in ['float','double']:
            for impl in analysis.IMPLEMENTATIONS:
                actual=[p for p in runtime if p['kernel']==kernel and p['datatype']==dtype and p['implementation']==impl]
                if len(actual)!=expected_points or len({p['footprint_bytes'] for p in actual})!=expected_points:
                    raise ValueError('Missing/duplicate measured point in a series')
    if any(p['repeat_count']!=repeats for p in runtime+speedup):raise ValueError('Incomplete process repeat coverage')
    # Count raw records using every configuration field, not just N or kernel.
    raw_counts={}
    for row in rows:
        key=tuple(row[k] for k in analysis.CONFIG+['implementation'])
        raw_counts[key]=raw_counts.get(key,0)+1
    plotted=[]
    for metric,points in [('runtime_ns',runtime),('speedup',speedup)]:
        for point in points:
            key=tuple(point[k] for k in analysis.CONFIG+['implementation'])
            if raw_counts[key]!=5*repeats:raise ValueError('Plotted point lacks 15 validated observations')
            baseline_key=tuple(point[k] for k in analysis.CONFIG)+('scalar',)
            if raw_counts[baseline_key]!=5*repeats:raise ValueError('Missing scalar baseline')
            if point['low']<=0 or not point['low']<=point['median']<=point['high']:
                raise ValueError('Invalid plotted median/range')
            record={k:point[k] for k in analysis.CONFIG+['implementation']}
            record.update(metric=metric,median=point['median'],low=point['low'],high=point['high'],
                          process_repeats=repeats,raw_observations=raw_counts[key],
                          scalar_observations=raw_counts[baseline_key] if metric=='speedup' else '')
            plotted.append(record)
    return runtime,speedup,plotted


def x_ticks():
    return [16*1024,48*1024,256*1024,1280*1024,8*1024**2,24*1024**2,96*1024**2],\
           ['16 KiB','48 KiB','256 KiB','1.25 MiB','8 MiB','24 MiB','96 MiB']


def draw_curve(ax,points,impl,scale,xscale=1):
    points=sorted([p for p in points if p['implementation']==impl],key=lambda p:int(p['footprint_bytes']))
    x=np.array([int(p['footprint_bytes']) for p in points])*xscale
    median=np.array([p['median'] for p in points])*scale
    low=np.array([p['low'] for p in points])*scale
    high=np.array([p['high'] for p in points])*scale
    ax.fill_between(x,low,high,color=COLORS[impl],alpha=.12,linewidth=0)
    ax.plot(x,median,color=COLORS[impl],marker=MARKERS[impl],markersize=4.0,
            linewidth=1.7,markeredgewidth=.6,label=LABELS[impl])


def make_chart(points,kind,out,manifest,linear=False):
    fig,axes=plt.subplots(3,2,figsize=(18,13.5),sharex=True,sharey='row')
    scale=(1e-6 if linear else 0.001) if kind=='runtime' else 1
    for row,kernel in enumerate(TITLES):
        for col,dtype in enumerate(['float','double']):
            ax=axes[row,col]
            selected=[p for p in points if p['kernel']==kernel and p['datatype']==dtype]
            for impl in analysis.IMPLEMENTATIONS:
                if kind=='runtime' or impl!='scalar':draw_curve(ax,selected,impl,scale,1/1024**2 if linear else 1)
            if kind=='speedup':
                ax.axhline(1,color=COLORS['scalar'],linestyle='--',linewidth=1.1,zorder=1)
            if not linear:ax.set_xscale('log',base=2)
            if linear:
                ax.set_xscale('linear');ax.set_yscale('linear')
                ax.set_ylim(0,max(p['high'] for p in points if p['kernel']==kernel)*scale*1.08)
            elif kind=='runtime':ax.set_yscale('log');ax.yaxis.set_major_locator(LogLocator(numticks=6))
            else:
                row_points=[p for p in points if p['kernel']==kernel]
                ax.set_ylim(0,max(p['high'] for p in row_points)*1.14)
            for size,label in CACHE:
                position=size/1024**2 if linear else size
                ax.axvline(position,color='#87939b',linestyle=':',linewidth=.9,zorder=0)
                if linear and size<24*1024**2: continue  # Labels would overlap near zero.
                ax.text(position,.98,label,transform=ax.get_xaxis_transform(),ha='center',va='top',
                        fontsize=9,color='#485963',bbox={'facecolor':'white','edgecolor':'none','alpha':.85,'pad':1})
            ax.set_title(f"{TITLES[kernel]} · {'float32' if dtype=='float' else 'float64'}",fontsize=14,pad=12)
            if linear:
                ax.set_xlim(0,100);ax.set_xticks([0,16,32,48,64,80,96])
            else:
                ax.set_xlim(11*1024,108*1024**2)
                ticks,labels=x_ticks();ax.set_xticks(ticks,labels)
            ax.tick_params(labelbottom=True,labelsize=10)
            ax.grid(True,color='#e2e7eb',linewidth=.7);ax.set_axisbelow(True);ax.spines[['top','right']].set_visible(False)
            if col==0:ax.set_ylabel(('Kernel time (ms per call)' if linear else 'Kernel time (µs per call; log scale)') if kind=='runtime' else 'Scalar / variant time (×)',fontsize=12)
    handles=[Line2D([],[],color=COLORS[i],marker=MARKERS[i] if kind=='runtime' or i!='scalar' else None,
                    linestyle='--' if kind=='speedup' and i=='scalar' else '-',linewidth=1.7,label=LABELS[i]+(' · 1× baseline' if kind=='speedup' and i=='scalar' else '')) for i in analysis.IMPLEMENTATIONS]
    count=len(manifest['target_footprints_kib'])
    fig.suptitle('Measured working-set speedup' if kind=='speedup' else 'Measured working-set runtime',
                 x=.065,y=.987,ha='left',fontsize=23,fontweight='bold',color='#18384b')
    fig.text(.065,.957,f'{count} measured sizes per series · 3 kernels × 2 data types · CPU {manifest["cpu"]} pinned · fresh run {manifest["run_id"]}',fontsize=12,color='#485963')
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.51,.939),ncol=3,frameon=False,fontsize=12)
    fig.supxlabel('Total active working set across kernel arrays (MiB; linear scale)' if linear else 'Total active working set across kernel arrays (log₂ scale)',y=.071,fontsize=13)
    fig.text(.065,.041,'Markers are actual measurements. Lines connect them; no synthetic or smoothed data points. Shading spans three process-median results (not a confidence interval).',fontsize=10,color='#485963')
    fig.text(.065,.024,'Each implementation/size has 3 process repeats × 5 validated trials. AVX2, relaxed finite-input FP; frequency/SMT not isolated. Dotted cache capacities do not prove residency.',fontsize=10,color='#485963')
    fig.subplots_adjust(left=.075,right=.975,bottom=.12,top=.89,hspace=.35,wspace=.12)
    path=out/(f'working_set_{kind}_highres'+('_linear' if linear else ''))
    if linear:
        axes_info=[dict(xscale=ax.get_xscale(),yscale=ax.get_yscale(),xlim=list(ax.get_xlim()),ylim=list(ax.get_ylim())) for ax in axes.flat]
        assert all(a['xscale']==a['yscale']=='linear' and a['xlim'][0]==a['ylim'][0]==0 for a in axes_info)
        (out/'runtime_linear_validation.json').write_text(json.dumps(dict(axes=axes_info,points=len(points),x_unit='MiB',y_unit='ms per call',source='Same validated dense measurements; no new experiments'),indent=2)+'\n')
    fig.savefig(path.with_suffix('.png'),dpi=300)
    fig.savefig(path.with_suffix('.svg'))
    fig.savefig(path.with_suffix('.pdf'))
    plt.close(fig)
    return path


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);parser.add_argument('--linear-runtime',action='store_true');args=parser.parse_args()
    rows,manifest=analysis.read_raw(args.directory)
    summary=analysis.summaries(rows);comparisons=analysis.compare(summary)
    runtime,speedup,plotted=checked_points(rows,summary,comparisons,manifest)
    out=args.directory/'highres'
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none','pdf.fonttype':42})
    if args.linear_runtime:
        if not out.is_dir():raise ValueError('Render the original dense charts first')
        print(make_chart(runtime,'runtime',out,manifest,linear=True))
        return
    out.mkdir(exist_ok=False)
    analysis.write_csv(out/'per_repeat_summary.csv',summary)
    analysis.write_csv(out/'per_repeat_speedups.csv',comparisons)
    analysis.write_csv(out/'plotted_points.csv',plotted)
    analysis.write_csv(args.directory/'all_trials.csv',rows)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none','pdf.fonttype':42})
    paths=[make_chart(speedup,'speedup',out,manifest),make_chart(runtime,'runtime',out,manifest)]
    validation=dict(run_id=manifest['run_id'],source_id=manifest['source_id'],raw_rows=len(rows),
                    measured_footprints_per_series=len(manifest['target_footprints_kib']),
                    runtime_series=18,runtime_points=len(runtime),speedup_series=12,speedup_points=len(speedup),
                    raw_trials_per_variant_point=15,process_repeats=3,trials_per_process=5,
                    png_dimensions=[5400,4050],png_dpi=300,formats=['PNG','SVG','PDF'],
                    interpolation='none; straight lines connect actual measurements',
                    group_policy='Exact config/calls matched within processes; ratios summarized across 3 process medians. No old runs pooled.',
                    source_csv_sha256={f'repeat-{i}/raw.csv':hashlib.sha256((args.directory/f'repeat-{i}/raw.csv').read_bytes()).hexdigest() for i in range(3)})
    (out/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    print(json.dumps(validation,indent=2));print('Charts:',*[str(p) for p in paths],sep='\n')
if __name__=='__main__':main()
