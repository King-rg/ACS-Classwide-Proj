from pathlib import Path
import csv,json,collections
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[2];O=R/'output/alignment-sweep'/(R/'output/alignment-sweep/LATEST').read_text().strip();P=O/'plots';P.mkdir(exist_ok=True)
rows=list(csv.DictReader((O/'raw.csv').open()));g=collections.defaultdict(list)
for r in rows:
 assert r['correct']=='pass'
 g[(r['kernel'],r['datatype'],int(r['base']),r['condition'],r['implementation'])].append(float(r['elapsed_ns'])/int(r['n']))
assert all(len(v)==15 for v in g.values())
s={k:np.median(v) for k,v in g.items()};bases=sorted({k[2] for k in s});C={'clean':'#24649a','shifted':'#bb6c16','tail':'#477d62','combined':'#8e679b'};labels={'clean':'Aligned, no tail','shifted':'Shifted one element','tail':'Seven added elements','combined':'Shifted + seven elements'}
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
processed=[]
for k in ['axpy','dot','multiply']:
 for typ in ['float','double']:
  for b in bases:
   for c in C:
    a=s[k,typ,b,c,'auto'];sc=s[k,typ,b,c,'scalar'];base=s[k,typ,b,'clean','auto']
    processed.append(dict(kernel=k,datatype=typ,base=b,condition=c,auto_ns_element=a,scalar_ns_element=sc,speedup=sc/a,auto_cost_ratio=a/base))
with (O/'summary.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=processed[0]);w.writeheader();w.writerows(processed)
for kind in ['cost','speedup']:
 fig,axes=plt.subplots(3,2,figsize=(12,10))
 for row,k in enumerate(['axpy','dot','multiply']):
  for col,typ in enumerate(['float','double']):
   ax=axes[row,col];width=4 if typ=='float' else 8;arrays=3 if k=='multiply' else 2;x=np.array(bases)*width*arrays/1024
   for c in C:
    if kind=='cost' and c=='clean':continue
    y=[];lo=[];hi=[]
    for b in bases:
     a=s[k,typ,b,c,'auto'];baseline=s[k,typ,b,'clean','auto'];v=np.array(g[k,typ,b,c,'auto'])
     y.append(a/baseline if kind=='cost' else s[k,typ,b,c,'scalar']/a)
     lo.append(np.percentile(v,25)/baseline);hi.append(np.percentile(v,75)/baseline)
    ax.plot(x,y,'o-',ms=3,lw=1.3,color=C[c],label=labels[c])
    if kind=='cost':ax.fill_between(x,lo,hi,color=C[c],alpha=.1)
   if kind=='speedup':
    h=collections.defaultdict(list)
    for r in csv.DictReader((R/'output/auto-extended'/f'{k}.csv').open()):
     if r['datatype']==typ:h[int(r['n']),r['implementation']].append(float(r['elapsed_ns']))
    ns=sorted({a for a,v in h});ax.plot(np.array(ns)*width*arrays/1024,[np.median(h[n,'scalar'])/np.median(h[n,'auto']) for n in ns],':',color='#555555',lw=1,label='Previous section (historical)')
   for v,label in [(48,'L1'),(1280,'L2'),(24576,'LLC')]:ax.axvline(v,color='#aaa',ls=':',lw=.7);ax.text(v,.98,label,transform=ax.get_xaxis_transform(),va='top',fontsize=8)
   ax.axhline(1,color='#777',lw=.7);ax.set_xscale('log');ax.grid(axis='y',alpha=.15);ax.set_title(k.upper()+' · '+typ);ax.set_xlabel('Base working set (KiB)');ax.set_ylabel('Auto time/element ÷ clean baseline' if kind=='cost' else 'Scalar / auto speedup')
 handles,ls=axes[0,0].get_legend_handles_labels();fig.legend(handles,ls,loc='upper center',ncol=3,frameon=False);fig.tight_layout(rect=(0,0,1,.94));fig.savefig(P/(kind+'.png'),dpi=200);fig.savefig(P/(kind+'.svg'));plt.close(fig)
lines=['# Working-set alignment and tail comparison',f'{len(rows)} validated measurements: 3 kernels × 2 precisions × 12 base sizes × 4 conditions × 2 builds × 15 trials. Five warmups; one timed call; CPU 0. Matched compiler flags and original input sequence.','The clean baseline uses 64-byte alignment and lengths divisible by eight. Shifted cases move every array one element (4 bytes for float, 8 for double). Tail cases add seven elements: remainder seven for float and three for double under 256-bit AVX. Combined cases apply both. Time per element accounts for the extra work.','The historical series is the actual previous-section data, plotted at its original sizes. Those allocations were not consistently 64-byte aligned and their lengths often already had tails. Consequently, only the new matched comparisons isolate these changes; historical differences also include allocation, run-to-run variation and different sizes.','Shading in the cost plot is the case timing IQR divided by the clean median; it is not a confidence interval and does not include uncertainty in that denominator. Cache lines mark nominal capacities. Base working set counts two arrays for AXPY/dot and three for multiplication; an AXPY reset source is outside the timed kernel but can affect cache state. Tiny single-call measurements are timer/call-overhead sensitive.']
lines+=['## Measured changes','Ranges below summarize medians across tested sizes; positive values mean slower auto-vectorized time per element.']
for k in ['axpy','dot','multiply']:
 for typ in ['float','double']:
  lines.append(f'### {k}, {typ}')
  for c in ['shifted','tail','combined']:
   rr=[r for r in processed if r['kernel']==k and r['datatype']==typ and r['condition']==c]
   v=[100*(r['auto_cost_ratio']-1) for r in rr];large=[100*(r['auto_cost_ratio']-1) for r in rr if r['base']>=4194304]
   lines.append(f'- {labels[c]}: {min(v):+.1f}% to {max(v):+.1f}%; large-size median {np.median(large):+.1f}%.')
lines+=['![Direct cost comparison](plots/cost.png)','![Speedup with historical baseline](plots/speedup.png)','## Interpretation limits','A tail-case difference is a whole-loop effect, not a direct measurement of cleanup instructions. Small effects comparable to trial variability should not be assigned to tails. Changing N can alter compiler paths and cache placement; no cold-cache behavior is inferred. All observations are retained. No new result replaces the previous figures.']
(O/'REPORT.md').write_text('\n\n'.join(lines));print('\n'.join(lines[5:]))
