"""Speedup and achieved GFLOP/s from matched scalar/auto C builds."""
from pathlib import Path
import argparse,csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--source-dir',type=Path,default=R/'output/auto-comparison')
args=parser.parse_args();O=args.source_dir.resolve();P=O/'plots';P.mkdir(exist_ok=True)
ks=['axpy','dot','multiply'];titles=['AXPY','Dot product','Elementwise multiply'];ts=['float','double'];vs=['scalar','auto']
meta=json.loads((O/'metadata.json').read_text());sizes=meta['sizes'];trials=meta['trials'];data={};summary=[]
for k in ks:
 rows=list(csv.DictReader((O/f'{k}.csv').open()))
 assert len(rows)==len(sizes)*trials*4
 assert all(r['kernel']==k and r['correct']=='pass' and float(r['elapsed_ns'])>0 for r in rows)
 assert len({(r['datatype'],r['implementation'],r['n'],r['trial']) for r in rows})==len(rows)
 for t in ts:
  for n in sizes:
   for v in vs:
    group=sorted([r for r in rows if r['datatype']==t and int(r['n'])==n and r['implementation']==v],key=lambda r:int(r['trial']))
    assert [int(r['trial']) for r in group]==list(range(trials))
    data[k,t,n,v]=np.array([float(r['elapsed_ns']) for r in group])
   speed=data[k,t,n,'scalar']/data[k,t,n,'auto']
   summary.append({'kernel':k,'datatype':t,'n':n,'working_set_bytes':n*(4 if t=='float' else 8)*(3 if k=='multiply' else 2),'speedup_median':np.median(speed),'speedup_q25':np.percentile(speed,25),'speedup_q75':np.percentile(speed,75),'scalar_gflops':np.median((1 if k=='multiply' else 2)*n/data[k,t,n,'scalar']),'auto_gflops':np.median((1 if k=='multiply' else 2)*n/data[k,t,n,'auto'])})
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','text.color':'#263340','axes.labelcolor':'#263340','savefig.facecolor':'white'})
colors=['#24649a','#bb6c16']
caches=json.loads((O/'cache_metadata.json').read_text())['caches']
def xvals(k,t): return np.array(sizes)*(4 if t=='float' else 8)*(3 if k=='multiply' else 2)/1024
def axis(ax):
 ax.set_xscale('log');ax.set_xlim(.12,max(sizes)*24/1024*1.12);ax.set_xticks([1,32,1024,16384,524288],['1 KiB','32 KiB','1 MiB','16 MiB','512 MiB']);ax.grid(axis='y',alpha=.18)
 ax.set_xlabel('Kernel working set (log scale)')
 for cache in caches:
  ax.axvline(cache['capacity_kib'],color='#68727b',ls=':',lw=1,zorder=0)
  ax.text(cache['capacity_kib'],1.015,cache['label'].replace('L3\n','L3 / LLC\n'),transform=ax.get_xaxis_transform(),ha='center',va='bottom',fontsize=8,color='#4b535a')
 if max(sizes)*8/1024 > 24576*4:
  ax.text(np.sqrt(24576*max(sizes)*24/1024),.65,'DRAM-sized\n> LLC capacity',transform=ax.get_xaxis_transform(),ha='center',va='bottom',fontsize=8,color='#4b535a')
def save(fig,name):
 fig.savefig(P/(name+'.png'),dpi=300);fig.savefig(P/(name+'.svg'));plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(15,5.8),sharey=True);fig.subplots_adjust(left=.06,right=.98,bottom=.16,top=.83,wspace=.13)
maxval=1
for ax,k,title in zip(axes,ks,titles):
 for t,c,marker in zip(ts,colors,['o','s']):
  ratios=[data[k,t,n,'scalar']/data[k,t,n,'auto'] for n in sizes]
  lo=np.percentile(ratios,25,axis=1);hi=np.percentile(ratios,75,axis=1);maxval=max(maxval,max(hi))
  ax.plot(xvals(k,t),np.median(ratios,axis=1),color=c,marker=marker,markersize=3,lw=1.5,label=t)
  ax.fill_between(xvals(k,t),lo,hi,color=c,alpha=.12)
 ax.axhline(1,color='#62686d',lw=1,ls='--');axis(ax);ax.set_title(title,pad=38);ax.legend(frameon=False)
axes[0].set_ylabel('Scalar time / auto-vectorized time (×)');axes[0].set_ylim(0,maxval*1.08);save(fig,'speedup')
fig,axes=plt.subplots(2,3,figsize=(15,9),sharey=True);fig.subplots_adjust(left=.06,right=.98,bottom=.10,top=.87,hspace=.55,wspace=.13)
maxval=1
for row,t in enumerate(ts):
 for col,(k,title) in enumerate(zip(ks,titles)):
  ax=axes[row,col]
  for v,c,marker in zip(vs,colors,['o','s']):
   throughput=[(1 if k=='multiply' else 2)*n/data[k,t,n,v] for n in sizes]
   lo=np.percentile(throughput,25,axis=1);hi=np.percentile(throughput,75,axis=1);maxval=max(maxval,max(hi))
   ax.plot(xvals(k,t),np.median(throughput,axis=1),color=c,marker=marker,markersize=3,lw=1.5,label='Scalar baseline' if v=='scalar' else 'Auto-vectorized')
   ax.fill_between(xvals(k,t),lo,hi,color=c,alpha=.12)
  axis(ax);ax.set_title(f'{title} · {t}',pad=38);ax.legend(frameon=False,fontsize=9)
 axes[row,0].set_ylabel('Achieved throughput (GFLOP/s)')
axes[0,0].set_ylim(0,maxval*1.08);save(fig,'throughput')
with (O/'summary.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=summary[0]);w.writeheader();w.writerows(summary)
(O/'plot_notes.txt').write_text('Kernel working set = distinct arrays touched by the timed kernel: 2*N*sizeof(T) for AXPY/dot; 3*N*sizeof(T) for multiply. Harness reference/reset arrays excluded. Single-call timing includes clock/dispatch overhead. No samples excluded; all validation passed. Dotted lines mark nominal CPU 0 cache capacities: L1D 48 KiB, L2 1.25 MiB, shared L3 24 MiB. These are not measured transition boundaries. Timing variability does not establish cache boundaries or memory bandwidth. Floating-point reassociation permitted in both builds; these results are a new experiment, not the earlier strict-FP intrinsic comparison.\n')
for k in ks:
 print(k,[(t,round(max(r['speedup_median'] for r in summary if r['kernel']==k and r['datatype']==t),2)) for t in ts])
