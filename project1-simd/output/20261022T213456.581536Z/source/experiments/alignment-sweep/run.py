import os
from pathlib import Path
import csv,json,datetime,subprocess,os,random,shutil
R=Path(__file__).resolve().parents[2];O=R/'output/alignment-sweep'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');O=Path(os.environ.get('REPORT_RUN_DIR',str(O)));O.mkdir(parents=True);(O/'raw').mkdir();(O/'source').mkdir()
bases=[32,128,512,2048,8192,32768,131072,524288,2097152,4194304,8388608,16777216]
(O/'PLAN.md').write_text('Before acquisition: compare clean, shifted, tail+7, and combined conditions across cache/DRAM spans. Expect alignment penalties to vary by regime and tail cost per element to diminish with size. Retain historical results separately: their addresses and lengths were not clean controls. Use single-call timing and original input generation to match the previous working-set protocol; tiny cases remain overhead-sensitive.\n')
subprocess.run(['make','-f','build.mk','AUTO=1','all','check'],cwd=R,check=True,stdout=subprocess.DEVNULL)
for f in (R/'src').glob('*'):shutil.copy2(f,O/'source'/f.name)
shutil.copy2(R/'Makefile',O/'source/Makefile');shutil.copy2(__file__,O/'source/run.py')
cpu=min(os.sched_getaffinity(0));jobs=[(k,b,t,o) for k in ['axpy','dot','multiply'] for b in bases for t,o in [(0,0),(0,1),(7,0),(7,1)]];random.Random(4320).shuffle(jobs)
meta={'cpu':cpu,'trials':15,'warmups':5,'calls':1,'bases':bases,'compiler':subprocess.check_output(['gcc','--version'],text=True),'kernel_flags':'-O3 -mavx -ffast-math -ffp-contract=off; scalar disables vectorization','historical':'output/auto-extended','commands':[],'notes':'Same original random inputs and single-call protocol; cases shuffled; binary rebuilt using integrated flow. No frequency control.'};rows=[]
for i,(k,b,t,o) in enumerate(jobs):
 f=O/'raw'/f'{k}-{b}-{t}-{o}.csv';cmd=['taskset','-c',str(cpu),str(R/'build/gcc/avx-auto'/k),'--sizes',str(b+t),'--offset',str(o),'--trials','15','--warmups','5','--csv',str(f)]
 subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL);meta['commands'].append(cmd)
 for r in csv.DictReader(f.open()):
  assert r['correct']=='pass' and int(r['calls'])==1
  r.update(base=b,tail=t,condition=('combined' if t and o else 'tail' if t else 'shifted' if o else 'clean'));rows.append(r)
 if i%12==0:print(f'{i+1}/{len(jobs)} cases',flush=True)
with (O/'raw.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
meta['observations']=len(rows);(O/'metadata.json').write_text(json.dumps(meta,indent=2));print(O,flush=True)
