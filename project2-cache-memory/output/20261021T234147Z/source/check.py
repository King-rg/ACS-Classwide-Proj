from pathlib import Path
import subprocess,json,os
R=Path(__file__).resolve().parents[1];cpu=str(min(os.sched_getaffinity(0)));exe=R/'build/memory_bench'
cases=[['latency','32768','64','8','100','1','0',str(s),'2',cpu] for s in [1,2,8]]
cases += [['bandwidth','65536',str(sp),str(b),str(r),str(random),'0','1','2',cpu] for sp,b in [(64,8),(256,64),(1024,1024)] for r in [0,50,70,100] for random in [0,1]]
cases += [['latency','4194304','4096','8','100','1',str(h),'1','2',cpu] for h in [0,1]]
for c in cases:
 r=json.loads(subprocess.check_output([str(exe),*c],text=True));assert r['check']=='pass' and r['elapsed_ns']>0
 if c[6]=='0':assert r['huge_bytes']==0
bad=subprocess.run([str(exe),'latency','4096','0','8','100','1','0','1','2',cpu],capture_output=True);assert bad.returncode!=0
print(f'{len(cases)} correctness cases passed; invalid input rejected.')
