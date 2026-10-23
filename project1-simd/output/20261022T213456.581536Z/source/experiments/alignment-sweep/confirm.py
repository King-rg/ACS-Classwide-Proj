from pathlib import Path
import subprocess,os,json,csv,random
R=Path(__file__).resolve().parents[2];O=R/'output/alignment-sweep'/(R/'output/alignment-sweep/LATEST').read_text().strip();D=O/'confirmation';D.mkdir(exist_ok=True)
subprocess.run(['make','-f','build.mk','AUTO=1','all','check'],cwd=R,check=True)
cpu=min(os.sched_getaffinity(0));jobs=[(k,b,t,o) for k,b in [('axpy',32768),('dot',16777216),('multiply',8388608)] for t,o in [(0,0),(0,1),(7,0),(7,1)]];random.Random(77).shuffle(jobs);commands=[]
for k,b,t,o in jobs:
 cmd=['taskset','-c',str(cpu),str(R/'build/gcc/avx-auto'/k),'--sizes',str(b+t),'--offset',str(o),'--trials','15','--warmups','5','--csv',str(D/f'{k}-{b}-{t}-{o}.csv')];subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL);commands.append(cmd)
 assert all(r['correct']=='pass' for r in csv.DictReader(open(cmd[-1])))
 print(k,b,t,o,flush=True)
(D/'commands.json').write_text(json.dumps(commands,indent=2))
