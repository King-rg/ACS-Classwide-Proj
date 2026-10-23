import os
from pathlib import Path
import subprocess as sp,datetime,json,csv,random,shutil
R=Path(__file__).resolve().parents[2]; O=R/'output/cycles'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');O=Path(os.environ.get('REPORT_RUN_DIR',str(O)));B=O/'build';B.mkdir(parents=True)
def run(c,**kw):return sp.run(list(map(str,c)),check=True,cwd=R,**kw)
for f in ['benchmark.h','benchmark.c','kernels.h']:shutil.copy2(R/'src'/f,B/f)
shutil.copy2(R/'experiments/cycles/counter.h',B/'counter.h')
flags=['gcc','-std=c11','-D_GNU_SOURCE','-D_POSIX_C_SOURCE=200809L','-O3','-mavx','-ffp-contract=off','-DBENCH_AUTO=1','-DSIMD_BUILD_MODE="avx-auto-cycles"','-I'+str(B)]
run(flags+['-c',B/'benchmark.c','-o',B/'benchmark.o'])
sizes=[1024,32768,262144,1048576,16777216];order=sizes.copy();random.Random(4320).shuffle(order)
meta={'sizes':sizes,'trials':15,'warmups':5,'cpu':min(os.sched_getaffinity(0)),'alignment':64,'event':'PERF_COUNT_HW_CPU_CYCLES; user only; pinned; no multiplexing','notes':'Separate single-call run. Counter brackets encompass the timer and dispatch as well as the kernel. Setup, warmups, reset and validation excluded. No overhead subtraction. No inferred cycles from nominal frequency.','commands':[]}
(O/'metadata.json').write_text(json.dumps(meta,indent=2));print(O,flush=True)
for k in ['axpy','dot','multiply']:
 s=(R/f'src/{k}_main.c').read_text().replace('#include "benchmark.h"','#include "benchmark.h"\n#include "counter.h"')
 s=s.replace('const uint64_t start = now_ns();','cycle_start();\n            const uint64_t start = now_ns();')
 s=s.replace('const double elapsed = (double)(now_ns() - start);','const double elapsed = (double)(now_ns() - start);\n            cycle_stop();\n            fprintf(stderr,"%s,%s,%zu,%zu,%s,%llu\\n", "'+k+'", sizeof(*x)==4?"float":"double",n,trial,simd?"auto":"scalar",(unsigned long long)cycle_value);')
 (B/f'{k}_main.c').write_text(s)
 objs=[B/'benchmark.o']
 for v in ['scalar','simd']:
  src=(R/f'src/{k}_scalar.c').read_text();src=src.replace('_scalar','_simd') if v=='simd' else src
  path=B/f'{k}_{v}.c';path.write_text(src);obj=B/f'{k}_{v}.o';objs.append(obj)
  run(flags+['-ffast-math']+(['-fno-tree-vectorize','-fno-tree-slp-vectorize'] if v=='scalar' else [])+['-c',path,'-o',obj])
 run(flags+[B/f'{k}_main.c',*objs,'-lm','-o',B/k])
 cmd=['taskset','-c',str(min(os.sched_getaffinity(0))),B/k,'--sizes',','.join(map(str,order)),'--trials','15','--warmups','5','--csv',O/f'{k}.csv']
 print('Measuring',k,flush=True)
 with (O/f'{k}-cycles.csv').open('w') as f:
  f.write('kernel,datatype,n,trial,implementation,cycles\n');f.flush();run(cmd,stderr=f)
 meta['commands'].append(list(map(str,cmd)));(O/'metadata.json').write_text(json.dumps(meta,indent=2))
print('Complete',flush=True)
