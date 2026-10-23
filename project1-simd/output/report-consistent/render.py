from pathlib import Path
import csv, json, hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
R=Path(__file__).resolve().parents[2]; O=Path(__file__).resolve().parent
M=R/'output/auto-aligned/20261022T024622Z'; A=R/'output/alignment-sweep/20261022T015440Z'; S=R/'output/supplemental-c/20261021T232708Z'; CYC=R/'output/cycles/20261022T031800Z'
BLUE='#24649a'; ORANGE='#bb6c16'; GRAY='#707982'; GREEN='#477d62'; PURPLE='#8e679b'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.labelsize':12,'xtick.labelsize':11,'ytick.labelsize':11,'legend.fontsize':11,'axes.titlesize':12,'axes.titleweight':'bold','axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#707982','axes.linewidth':.7,'text.color':'#263340','axes.labelcolor':'#263340','xtick.color':'#4b535a','ytick.color':'#4b535a','lines.linewidth':1.6,'lines.markersize':4,'savefig.facecolor':'white'})
def read(p): return list(csv.DictReader(p.open()))
def base(nr=1,nc=2,h=4.4):
 f,axs=plt.subplots(nr,nc,figsize=(10,h),squeeze=False)
 f.subplots_adjust(left=.09,right=.965,bottom=.17 if nr==1 else .10,top=.80 if nr==1 else .88,wspace=.25,hspace=.62)
 for ax in axs.flat: ax.set_axisbelow(True);ax.grid(axis='y',color='#d9dfe4',lw=.65);ax.tick_params(length=3)
 return f,axs
points=[]
def line(ax,x,arr,label,c,marker='o',ls='-'):
 arr=np.array(arr);lo,med,hi=np.percentile(arr,[25,50,75],axis=1)
 ax.plot(x,med,label=label,color=c,marker=marker,ls=ls)
 ax.fill_between(x,lo,hi,color=c,alpha=.14,linewidth=0)
 points.append({'series':label,'x':list(map(float,x)),'median':med.tolist(),'q25':lo.tolist(),'q75':hi.tolist()})
 return hi.max()
def legend(f,ax,ncol=2): f.legend(*ax.get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.54,.995),ncol=ncol,frameon=False)
def save(f,n):
 for ax in f.axes: ax.set_ylim(bottom=0)
 f.savefig(O/f'figure-{n}.png',dpi=195); f.savefig(O/f'figure-{n}.svg');plt.close(f)
def equal(ax):ax.axhline(1,color=GRAY,lw=1,ls='--',zorder=1)
ks=['axpy','dot','multiply']; names=['AXPY','Dot product','Multiplication'];types=['float','double']
D={};sizes=json.loads((M/'metadata.json').read_text())['sizes']
for k in ks:
 rr=read(M/f'{k}.csv');assert all(r['correct']=='pass' for r in rr)
 for t in types:
  for n in sizes:
   for v in ['scalar','auto']:
    g=sorted((r for r in rr if r['datatype']==t and int(r['n'])==n and r['implementation']==v),key=lambda r:int(r['trial']));assert len(g)==15
    D[k,t,n,v]=np.array([float(r['elapsed_ns']) for r in g])
def cacheaxis(ax):
 ax.set_xscale('log');ax.set_xlim(.12,900000);ax.set_xticks([1,1024,524288],['1 KiB','1 MiB','512 MiB'])
 for x,label in [(48,'L1'),(1280,'L2'),(24576,'L3')]:
  ax.axvline(x,color=GRAY,ls=':',lw=.8,zorder=0);ax.text(x,.98,label,transform=ax.get_xaxis_transform(),ha='center',va='top',fontsize=10,color=GRAY)
def xvals(k,t):return np.array(sizes)*(4 if t=='float' else 8)*(3 if k=='multiply' else 2)/1024
f,axs=base(1,3,4.3);mx=0
for ax,k,title in zip(axs.flat,ks,names):
 for t,c,m in zip(types,[BLUE,ORANGE],['o','s']):mx=max(mx,line(ax,xvals(k,t),[D[k,t,n,'scalar']/D[k,t,n,'auto'] for n in sizes],t.capitalize(),c,m))
 cacheaxis(ax);equal(ax);ax.set_title(title,pad=10)
