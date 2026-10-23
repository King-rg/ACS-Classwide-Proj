"""Run every Project 2 study without changing machine policy."""
from pathlib import Path
import argparse,datetime,json,csv,subprocess,os,random,hashlib,shutil
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--profile',choices=['quick','full'],default='quick');a=p.parse_args()
trials,ms=(3,15) if a.profile=='quick' else (7,100)
O=ROOT/'output'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');O.mkdir(parents=True)
subprocess.run(['make','-C',str(ROOT)],check=True)
allowed=sorted(os.sched_getaffinity(0));cpus=[];cores=set()
# Prefer P-core PMU membership when this hybrid Linux host exposes it.
def parse_set(s):
 out=set()
 for part in s.strip().split(','):
  if '-' in part:x,y=map(int,part.split('-'));out.update(range(x,y+1))
  elif part:out.add(int(part))
 return out
pmu=Path('/sys/bus/event_source/devices/cpu_core/cpus');preferred=parse_set(pmu.read_text()) if pmu.exists() else set(allowed)
for cpu in allowed:
 if cpu not in preferred:continue
 topology=Path(f'/sys/devices/system/cpu/cpu{cpu}/topology');key=((topology/'physical_package_id').read_text(),(topology/'core_id').read_text())
 if key not in cores:cores.add(key);cpus.append(cpu)
assert cpus;primary=cpus[0];cases=[]
def case(study,mode,span,spacing=64,block=8,reads=100,random_access=1,huge=0,streams=1,threads=1):
 cases.append(dict(study=study,mode=mode,bytes=span,spacing=spacing,block=block,read_pct=reads,random=random_access,huge=huge,streams=streams,threads=threads))
KiB=1024;MiB=1024**2
sizes=[4*KiB,16*KiB,32*KiB,48*KiB,64*KiB,256*KiB,512*KiB,1*MiB,2*MiB,8*MiB,24*MiB,48*MiB,96*MiB,192*MiB]
if a.profile=='full':sizes=sorted(set(sizes+[8*KiB,96*KiB,128*KiB,768*KiB,1280*KiB,4*MiB,16*MiB,32*MiB,64*MiB,128*MiB]))
for n in sizes:
 for order in [0,1]:case('working_set','latency',n,random_access=order)
for space in [64,256,1024]:
 for order in [0,1]:case('pattern_latency','latency',96*MiB,spacing=space,random_access=order)
for block in [8,64,256,1024]:
 for gap in [1,4]:
  for order in [0,1]:case('pattern_bandwidth','bandwidth',96*MiB,spacing=block*gap,block=block,random_access=order)
for reads in [100,70,50,0]:
 for order in [0,1]:case('mix','bandwidth',96*MiB,spacing=1024,block=1024,reads=reads,random_access=order)
for threads in sorted(set([1,min(2,len(cpus)),min(4,len(cpus)),min(6,len(cpus))])):
 case('intensity_threads','latency',96*MiB,threads=threads)
for streams in [1,2,4,8,16]:case('intensity_streams','latency',96*MiB,streams=streams)
for n in [4*MiB,16*MiB,64*MiB,192*MiB]:
 for order in [0,1]:
  for huge in [0,1]:case('tlb','latency',n,spacing=4096,random_access=order,huge=huge)
for n in [32*KiB,192*MiB]:case('pitfall','bandwidth',n,spacing=1024,block=1024,random_access=0)
caches=[]
for f in sorted(Path(f'/sys/devices/system/cpu/cpu{primary}/cache').glob('index*')):
 if (f/'type').read_text().strip()=='Instruction':continue
 s=(f/'size').read_text().strip();size=int(s[:-1])*(1024 if s.endswith('K') else 1024**2)
 caches.append(dict(level=int((f/'level').read_text()),bytes=size,shared=(f/'shared_cpu_list').read_text().strip()))
def read(path):
 p=Path(path);return p.read_text().strip() if p.exists() else None
meta=dict(profile=a.profile,trials=trials,target_ms=ms,cpus=cpus,caches=caches,started=datetime.datetime.now(datetime.timezone.utc).isoformat(),compiler=subprocess.check_output(['cc','--version'],text=True),kernel=subprocess.check_output(['uname','-a'],text=True),lscpu=subprocess.check_output(['lscpu'],text=True),meminfo=read('/proc/meminfo'),governor=read(f'/sys/devices/system/cpu/cpu{primary}/cpufreq/scaling_governor'),smt=read('/sys/devices/system/cpu/smt/active'),perf_event_paranoid=read('/proc/sys/kernel/perf_event_paranoid'),transparent_hugepage=read('/sys/kernel/mm/transparent_hugepage/enabled'),numa_maps_policy='Anonymous mappings first-touched by each pinned worker; default NUMA policy; placement not independently measured.',cases=cases,commands=[])
(O/'source').mkdir();shutil.copy2(ROOT/'src/memory_bench.c',O/'source/memory_bench.c');shutil.copy2(ROOT/'Makefile',O/'source/Makefile');shutil.copy2(ROOT/'PLAN.md',O/'source/PLAN.md')
for f in Path(__file__).parent.glob('*.py'):shutil.copy2(f,O/'source'/f.name)
(O/'metadata.json').write_text(json.dumps(meta,indent=2));print(O,flush=True)
random.Random(4320).shuffle(cases)
with (O/'raw.csv').open('w') as out:
 writer=None
 for i,c in enumerate(cases):
  for trial in range(trials):
   cmd=[str(ROOT/'build/memory_bench'),c['mode'],str(c['bytes']),str(c['spacing']),str(c['block']),str(c['read_pct']),str(c['random']),str(c['huge']),str(c['streams']),str(ms),','.join(map(str,cpus[:c['threads']]))]
   result=subprocess.run(cmd,check=True,capture_output=True,text=True);r=json.loads(result.stdout);assert r['check']=='pass'
   row={**c,'trial':trial,**r};meta['commands'].append(cmd)
   if writer is None:writer=csv.DictWriter(out,fieldnames=row.keys());writer.writeheader()
   writer.writerow(row);out.flush()
  print(f'{i+1}/{len(cases)} {c["study"]} {c["bytes"]//1024} KiB',flush=True)
meta['finished']=datetime.datetime.now(datetime.timezone.utc).isoformat();meta['raw_sha256']=hashlib.sha256((O/'raw.csv').read_bytes()).hexdigest();(O/'metadata.json').write_text(json.dumps(meta,indent=2))
(ROOT/'output/LATEST').write_text(O.name+'\n');print('COMPLETE '+str(O),flush=True)
