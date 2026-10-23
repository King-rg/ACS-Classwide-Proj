import os
"""Build and run supplementary C studies; timestamped immutable acquisition."""
from pathlib import Path
import subprocess as sp, json, datetime, os, random, hashlib, csv
R=Path(__file__).resolve().parents[2]; S=R/'experiments/supplemental-c'
O=R/'output/supplemental-c'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
O=Path(os.environ.get('REPORT_RUN_DIR',str(O)));B=O/'build';B.mkdir(parents=True);(O/'source').mkdir()
commands=[]
def run(cmd,**kw):
 commands.append(list(map(str,cmd)));return sp.run(list(map(str,cmd)),cwd=R,check=True,**kw)
common=['gcc','-std=c11','-O3','-mavx','-ffp-contract=off','-Wall','-Wextra']
objs=[]
for kernel in ['axpy','dot']:
 for variant in ['scalar','auto']+(['strict'] if kernel=='dot' else []):
  source=B/f'{kernel}_{variant}.c';source.write_text((R/f'src/{kernel}_scalar.c').read_text().replace('_scalar','_'+variant))
  (B/'kernels.h').write_text((R/'src/kernels.h').read_text())
  flags=([] if variant=='strict' else ['-ffast-math'])+(['-fno-tree-vectorize','-fno-tree-slp-vectorize'] if variant=='scalar' else [f'-fopt-info-vec-all={B}/{kernel}_{variant}.vec'])
  obj=source.with_suffix('.o');run(common+flags+['-c',source,'-o',obj]);objs.append(obj)
for typ,ctype in [('f','float'),('d','double')]:
 for variant in ['scalar','auto']:
  obj=B/f'stride_{variant}_{typ}.o'; flags=['-ffast-math']+(['-fno-tree-vectorize','-fno-tree-slp-vectorize'] if variant=='scalar' else [f'-fopt-info-vec-all={B}/stride_{typ}.vec'])
  run(common+flags+[f'-DTYPE={ctype}',f'-DNAME=axpy_stride_{variant}_{typ}','-c',S/'loops.c','-o',obj]);objs.append(obj)
for part,extra in [('stream',['-ffast-math',f'-fopt-info-vec-all={B}/stream.vec']),('compute',['-mfma'])]:
 obj=B/f'{part}.o';run(common+extra+['-c',S/f'{part}.c','-o',obj]);objs.append(obj)
for obj in objs:
 with obj.with_suffix('.asm').open('w') as f:run(['objdump','-d',obj],stdout=f)
for typ in ['float','double']:
 run(common+(['-DDOUBLE'] if typ=='double' else [])+[S/'runner.c',*objs,'-lm','-o',B/typ])
cpu=min(os.sched_getaffinity(0)); cases=[]
for typ,size in [('float',4),('double',8)]:
 for base in [32,4096]:
  for tail in range(8):
   for off in [0,1]:cases.append(('alignment',typ,base+tail,1,off,4096 if base==32 else 256))
 for footprint in [256*1024,192*1024**2]:
  for stride in [1,2,4,8]:cases.append(('stride',typ,footprint//(2*size*stride),stride,0,32 if footprint<1024**2 else 1))
 for n in [4096,65536]:cases.append(('dot',typ,n,1,0,256 if n==4096 else 16))
 # Independent large contiguous AXPY reference for the roofline.
 cases.append(('roofline',typ,192*1024**2//(2*size),1,0,1))
cases += [('stream','float',192*1024**2//12,1,0,1),('compute','float',1000000,1,0,1)]
random.Random(4320).shuffle(cases)
probe=sp.run(['perf','stat','-e','cycles:u','--','taskset','-c',str(cpu),'true'],text=True,capture_output=True)
meta={'cpu':cpu,'started':datetime.datetime.now(datetime.timezone.utc).isoformat(),'compiler':sp.check_output(['gcc','--version'],text=True),'uname':sp.check_output(['uname','-a'],text=True),'trials':15,'warmups':5,'cases':cases,'perf_probe':probe.stderr,'perf_available':probe.returncode==0,'commands':commands,'governor':Path(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor').read_text().strip(),'smt':Path('/sys/devices/system/cpu/smt/active').read_text().strip()}
for p in S.iterdir():
 if p.is_file():(O/'source'/p.name).write_bytes(p.read_bytes())
(O/'metadata.json').write_text(json.dumps(meta,indent=2));print(O,flush=True)
with (O/'raw.csv').open('w') as f:
 writer=None
 for i,(study,typ,n,st,off,calls) in enumerate(cases):
  cmd=['taskset','-c',str(cpu),B/typ,study,str(n),str(st),str(off),'15',str(calls)]
  result=run(cmd,capture_output=True,text=True)
  rows=list(csv.DictReader(result.stdout.splitlines()));assert rows and all(r['check']=='pass' for r in rows)
  if writer is None:writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader()
  writer.writerows(rows);f.flush();print(f'{i+1}/{len(cases)} {study} {typ} n={n} stride={st} offset={off}',flush=True)
meta['finished']=datetime.datetime.now(datetime.timezone.utc).isoformat();meta['commands']=commands;meta['sha256']=hashlib.sha256((O/'raw.csv').read_bytes()).hexdigest();(O/'metadata.json').write_text(json.dumps(meta,indent=2))
print('COMPLETE '+str(O),flush=True)
