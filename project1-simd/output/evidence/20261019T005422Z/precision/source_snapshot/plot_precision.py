#!/usr/bin/env python3
"""Direct float32/float64 line comparisons from the same validated dense run."""
import argparse,csv,hashlib,json,math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import analyze_evidence as analysis
import plot_dense

TYPES={'float':('float32','#24649a','o','-'),'double':('float64','#c76b14','s','--')}
IMPLEMENTATIONS={'scalar':'Optimized scalar','auto':'Compiler auto-vectorized','simd':'Explicit AVX2 intrinsics'}
KERNELS={'axpy':'AXPY','dot':'Dot product','multiply':'Elementwise multiply'}


def precision_points(rows,summary,manifest):
    runtime,_,_=plot_dense.checked_points(rows,summary,analysis.compare(summary),manifest)
    points=[]
    for kernel in KERNELS:
        arrays=3 if kernel=='multiply' else 2
        for implementation in IMPLEMENTATIONS:
            for datatype,width in [('float',4),('double',8)]:
                selected=sorted([p for p in runtime if p['kernel']==kernel and p['implementation']==implementation and p['datatype']==datatype],key=lambda p:int(p['footprint_bytes']))
                for target,point in zip(manifest['target_footprints_kib'],selected):
                    n=int(point['n']);physical=int(point['footprint_bytes'])
                    if n!=target*1024//(arrays*width)//8*8 or physical!=n*arrays*width:
                        raise ValueError('Footprint/element count does not match measured case grid')
                    if point['stride']!='1' or point['offset_elements']!='0':raise ValueError('Unexpected access pattern')
                    points.append(dict(point,nominal_footprint_bytes=target*1024,
                                       median_ns_per_element=point['median']/n,
                                       low_ns_per_element=point['low']/n,
                                       high_ns_per_element=point['high']/n))
    if len(points)!=612:raise ValueError('Expected 18 measured curves with 34 points each')
    return points


def validate_independently(points,rows):
    # Recompute from raw durations without using aggregation helpers or saved summaries.
    keys=analysis.CONFIG+['implementation']
    groups={}
    for row in rows:
        key=tuple(row[k] for k in keys)
        groups.setdefault(key,{}).setdefault(row['repeat'],[]).append(row)
    for point in points:
        group=groups[tuple(point[k] for k in keys)]
        if set(group)!={'0','1','2'}:raise ValueError('Missing repeats')
        values=[]
        for trial_rows in group.values():
            if len(trial_rows)!=5:raise ValueError('Missing trials')
            per_element=sorted(float(r['elapsed_ns'])/int(r['calls'])/int(r['n']) for r in trial_rows)
            values.append(per_element[2])
        for key,expected in [('median_ns_per_element',sorted(values)[1]),('low_ns_per_element',min(values)),('high_ns_per_element',max(values))]:
            if not math.isclose(point[key],expected,rel_tol=1e-12,abs_tol=1e-12):raise ValueError('Raw-to-point normalization mismatch')