for ax in axs.flat:ax.set_ylim(0,mx*1.18)
axs[0,0].set_ylabel('Scalar / auto speedup (×)');f.supxlabel('Working-set size (log scale)',y=.035,fontsize=12);legend(f,axs[0,0]);save(f,1)
f,axs=base(2,3,6.6);mx=0
for i,t in enumerate(types):
 for j,(k,name) in enumerate(zip(ks,names)):
  ax=axs[i,j]
  for v,c,m in zip(['scalar','auto'],[BLUE,ORANGE],['o','s']):mx=max(mx,line(ax,xvals(k,t),[(1 if k=='multiply' else 2)*n/D[k,t,n,v] for n in sizes],'Scalar' if v=='scalar' else 'Auto-vectorized',c,m))
  cacheaxis(ax);ax.set_title(f'{name} · {t}',pad=10)
 axs[i,0].set_ylabel('Throughput (GFLOP/s)')
for ax in axs.flat:ax.set_ylim(0,mx*1.18)
f.supxlabel('Working-set size (log scale)',y=.015,fontsize=12);legend(f,axs[0,0]);save(f,2)
a=read(A/'average_speedup.csv')
f,axs=base()
for ax,t in zip(axs.flat,types):
 for cond,label,c,m in [('clean','Aligned baseline',BLUE,'o'),('shifted','Shifted one element',ORANGE,'s')]:
  rr=sorted((r for r in a if r['datatype']==t and r['condition']==cond),key=lambda r:int(r['base']))
  ax.plot([int(r['base']) for r in rr],[float(r['speedup']) for r in rr],label=label,color=c,marker=m)
 ax.set_xscale('log',base=2);ax.set_xticks([32,2048,131072,8388608],['32','2,048','131,072','8,388,608']);ax.tick_params(axis='x',labelsize=10);ax.set_title(t.capitalize(),pad=10);ax.set_ylim(0,6.5);equal(ax)
axs[0,0].set_ylabel('Scalar / auto speedup (×)');f.supxlabel('Original array length (elements, log scale)',y=.035,fontsize=12);legend(f,axs[0,0]);save(f,3)
f,axs=base(1,1,4.4);ax=axs[0,0]
conds=['clean','tail','shifted','combined'];labels=['Aligned baseline','Tail only','Shifted','Shifted + tail']
for i,(cond,label,c) in enumerate(zip(conds,labels,[BLUE,GREEN,ORANGE,PURPLE])):
 vals=[float(next(r['speedup'] for r in a if r['datatype']==t and int(r['base'])==32768 and r['condition']==cond)) for t in types]
 bars=ax.bar(np.arange(2)+(i-1.5)*.19,vals,width=.17,color=c,label=label)
 ax.bar_label(bars,labels=[f'{v:.2f}×' for v in vals],padding=4,fontsize=11)
ax.set_xticks([0,1],['Float','Double']);ax.set_ylim(0,6);ax.set_ylabel('Scalar / auto speedup (×)');equal(ax);legend(f,ax,4);save(f,4)
rr=read(S/'raw.csv');SD={}
for r in rr:
 assert r['check']=='pass'
 key=(r['study'],r['type'],int(r['n']),int(r['stride']),int(r['offset']),r['variant']);SD.setdefault(key,[]).append(r)
for key,g in SD.items():
 g.sort(key=lambda r:int(r['trial']));assert len(g)==15;SD[key]=np.array([float(r['ns_per_call']) for r in g])
