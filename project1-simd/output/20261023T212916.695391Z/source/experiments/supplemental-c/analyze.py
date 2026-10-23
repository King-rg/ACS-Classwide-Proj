from pathlib import Path
import sys,csv,json,collections
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(sys.argv[1]);P=O/'plots';P.mkdir(exist_ok=True)
rows=list(csv.DictReader((O/'raw.csv').open()));groups=collections.defaultdict(list)
for r in rows:
 assert r['check']=='pass' and float(r['elapsed_ns'])>0 and int(r['cpu'])==0
 key=(r['study'],r['type'],int(r['n']),int(r['stride']),int(r['offset']),r['variant']);groups[key].append(r)
D={};summary=[]
for key,rr in groups.items():
 rr.sort(key=lambda x:int(x['trial']));assert [int(x['trial']) for x in rr]==list(range(15))
 D[key]=a=np.array([float(x['ns_per_call']) for x in rr]);study,t,n,st,off,v=key;s=4 if t=='float' else 8
 summary.append(dict(study=study,type=t,n=n,stride=st,offset=off,variant=v,ns_median=np.median(a),ns_q25=np.percentile(a,25),ns_q75=np.percentile(a,75),gflops_median=np.median((128 if study=='compute' else 2)*n/a),useful_gib_s=np.median(3*n*s/a*1e9/2**30)))
with (O/'summary.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=summary[0]);w.writeheader();w.writerows(summary)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','text.color':'#263340','axes.labelcolor':'#263340','savefig.facecolor':'white'})
C={'scalar':'#24649a','auto':'#bb6c16','strict':'#707982'}
def save(fig,name):
 fig.savefig(P/(name+'.png'),dpi=300,bbox_inches='tight');fig.savefig(P/(name+'.svg'),bbox_inches='tight');plt.close(fig)
def line(ax,x,arr,label,c,ls='-',marker='o'):
 ax.plot(x,np.median(arr,axis=1),label=label,color=c,ls=ls,marker=marker,ms=4)
 ax.fill_between(x,np.percentile(arr,25,axis=1),np.percentile(arr,75,axis=1),color=c,alpha=.10)
fig,axs=plt.subplots(2,2,figsize=(12,8),layout='constrained')
for j,t in enumerate(['float','double']):
 for i,base in enumerate([32,4096]):
  ax=axs[i,j]
  for v in ['scalar','auto']:
   for off in [0,1]:
    a=[D['alignment',t,base+k,1,off,v]/(base+k) for k in range(8)]
    line(ax,range(8),a,('Scalar' if v=='scalar' else 'Auto')+(' · aligned' if off==0 else ' · shifted'),C[v],'-' if off==0 else '--','o' if off==0 else 's')
  ax.set_title(f'{t} · N = {base} + r');ax.set_xticks(range(8));ax.set_xlabel('Added elements (r)');ax.set_ylabel('Time per element (ns)');ax.set_ylim(bottom=0);ax.grid(axis='y',alpha=.18)