def draw(points,out,manifest):
    fig,axes=plt.subplots(3,3,figsize=(18,13.5),sharex=True,sharey='row')
    for i,kernel in enumerate(KERNELS):
        maximum=max(p['high_ns_per_element'] for p in points if p['kernel']==kernel)*1.1
        for j,implementation in enumerate(IMPLEMENTATIONS):
            ax=axes[i,j]
            for datatype,(label,color,marker,linestyle) in TYPES.items():
                selected=sorted([p for p in points if p['kernel']==kernel and p['implementation']==implementation and p['datatype']==datatype],key=lambda p:int(p['footprint_bytes']))
                x=np.array([int(p['footprint_bytes'])/1024**2 for p in selected])
                median=np.array([p['median_ns_per_element'] for p in selected])
                low=np.array([p['low_ns_per_element'] for p in selected]);high=np.array([p['high_ns_per_element'] for p in selected])
                ax.fill_between(x,low,high,color=color,alpha=.12,linewidth=0)
                ax.plot(x,median,color=color,marker=marker,linestyle=linestyle,markersize=3.5,linewidth=1.7,label=label)
            for size in [48/1024,1.25,24]:ax.axvline(size,color='#87939b',linestyle=':',linewidth=.8,zorder=0)
            ax.text(24,.98,'LLC 24 MiB',transform=ax.get_xaxis_transform(),va='top',ha='center',fontsize=8,color='#485963',bbox={'facecolor':'white','edgecolor':'none','alpha':.8,'pad':1})
            ax.set_title(f'{KERNELS[kernel]}\n{IMPLEMENTATIONS[implementation]}',fontsize=13,pad=10)
            ax.set_xscale('linear');ax.set_yscale('linear');ax.set_xlim(0,100);ax.set_ylim(0,maximum)
            ax.set_xticks([0,24,48,72,96]);ax.tick_params(labelbottom=True,labelsize=10)
            ax.grid(color='#e2e7eb',linewidth=.7);ax.set_axisbelow(True);ax.spines[['top','right']].set_visible(False)
            if j==0:ax.set_ylabel('ns per processed element · lower is faster',fontsize=11)
    fig.suptitle('Float32 vs float64: time per processed element',x=.065,y=.987,ha='left',fontsize=23,fontweight='bold',color='#18384b')
    fig.text(.065,.957,'Shared axes within each panel · 34 measured working-set sizes per curve · same dense run '+manifest['run_id'],fontsize=12,color='#485963')
    handles=[Line2D([],[],color=spec[1],marker=spec[2],linestyle=spec[3],linewidth=1.7,label=spec[0]) for spec in TYPES.values()]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.52,.937),ncol=2,frameon=False,fontsize=13)
    fig.supxlabel('Total active working set across kernel arrays (MiB; linear scale)',y=.074,fontsize=13)
    fig.text(.065,.047,'Same nominal byte footprint, NOT equal N: float32 processes about twice as many elements. Actual byte footprints may differ by up to 96 bytes due to vector rounding.',fontsize=9.5,color='#485963')
    fig.text(.065,.030,'Lines/markers: median of 3 process medians; shading: their observed range (not a CI). Every point uses 15 validated raw trials. No new measurements or interpolation.',fontsize=9.5,color='#485963')
    fig.text(.065,.013,'CPU 0 pinned; same AVX2 / relaxed finite-input FP policy, stride 1 and aligned starts. DVFS/SMT not isolated. L1D/L2 marks cluster near zero; cache marks do not prove residency.',fontsize=9.5,color='#485963')
    fig.subplots_adjust(left=.075,right=.975,bottom=.125,top=.875,hspace=.43,wspace=.14)
    path=out/'float32_vs_float64_ns_per_element_linear'
    scales=[dict(x=a.get_xscale(),y=a.get_yscale(),xmin=a.get_xlim()[0],ymin=a.get_ylim()[0]) for a in axes.flat]
    if not all(a==dict(x='linear',y='linear',xmin=0,ymin=0) for a in scales):raise ValueError('Axis scaling mismatch')
    for ext in ['png','svg','pdf']:fig.savefig(path.with_suffix('.'+ext),dpi=300)
    plt.close(fig)
    return path,scales


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);args=parser.parse_args()
    rows,manifest=analysis.read_raw(args.directory)
    points=precision_points(rows,analysis.summaries(rows),manifest)
    validate_independently(points,rows)
    out=args.directory/'precision';out.mkdir(exist_ok=False)
    analysis.write_csv(out/'plotted_points.csv',points)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none','pdf.fonttype':42})
    path,scales=draw(points,out,manifest)
    # Compare at identical nominal grid settings, without pretending different N is equal work.
    pairs={}
    for p in points:
        key=(p['kernel'],p['implementation'],p['nominal_footprint_bytes'])
        pairs.setdefault(key,{})[p['datatype']]=p
    max_byte_difference=max(abs(int(p['float']['footprint_bytes'])-int(p['double']['footprint_bytes'])) for p in pairs.values())
    if max_byte_difference>96:raise ValueError('Unexpected footprint mismatch')
    validation=dict(run_id=manifest['run_id'],raw_rows=len(rows),independently_checked_points=len(points),series=18,measured_sizes_per_series=34,
                    observations_per_variant_point=15,axes=scales,png_dimensions=[5400,4050],dpi=300,
                    matching='Same nominal footprint, kernel, implementation, stride, offset/alignment, seed and FP policy; N differs by precision and is normalized explicitly.',
                    maximum_actual_byte_footprint_difference=max_byte_difference,
                    interpretation='Per-element elapsed cost at matched footprint; NOT equal-N total-runtime precision speedup.',
                    source_csv_sha256={f'repeat-{i}/raw.csv':hashlib.sha256((args.directory/f'repeat-{i}/raw.csv').read_bytes()).hexdigest() for i in range(3)})
    (out/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    print(path);print(json.dumps(validation,indent=2))
if __name__=='__main__':main()
