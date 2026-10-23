import os
"""Compare AVX and native auto-vectorized loops in one alternating harness."""
from pathlib import Path
import subprocess as sp,datetime,json,csv,shutil
R=Path(__file__).resolve().parents[2];O=R/'output/native-comparison'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');O=Path(os.environ.get('REPORT_RUN_DIR',str(O)));B=O/'build';B.mkdir(parents=True)
def run(c,**kw):sp.run(list(map(str,c)),check=True,cwd=R,**kw)
for f in ['benchmark.h','kernels.h']:shutil.copy2(R/'src'/f,B/f)
s=(R/'src/benchmark.c').read_text().replace('simd ? "auto" : "scalar"','simd ? "native" : "avx"');(B/'benchmark.c').write_text(s)
common=['gcc','-std=c11','-D_POSIX_C_SOURCE=200809L','-O3','-ffp-contract=off','-I'+str(B)]
run(common+['-DBENCH_AUTO=1','-DSIMD_BUILD_MODE="avx-vs-native"','-c',B/'benchmark.c','-o',B/'benchmark.o'])
objects=[]
for k in ['axpy','dot','multiply']:
 for v,isa in [('scalar','-mavx'),('simd','-march=native')]:
  p=B/f'{k}_{v}.c';p.write_text((R/f'src/{k}_scalar.c').read_text().replace('_scalar','_'+v));obj=B/f'{k}_{v}.o';objects.append(obj)
  run(common+['-ffast-math',isa,'-fopt-info-vec-all='+str(B/f'{k}_{v}.vec'),'-c',p,'-o',obj])
  with (B/f'{k}_{v}.asm').open('w') as f:run(['objdump','-d',obj],stdout=f)
 shutil.copy2(R/f'src/{k}_main.c',B/f'{k}_main.c')
 run(common+[B/f'{k}_main.c',B/f'{k}_scalar.o',B/f'{k}_simd.o',B/'benchmark.o','-lm','-o',B/k])
run(common+[R/'tests/correctness.c',*objects,B/'benchmark.o','-lm','-o',B/'correctness']);run([B/'correctness'])
meta={'sizes':[32768,1048576,8388608],'trials':15,'warmups':5,'cpu':min(os.sched_getaffinity(0)),'flags':{'avx':'-O3 -ffast-math -ffp-contract=off -mavx','native':'-O3 -ffast-math -ffp-contract=off -march=native'},'notes':'Both implementations auto-vectorized from identical loops; symbols scalar/simd are harness slots for AVX/native, not actual scalar/vector distinction. Alternating order within each trial, same allocated arrays, 64-byte aligned, no tails, single-call timing. No frequency isolation.','commands':[]}
(O/'metadata.json').write_text(json.dumps(meta,indent=2));print(O,flush=True)
for k in ['axpy','dot','multiply']:
 cmd=['taskset','-c',str(min(os.sched_getaffinity(0))),B/k,'--sizes','1048576,32768,8388608','--trials','15','--warmups','5','--csv',O/f'{k}.csv'];print('Measuring',k,flush=True);run(cmd);meta['commands'].append(list(map(str,cmd)))
(O/'metadata.json').write_text(json.dumps(meta,indent=2));shutil.copy2(__file__,O/'run.py')
print('Complete',flush=True)
