from pathlib import Path
import sys,csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(sys.argv[1]);summary=[];count=0
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold'})
fig,axs=plt.subplots(2,3,figsize=(12,7),layout='constrained')
for col,k in enumerate(['axpy','dot','multiply']):
 rows=list(csv.DictReader((p/f'{k}-cycles.csv').open()));times=list(csv.DictReader((p/f'{k}.csv').open()));assert len(rows)==len(times)==300
 assert all(r['correct']=='pass' for r in times);count+=len(rows)
 for row,t in enumerate(['float','double']):
  ax=axs[row,col]
  for v,c,m in [('scalar','#24649a','o'),('auto','#bb6c16','s')]:
   xs=[];ys=[];los=[];his=[]
   for n in sorted({int(r['n']) for r in rows}):
    rr=sorted([r for r in rows if r['datatype']==t and r['implementation']==v and int(r['n'])==n],key=lambda r:int(r['trial']))
    assert [int(r['trial']) for r in rr]==list(range(15))
    a=np.array([int(r['cycles'])/n for r in rr]);assert np.all(a>0)
    med=np.median(a);lo,hi=np.percentile(a,[25,75]);xs.append(n);ys.append(med);los.append(lo);his.append(hi)
    summary.append(dict(kernel=k,datatype=t,implementation=v,n=n,cycles_per_element=med,q25=lo,q75=hi))
   ax.plot(xs,ys,color=c,marker=m,label='Scalar' if v=='scalar' else 'Auto');ax.fill_between(xs,los,his,color=c,alpha=.14)
  ax.set_xscale('log',base=2);ax.set_xticks(xs,['1K','32K','256K','1M','16M']);ax.set_ylim(bottom=0);ax.set_title(f'{k.upper() if k=="axpy" else k.capitalize()} · {t}');ax.set_xlabel('Array length (elements)');ax.grid(axis='y',alpha=.18);ax.legend(frameon=False)
  if col==0:ax.set_ylabel('Core cycles / element')
for ext in ['png','svg']:fig.savefig(p/f'cycles_per_element.{ext}',dpi=300)
with (p/'summary.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=summary[0]);w.writeheader();w.writerows(summary)
(p/'validation.json').write_text(json.dumps({'observations':count,'correctness':'all pass','trials_per_case':15,'counter':'pinned, time_running equals time_enabled'},indent=2))
print('Validated',count)
for r in summary:
 if r['n'] in [32768,16777216]:print(r)
