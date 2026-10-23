"""Replot measured stride trials as matched scalar/auto speedup."""
from pathlib import Path
import sys,csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(sys.argv[1]); rows=list(csv.DictReader((p/'raw.csv').open()))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold'})
fig,axs=plt.subplots(1,2,figsize=(12,4.6),sharey=True,layout='constrained');summary=[]
for ax,fp,title in zip(axs,[256*1024,192*1024**2],['L2-sized · 256 KiB','DRAM-sized · 192 MiB']):
 for t,b,c,m in [('float',4,'#24649a','o'),('double',8,'#bb6c16','s')]:
  vals=[]
  for st in [1,2,4,8]:
   n=fp//(2*b*st); d={}
   for v in ['scalar','auto']:
    rr=sorted([r for r in rows if r['study']=='stride' and r['type']==t and int(r['n'])==n and int(r['stride'])==st and r['variant']==v],key=lambda r:int(r['trial']))
    assert [int(r['trial']) for r in rr]==list(range(15)) and all(r['check']=='pass' for r in rr)
    d[v]=np.array([float(r['ns_per_call']) for r in rr])
   a=d['scalar']/d['auto']; vals.append(a)
   summary.append(dict(type=t,footprint_bytes=fp,stride=st,speedup=float(np.median(a)),q25=float(np.percentile(a,25)),q75=float(np.percentile(a,75))))
  ax.plot(range(4),np.median(vals,axis=1),color=c,marker=m,label=t,lw=2)
  ax.fill_between(range(4),np.percentile(vals,25,axis=1),np.percentile(vals,75,axis=1),color=c,alpha=.14)
 ax.axhline(1,color='#62686d',ls='--',lw=1); ax.set_xticks(range(4),['1\n(contiguous)','2','4','8']);ax.set_xlabel('Stride (elements)');ax.set_title(title);ax.grid(axis='y',alpha=.18);ax.legend(frameon=False);ax.set_ylim(bottom=0)
axs[0].set_ylabel('Scalar time / auto-build time (×)')
for ext in ['png','svg']:fig.savefig(p/'plots'/('stride_speedup.'+ext),dpi=300)
with (p/'stride_speedup.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=summary[0]);w.writeheader();w.writerows(summary)
print(summary)