f,axs=base()
for ax,fp,title in zip(axs.flat,[262144,201326592],['L2 cache','Main memory']):
 for t,b,c,m in [('float',4,BLUE,'o'),('double',8,ORANGE,'s')]:
  arr=[SD['stride',t,fp//(2*b*st),st,0,'scalar']/SD['stride',t,fp//(2*b*st),st,0,'auto'] for st in [1,2,4,8]];line(ax,range(4),arr,t.capitalize(),c,m)
 ax.set_xticks(range(4),['1','2','4','8']);ax.set_title(title,pad=10);equal(ax);ax.set_ylim(0,6)
axs[0,0].set_ylabel('Scalar / auto speedup (×)');f.supxlabel('Stride (elements)',y=.035,fontsize=12);legend(f,axs[0,0]);save(f,5)
f,axs=base(2,2,6.6)
for i,fp in enumerate([262144,201326592]):
 for j,t in enumerate(types):
  ax=axs[i,j];b=4 if t=='float' else 8
  for v,c,m in [('scalar',BLUE,'o'),('auto',ORANGE,'s')]:
   arr=[3*(fp//(2*b*st))*b/SD['stride',t,fp//(2*b*st),st,0,v]*1e9/2**30 for st in [1,2,4,8]];line(ax,range(4),arr,'Scalar' if v=='scalar' else 'Auto-vectorized',c,m)
  ax.set_xticks(range(4),['1','2','4','8']);ax.set_title(('L2 cache' if i==0 else 'Main memory')+' · '+t,pad=10)
 axs[i,0].set_ylabel('Useful bandwidth (GiB/s)')
 maxy=max(axs[i,0].get_ylim()[1],axs[i,1].get_ylim()[1]);axs[i,0].set_ylim(0,maxy);axs[i,1].set_ylim(0,maxy)
f.supxlabel('Stride (elements)',y=.015,fontsize=12);legend(f,axs[0,0]);save(f,6)
f,axs=base()
for ax,t in zip(axs.flat,types):
 for j,(v,c,label) in enumerate([('scalar',BLUE,'Scalar (relaxed)'),('strict',GRAY,'Auto (strict)'),('auto',ORANGE,'Auto (relaxed)')]):
  arr=[SD['dot',t,n,1,0,v]/n for n in [4096,65536]];lo,med,hi=np.percentile(arr,[25,50,75],axis=1)
  ax.bar(np.arange(2)+(j-1)*.24,med,width=.22,color=c,label=label,yerr=[med-lo,hi-med],capsize=3,error_kw={'elinewidth':1,'ecolor':'#263340'})
 ax.set_xticks([0,1],['4,096','65,536']);ax.set_title(t.capitalize(),pad=10)
maxy=max(ax.get_ylim()[1] for ax in axs.flat)
for ax in axs.flat:ax.set_ylim(0,maxy)
axs[0,0].set_ylabel('Time per element (ns)');f.supxlabel('Array length (elements)',y=.035,fontsize=12);legend(f,axs[0,0],3);save(f,7)
f,axs=base(1,1,4.8);ax=axs[0,0];n=201326592//8
band=(16*16777216/SD['stream','float',16777216,1,0,'calibration'])/6
lo,med,hi=np.percentile(band,[25,50,75]);ax.axhspan(lo,hi,color=GRAY,alpha=.14,linewidth=0);ax.axhline(med,color=GRAY,ls='--',lw=1,label='Measured-bandwidth prediction')
for j,(v,c) in enumerate([('scalar',BLUE),('auto',ORANGE)]):
 arr=2*n/SD['roofline','float',n,1,0,v];lo,med,hi=np.percentile(arr,[25,50,75]);ax.bar(j,med,width=.55,color=c,yerr=[[med-lo],[hi-med]],capsize=3,error_kw={'elinewidth':1,'ecolor':'#263340'})
ax.set_xticks([0,1],['Scalar','Auto-vectorized']);ax.set_ylabel('Throughput (GFLOP/s)');ax.set_ylim(0,6);legend(f,ax,1);save(f,8)
f,axs=base(2,3,6.6)
for j,(k,name) in enumerate(zip(ks,names)):
 rr=read(CYC/f'{k}-cycles.csv');ns=sorted({int(r['n']) for r in rr})
 for i,t in enumerate(types):
  ax=axs[i,j]
  for v,c,m in [('scalar',BLUE,'o'),('auto',ORANGE,'s')]:
   arr=[]
   for n in ns:
    g=[r for r in rr if r['datatype']==t and r['implementation']==v and int(r['n'])==n];assert len(g)==15;arr.append([int(r['cycles'])/n for r in g])
   line(ax,ns,arr,'Scalar' if v=='scalar' else 'Auto-vectorized',c,m)
  ax.set_xscale('log',base=2);ax.set_xticks(ns,['1K','32K','256K','1M','16M']);ax.tick_params(axis='x',labelsize=10);ax.set_title(f'{name} · {t}',pad=10)
for i in range(2):
 maxy=max(ax.get_ylim()[1] for ax in axs[i]);
 for ax in axs[i]:ax.set_ylim(0,maxy)
 axs[i,0].set_ylabel('Core cycles per element')
f.supxlabel('Array length (elements, log scale)',y=.015,fontsize=12);legend(f,axs[0,0]);save(f,9)
(O/'plotted-series.json').write_text(json.dumps(points,indent=2))
files=[*(M/f'{k}.csv' for k in ks),A/'average_speedup.csv',S/'raw.csv',*(CYC/f'{k}-cycles.csv' for k in ks)]
(O/'sources.json').write_text(json.dumps([{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],indent=2))
print('Rendered nine figures from original saved measurements.')
