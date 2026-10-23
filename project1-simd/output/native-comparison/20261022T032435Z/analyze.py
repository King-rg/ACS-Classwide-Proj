from pathlib import Path
import csv,sys,json
import numpy as np
p=Path(sys.argv[1]);summary=[];total=0
for k in ['axpy','dot','multiply']:
 rows=list(csv.DictReader((p/f'{k}.csv').open()));assert len(rows)==180;total+=len(rows)
 assert all(r['correct']=='pass' and r['calls']=='1' and int(r['n'])%8==0 and r['x_mod32']==r['y_mod32']=='0' for r in rows)
 for t in ['float','double']:
  for n in [32768,1048576,8388608]:
   vals={}
   for v in ['avx','native']:
    rr=sorted([r for r in rows if r['datatype']==t and int(r['n'])==n and r['implementation']==v],key=lambda r:int(r['trial']))
    assert [int(r['trial']) for r in rr]==list(range(15));vals[v]=np.array([float(r['elapsed_ns']) for r in rr])
   a=vals['avx']/vals['native'];summary.append(dict(kernel=k,datatype=t,n=n,ratio=float(np.median(a)),q25=float(np.percentile(a,25)),q75=float(np.percentile(a,75))))
with (p/'summary.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=summary[0]);w.writeheader();w.writerows(summary)
print(json.dumps(summary,indent=2));print('Validated',total)
