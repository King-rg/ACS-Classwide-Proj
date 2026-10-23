"""Compile identical C loops with/without GCC vectorization; no intrinsic objects."""
from pathlib import Path
import subprocess, os, math, random, json, datetime, hashlib, argparse
parser=argparse.ArgumentParser()
parser.add_argument('--extended',action='store_true')
parser.add_argument('--aligned',action='store_true')
args=parser.parse_args()
R=Path(__file__).resolve().parents[1]; B=R/'build/auto-comparison'; O=R/'output/auto-comparison'
if args.extended: O=R/'output/auto-extended'
if args.aligned: O=R/'output/auto-aligned'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
B.mkdir(parents=True,exist_ok=True); O.mkdir(parents=True,exist_ok=True)
def run(cmd,**kw): subprocess.run(cmd,cwd=R,check=True,**kw)
# Generated harness copies only rename the second implementation; source stays inspectable.
h=(R/'src/kernels.h').read_text().replace('_simd','_auto'); (B/'kernels.h').write_text(h)
(B/'benchmark.h').write_text((R/'src/benchmark.h').read_text())
(B/'benchmark.c').write_text((R/'src/benchmark.c').read_text().replace('simd ? "simd"','simd ? "auto"'))
common=['gcc','-std=c11','-D_POSIX_C_SOURCE=200809L','-O3','-mavx','-ffp-contract=off','-Wall','-Wextra','-Wpedantic','-I'+str(B)]
run(common+['-DSIMD_BUILD_MODE="avx-auto"','-DBENCH_AUTO=1','-c',str(B/'benchmark.c'),'-o',str(B/'benchmark.o')])
objects=[]
for k in ['axpy','dot','multiply']:
 s=(R/f'src/{k}_scalar.c').read_text()
 for variant in ['scalar','auto']:
  source=B/f'{k}_{variant}.c'; source.write_text(s.replace('_scalar','_auto') if variant=='auto' else s)
  flags=['-ffast-math']+(['-fno-tree-vectorize','-fno-tree-slp-vectorize'] if variant=='scalar' else [f'-fopt-info-vec-all={B}/{k}-vectorization.txt'])
  report=B/f'{k}-vectorization.txt'
  if variant=='auto' and report.exists(): report.unlink()
  obj=B/f'{k}_{variant}.o';run(common+flags+['-c',str(source),'-o',str(obj)]);objects.append(str(obj))
  with (B/f'{k}_{variant}-disassembly.txt').open('w') as out:run(['objdump','-d',str(obj)],stdout=out)
 (B/f'{k}_main.c').write_text((R/f'src/{k}_main.c').read_text().replace('_simd','_auto'))
 run(common+['-c',str(B/f'{k}_main.c'),'-o',str(B/f'{k}_main.o')])
 run(['gcc',str(B/f'{k}_main.o'),str(B/f'{k}_scalar.o'),str(B/f'{k}_auto.o'),str(B/'benchmark.o'),'-lm','-o',str(B/k)])
(B/'correctness.c').write_text((R/'tests/correctness.c').read_text().replace('_simd','_auto'))
run(common+['-c',str(B/'correctness.c'),'-o',str(B/'correctness.o')])
run(['gcc',str(B/'correctness.o'),*objects,str(B/'benchmark.o'),'-lm','-o',str(B/'correctness')]);run([str(B/'correctness')])
sizes=sorted({round(math.exp(math.log(19)+i*(math.log(4194304)-math.log(19))/47)) for i in range(48)})
if args.extended:
 sizes=sorted(set(sizes + [6291456,8388608,12582912,16777216,25165824,33554432]))
if args.aligned: sizes=sorted({((n+7)//8)*8 for n in sizes})
order=sizes.copy();random.Random(4320).shuffle(order);cpu=min(os.sched_getaffinity(0))
caches=[]
for directory in sorted(Path(f'/sys/devices/system/cpu/cpu{cpu}/cache').glob('index*')):
 if (directory/'type').read_text().strip() == 'Instruction': continue
 level=int((directory/'level').read_text()); raw=(directory/'size').read_text().strip()
 kib=int(raw[:-1])*(1024 if raw[-1]=='M' else 1)
 label='L1D' if level==1 else f'L{level}'
 capacity=f'{kib} KiB' if kib<1024 else f'{kib/1024:g} MiB'
 caches.append({'level':label,'capacity_kib':kib,'label':label+'\n'+capacity,'shared_cpus':(directory/'shared_cpu_list').read_text().strip()})
(O/'cache_metadata.json').write_text(json.dumps({'cpu':cpu,'caches':caches,'note':'Nominal capacities, not measured transition boundaries.'},indent=2))
meta={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sizes':sizes,'size_order':order,'trials':15,'warmups':5,'cpu':cpu,'compiler':subprocess.check_output(['gcc','--version'],text=True),'kernel_flags':common[1:]+['-ffast-math'],'scalar_extra_flags':['-fno-tree-vectorize','-fno-tree-slp-vectorize'],'notes':'Identical scalar-loop sources; auto has vectorization enabled. Both kernels permit FP reassociation with fast-math; strict harness validation. No intrinsics linked. Single-call timing; no frequency control/isolation.','allocation_alignment_bytes':64,'offset_elements':0,'vector_multiple_lengths':args.aligned,'commands':[]}
(O/'metadata.json').write_text(json.dumps(meta,indent=2))
for k in ['axpy','dot','multiply']:
 cmd=['taskset','-c',str(cpu),str(B/k),'--sizes',','.join(map(str,order)),'--trials','15','--warmups','5','--csv',str(O/f'{k}.csv')]
 print('Measuring '+k,flush=True);run(cmd);meta['commands'].append(cmd)
 meta[k+'_sha256']=hashlib.sha256((O/f'{k}.csv').read_bytes()).hexdigest();(O/'metadata.json').write_text(json.dumps(meta,indent=2))
meta['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();(O/'metadata.json').write_text(json.dumps(meta,indent=2))
