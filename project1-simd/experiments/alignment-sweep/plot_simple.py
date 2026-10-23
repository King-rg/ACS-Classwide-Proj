"""Equal-kernel geometric mean of scalar/auto speedup at matched base N."""
from pathlib import Path
import csv,math,sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[2]
O=Path(sys.argv[1]) if len(sys.argv)>1 else R/'output/alignment-sweep'/(R/'output/alignment-sweep/LATEST').read_text().strip()
rows=list(csv.DictReader((O/'summary.csv').open()));out=[]
conditions=['clean','tail','shifted','combined'];labels=['Aligned baseline','Tail only','Shifted','Shifted + tail'];colors=['#24649a','#477d62','#bb6c16','#8e679b']
for typ in ['float','double']:
 for n in sorted({int(r['base']) for r in rows}):
  for c in conditions:
   rr=[r for r in rows if r['datatype']==typ and int(r['base'])==n and r['condition']==c]
   assert len(rr)==3 and {r['kernel'] for r in rr}=={'axpy','dot','multiply'}
   vals=[float(r['speedup']) for r in rr];assert all(v>0 for v in vals)
   out.append(dict(datatype=typ,base=n,condition=c,speedup=math.exp(sum(math.log(v) for v in vals)/3)))
with (O/'average_speedup.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=out[0]);w.writeheader();w.writerows(out)
plt.rcParams.update({'font.size':12,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(1,2,figsize=(12,4.8),sharey=True)
for ax,typ in zip(axes,['float','double']):
 for c,label,color,marker in zip(['clean','shifted'],['Aligned baseline','Shifted one element'],['#24649a','#bb6c16'],['o','s']):
  rr=[r for r in out if r['datatype']==typ and r['condition']==c];ax.plot([r['base'] for r in rr],[r['speedup'] for r in rr],label=label,color=color,marker=marker,ms=4,lw=1.8)
 ax.axhline(1,color='#777',ls='--',lw=1);ax.set_xscale('log',base=2);ax.set_xticks([32,2048,131072,8388608],labels=['32','2K','128K','8M']);ax.set_xlabel('Base array length (elements)');ax.set_title(typ.capitalize());ax.set_ylim(0,6.5);ax.grid(axis='y',alpha=.18)
axes[0].set_ylabel('Scalar-to-auto speedup (×)')
fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',ncol=3,frameon=False)
fig.tight_layout(rect=(0,0,1,.89));P=O/'plots';P.mkdir(exist_ok=True);fig.savefig(P/'simple_speedup.png',dpi=220);fig.savefig(P/'simple_speedup.svg');plt.close(fig)
for r in out:
 if r['base']==32768:print(r)

fig,ax=plt.subplots(figsize=(10,4.8))
for j,typ in enumerate(['float','double']):
 vals=[next(r['speedup'] for r in out if r['datatype']==typ and r['base']==32768 and r['condition']==c) for c in conditions]
 xx=[j*5+i for i in range(4)]
 bars=ax.bar(xx,vals,width=.8,color=colors)
 for bar,v in zip(bars,vals):ax.text(bar.get_x()+bar.get_width()/2,v+.06,f'{v:.2f}×',ha='center',fontsize=11)
ax.set_xticks([1.5,6.5],labels=['Float','Double']);ax.set_ylabel('Scalar-to-auto speedup (×)');ax.set_ylim(0,6);ax.axhline(1,color='#777',ls='--',lw=1);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
fig.legend(bars,labels,loc='upper center',ncol=4,frameon=False);fig.tight_layout(rect=(0,0,1,.88));fig.savefig(P/'representative_speedup.png',dpi=220);fig.savefig(P/'representative_speedup.svg');plt.close(fig)