axs[0,0].legend(frameon=False,fontsize=9,ncol=2);save(fig,'alignment_tail')
fig,axs=plt.subplots(2,2,figsize=(12,8),layout='constrained')
for j,t in enumerate(['float','double']):
 for i,fp in enumerate([256*1024,192*1024**2]):
  ax=axs[i,j];s=4 if t=='float' else 8
  for v in ['scalar','auto']:
   a=[3*(fp//(2*s*st))*s/D['stride',t,fp//(2*s*st),st,0,v]*1e9/2**30 for st in [1,2,4,8]]
   line(ax,[1,2,4,8],a,'Scalar baseline' if v=='scalar' else 'Auto-vectorized',C[v],marker='o' if v=='scalar' else 's')
  ax.set_title(f'{t} · '+('256 KiB' if i==0 else '192 MiB')+' footprint');ax.set_xticks([1,2,4,8]);ax.set_xlabel('Stride (elements)');ax.set_ylabel('Useful bandwidth (GiB/s)');ax.set_ylim(bottom=0);ax.grid(axis='y',alpha=.18);ax.legend(frameon=False)
save(fig,'stride')
fig,axs=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
for ax,t in zip(axs,['float','double']):
 for j,v in enumerate(['scalar','strict','auto']):
  a=np.array([D['dot',t,n,1,0,v]/n for n in [4096,65536]]);m=np.median(a,axis=1);lo=np.percentile(a,25,axis=1);hi=np.percentile(a,75,axis=1)
  ax.bar(np.arange(2)+(j-1)*.24,m,width=.22,color=C[v],label={'scalar':'Scalar (relaxed FP)','strict':'Auto (strict FP)','auto':'Auto (relaxed FP)'}[v],yerr=[m-lo,hi-m],capsize=3)
 ax.set_xticks([0,1],['4,096','65,536']);ax.set_xlabel('Dot-product elements');ax.set_ylabel('Time per element (ns)');ax.set_title(t);ax.grid(axis='y',alpha=.18);
handles, labels = axs[0].get_legend_handles_labels()
fig.legend(handles, labels, loc='outside upper center', ncol=3, frameon=False, fontsize=10)
save(fig,'strict_dot')
stream=D['stream','float',16777216,1,0,'calibration'];compute=D['compute','float',1000000,1,0,'calibration']
Balg=np.median(12*16777216/stream);Bphys=Balg*4/3;peak=np.median(128e6/compute)
fig,ax=plt.subplots(figsize=(10,5.2),layout='constrained');xx=np.logspace(-2,2,300)
ax.loglog(xx,np.minimum(peak,Bphys*xx),color='#707982',label='Estimated DRAM roof (write allocation model)')
ax.axhline(peak,color='#707982',ls=':',label='Empirical float register-FMA peak estimate')
ax.fill_between(xx,np.minimum(np.percentile(128e6/compute,25),np.percentile(16*16777216/stream,25)*xx),np.minimum(np.percentile(128e6/compute,75),np.percentile(16*16777216/stream,75)*xx),color='#707982',alpha=.15)
roof=[]
for t,marker in [('float','o')]:
 s=4 if t=='float' else 8;n=192*1024**2//(2*s);ai=2/(3*s)
 for v in ['scalar','auto']:
  a=2*n/D['roofline',t,n,1,0,v];m=np.median(a);lo,hi=np.percentile(a,[25,75]);roof.append(dict(type=t,variant=v,gflops=m,ai=ai,roof=Bphys*ai))
  ax.errorbar(ai,m,yerr=[[m-lo],[hi-m]],fmt=marker,ms=8,color=C[v],capsize=3,label=f'AXPY {t} · {v}')
ax.set_xlabel('Estimated arithmetic intensity (FLOP/byte)');ax.set_ylabel('Achieved throughput (GFLOP/s)');ax.set_xlim(.01,100);ax.set_ylim(.1,max(peak*1.7,100));ax.grid(alpha=.16);ax.legend(frameon=False,fontsize=9,loc='lower right');save(fig,'roofline')
facts={'rows':len(rows),'groups':len(groups),'stream_useful_GB_s':Balg,'stream_estimated_physical_GB_s':Bphys,'empirical_peak_GFLOP_s':peak,'roofline_points':roof,'strict_dot':[],'alignment':[],'stride':[]}
for t in ['float','double']:
 for n in [4096,65536]:
  a=D['dot',t,n,1,0,'scalar'];facts['strict_dot'].append(dict(type=t,n=n,strict_speedup=np.median(a/D['dot',t,n,1,0,'strict']),relaxed_speedup=np.median(a/D['dot',t,n,1,0,'auto'])))
 for base in [32,4096]:
  penalties=[100*(np.median(D['alignment',t,base+k,1,1,'auto'])/np.median(D['alignment',t,base+k,1,0,'auto'])-1) for k in range(8)]
  tail=[100*((np.median(D['alignment',t,base+k,1,0,'auto'])/(base+k))/(np.median(D['alignment',t,base,1,0,'auto'])/base)-1) for k in range(8)]
  facts['alignment'].append(dict(type=t,base=base,shift_penalty_percent_range=[min(penalties),max(penalties)],max_tail_ns_per_element_penalty_percent=max(tail)))
 for fp in [256*1024,192*1024**2]:
  s=4 if t=='float' else 8
  for st in [1,2,4,8]:
   n=fp//(2*s*st);a=D['stride',t,n,st,0,'auto'];b=D['stride',t,n,st,0,'scalar'];facts['stride'].append(dict(type=t,footprint=fp,stride=st,useful_GiB_s=np.median(3*n*s/a*1e9/2**30),speedup=np.median(b/a)))
(O/'findings.json').write_text(json.dumps(facts,indent=2));print(json.dumps(facts,indent=2))
