#!/usr/bin/env python3
"""CPU0 frequency experiment. Default is read-only preflight; --run requires root.
No voltage, turbo-enable, power-limit, fan, or thermal-protection writes.
"""
import argparse, datetime, hashlib, json, os, pathlib, signal, struct, subprocess, time
P=pathlib.Path
ROOT=P(__file__).resolve().parents[1]
SYS=P('/sys/devices/system/cpu')
POL=[SYS/'cpufreq'/f'policy{i}' for i in (0,1)]
STEPS=[1500000,2000000,2500000,3000000,3500000,4000000,4500000,5000000]
def read(p): return P(p).read_text().strip()
def write(p,v): P(p).write_text(str(v))
def save(p,v): p.write_text(json.dumps(v,indent=2)+'\n')
def temperatures():
 h=next(h for h in P('/sys/class/hwmon').glob('hwmon*') if read(h/'name')=='coretemp')
 return {read(t.with_name(t.name.replace('_input','_label'))):{'c':int(read(t))/1000,'critical_c':int(read(t.with_name(t.name.replace('_input','_crit'))))/1000} for t in h.glob('temp*_input')}
def throttles():
 return {f'{i}/{t.name}':int(read(t)) for i in (0,1) for t in (SYS/f'cpu{i}'/'thermal_throttle').glob('*_throttle_count')}
def proc_cpu():
 return {l.split()[0]:list(map(int,l.split()[1:])) for l in P('/proc/stat').read_text().splitlines() if l.startswith(('cpu0 ','cpu1 '))}
def sibling_busy(old,new):
 a,b=old['cpu1'],new['cpu1'];d=[y-x for x,y in zip(a,b)];total=sum(d[:8]);return (total-d[3]-d[4])/total if total else 0

def policy_values(expected):
 return {name:{k:read(P(name)/k) for k in fields} for name,fields in expected.items()}
def wait_policy_values(expected,timeout=1.,stable_samples=3):
 """CPUFreq QoS writes queue asynchronous work; require exact, stable readback.
 No rounding/clamping tolerance: a persistent mismatch remains a hard stop.
 """
 start=time.monotonic();history=[];matching=0
 while True:
  observed=policy_values(expected);elapsed=time.monotonic()-start
  history.append({'elapsed_s':elapsed,'observed':observed})
  matching=matching+1 if observed==expected else 0
  if matching>=stable_samples or elapsed>=timeout:
   return {'verified':matching>=stable_samples,'expected':expected,'observed':observed,'elapsed_s':elapsed,'history':history}
  time.sleep(.02)
def log_control(out,record):
 with (out/'control_requests.jsonl').open('a') as f:
  f.write(json.dumps(record)+'\n');f.flush()
def apply_frequency(khz,snapshot,out):
 expected={name:{**values,'scaling_min_freq':str(khz),'scaling_max_freq':str(khz)} for name,values in snapshot['policies'].items()}
 log_control(out,{'phase':'request','requested_khz':khz,'expected':expected,'before':policy_values(expected)})
 for p in POL:write(p/'scaling_min_freq',read(p/'cpuinfo_min_freq'))
 for p in POL:write(p/'scaling_max_freq',khz)
 for p in POL:write(p/'scaling_min_freq',khz)
 accepted=wait_policy_values(expected)
 log_control(out,{'phase':'readback','requested_khz':khz,**accepted})
 if not accepted['verified']:
  raise RuntimeError('frequency request readback mismatch after settling: '+json.dumps({'requested_khz':khz,'expected':expected,'observed':accepted['observed']}))
 return accepted['observed']
def restore(snapshot):
 errors=[]
 for name,s in snapshot['policies'].items():
  p=P(name)
  try:
   write(p/'scaling_min_freq',read(p/'cpuinfo_min_freq'))
   write(p/'scaling_max_freq',s['scaling_max_freq'])
   write(p/'scaling_min_freq',s['scaling_min_freq'])
  except Exception as e: errors.append(str(e))
 try:
  settled=wait_policy_values(snapshot['policies'],timeout=2.)
  if not settled['verified']:errors.append('restore readback mismatch after settling: '+json.dumps(settled['observed']))
 except Exception as e:
  errors.append(str(e));settled=None
 return {'verified':not errors,'errors':errors,'readback':settled,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
def preflight():
 return {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cpu':0,'siblings':read(SYS/'cpu0/topology/thread_siblings_list'),'base_khz':int(read(POL[0]/'base_frequency')),
 'no_turbo':read(SYS/'intel_pstate/no_turbo'),'policies':{str(p):{k:read(p/k) for k in ['scaling_min_freq','scaling_max_freq','scaling_governor','energy_performance_preference']} for p in POL},
 'temperatures':temperatures(),'throttle_counters':throttles(),'core_perf_type':int(read('/sys/bus/event_source/devices/cpu_core/type')),'requested_steps_khz':STEPS,
 'notes':['Equal min/max is a request; hardware may deliver another clock.','SMT sibling remains online; >10% observed activity stops progression.','Short single-core test cannot establish maximum sustained stable frequency.','No global turbo, power, voltage, fan or thermal controls are modified.']}
def run(out):
 if os.geteuid()!=0: raise SystemExit('Use sudo for --run; default preflight never writes controls.')
 out.mkdir(parents=True,exist_ok=False)
 s=preflight();save(out/'original_settings.json',s)
 if s['siblings']!='0-1' or read(POL[0]/'scaling_driver')!='intel_pstate':raise RuntimeError('unexpected topology/driver')
 if not (SYS/'cpu1/online').exists() or read(SYS/'cpu1/online')!='1':raise RuntimeError('sibling must be online')
 max_khz=min(int(v['scaling_max_freq']) for v in s['policies'].values())
 steps=[x for x in STEPS if x<=max_khz and (s['no_turbo']=='0' or x<=s['base_khz'])]
 if not steps:raise RuntimeError('no requested steps within existing limits')
 snapshot=out/'source_snapshot';snapshot.mkdir()
 for name in ('frequency_sweep.py','frequency_worker.cpp','analyze_frequency.py','compute.cpp','intrinsics.cpp','kernels.hpp','run_frequency_sweep.sh'):
  source=ROOT/'experiments'/name;(snapshot/name).write_bytes(source.read_bytes())
 save(out/'provenance.json',{'uname':list(os.uname()),'cpu_model':next(l for l in P('/proc/cpuinfo').read_text().splitlines() if l.startswith('model name')),'compiler':subprocess.check_output(['g++','--version'],text=True).splitlines()[0],'sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [ROOT/'build/frequency/worker',*[ROOT/'experiments'/n for n in ('frequency_sweep.py','frequency_worker.cpp','compute.cpp','intrinsics.cpp')]]}})
 t0=time.monotonic();worker=None;msr=None;status={'state':'running','steps_khz':steps};save(out/'status.json',status)
 def interrupt(signum,frame): raise InterruptedError(f'signal {signum}')
 for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP,signal.SIGALRM):signal.signal(sig,interrupt)
 signal.alarm(120)
 def sample():
  ts=time.monotonic();a,m=struct.unpack('<Q',os.pread(msr,8,0xe8))[0],struct.unpack('<Q',os.pread(msr,8,0xe7))[0]
  return {'elapsed_s':ts-t0,'aperf':a,'mperf':m,'temperatures':temperatures(),'throttles':throttles(),'proc':proc_cpu()}
 try:
  msr=os.open('/dev/cpu/0/msr',os.O_RDONLY)
  first=sample();last=first;critical=min(v['critical_c'] for v in first['temperatures'].values());limit=min(90.,critical-10.)
  save(out/'plan.json',{'steps_khz':steps,'stop_temperature_c':limit,'interval_s':0.75,'warmup_intervals':1,'measured_intervals':3,'workloads':['compute','dot'],'cooldown_s':2,'timeout_s':120,'policy_readback':'Exact requested min/max, governor and EPP on both siblings; up to 1 second to settle, 3 matching observations 20 ms apart. No rounding tolerance.','aperf_meaning':'CPU0 delivered cycles per wall time; includes idle. APERF/MPERF ratio is also recorded; no assumed nominal conversion.','perf_meaning':'User core cycles / thread CPU time = execution MHz, measured in worker.','compiler_flags':'-O3 -mavx2 -mfma (compute only); ffp-contract=off; no fast-math','sources':['https://www.kernel.org/doc/html/latest/admin-guide/pm/intel_pstate.html','https://cdn.kernel.org/doc/html/latest/hwmon/coretemp.html']})
  with (out/'telemetry.jsonl').open('w',buffering=1) as telemetry,(out/'measurements.jsonl').open('w',buffering=1) as results:
   for khz in steps:
    # Abort before each new step if the package is already hot or counters advanced.
    before=sample()
    if max(v['c'] for v in before['temperatures'].values())>=limit:raise RuntimeError('temperature threshold before step')
    if any(before['throttles'][k]>first['throttles'][k] for k in first['throttles']):raise RuntimeError('thermal throttle counter advanced')
    accepted=apply_frequency(khz,s,out)
    print(f'Request {khz/1e6:.1f} GHz',flush=True)
    for mode in ('compute','dot'):
     log=out/f'{khz}-{mode}.jsonl';err=out/f'{khz}-{mode}.stderr';start=sample();last=start
     with log.open('w') as f,err.open('w') as e:
      worker=subprocess.Popen([str(ROOT/'build/frequency/worker'),mode,str(s['core_perf_type'])],stdout=f,stderr=e,start_new_session=True)
      while worker.poll() is None:
       time.sleep(.25);v=sample();dt=v['elapsed_s']-last['elapsed_s'];da=v['aperf']-last['aperf'];dm=v['mperf']-last['mperf']
       if dt<=0 or da<0 or dm<=0:raise RuntimeError('invalid APERF/MPERF measurement')
       row={'requested_khz':khz,'accepted_policies':accepted,'workload':mode,'elapsed_s':v['elapsed_s'],'delivered_mhz_wall':da/dt/1e6,'aperf_mperf_ratio':da/dm,'package_max_c':max(x['c'] for x in v['temperatures'].values()),'sibling_busy':sibling_busy(last['proc'],v['proc']),'throttle_counters':v['throttles']}
       row['current_policies']=policy_values(accepted)
       telemetry.write(json.dumps(row)+'\n');last=v
       if row['current_policies']!=accepted:raise RuntimeError('frequency policy drift during workload: '+json.dumps(row['current_policies']))
       if row['package_max_c']>=limit:raise RuntimeError('temperature margin reached')
       if any(v['throttles'][k]>first['throttles'][k] for k in first['throttles']):raise RuntimeError('thermal throttle counter advanced')
       if time.monotonic()-t0>120:raise RuntimeError('120-second watchdog limit')
       if time.monotonic()-t0-start['elapsed_s']>5:raise RuntimeError('workload timeout')
     if worker.returncode:raise RuntimeError(f'worker failed: {err.read_text()}')
     worker=None
     rows=[json.loads(l) for l in log.read_text().splitlines()]
     if len(rows)!=4:raise RuntimeError('missing intervals')
     measured=[]
     for r in rows:
      r.update(requested_khz=khz,accepted_policies=accepted,workload=mode,effective_mhz=r['cycles']/r['cpu_s']/1e6,gflops=r['operations']/r['wall_s']/1e9,utilization=r['cpu_s']/r['wall_s'])
      results.write(json.dumps(r)+'\n')
      if not r['warmup']:measured.append(r)
     if any(r['utilization']<.85 for r in measured):raise RuntimeError('CPU scheduling interference: utilization below 85%')
     if all(r['effective_mhz']<khz/1000*.90 for r in measured):raise RuntimeError('sustained clock shortfall >10%; cause unknown unless thermal counter/temperature evidence identifies it')
     active=[json.loads(l) for l in (out/'telemetry.jsonl').read_text().splitlines() if json.loads(l)['elapsed_s']>=start['elapsed_s']]
     if sum(r['sibling_busy'] for r in active)/len(active)>.10:raise RuntimeError('SMT sibling activity above 10%')
    # Remove experiment floor between steps; do not hold a high minimum while idle.
    for p in POL:write(p/'scaling_min_freq',read(p/'cpuinfo_min_freq'))
    time.sleep(2)
   status={'state':'complete','note':'Completed short bounded sweep; not a maximum stable frequency certification.'}
 except BaseException as e:
  status={'state':'stopped','reason':str(e),'exception':type(e).__name__};print(f'Stopped: {e}',flush=True)
 finally:
  # Ignore repeat termination while restoring. SIGKILL/power loss cannot run finally;
  # --restore original_settings.json is the explicit recovery path.
  signal.alarm(0)
  for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP,signal.SIGALRM):signal.signal(sig,signal.SIG_IGN)
  if worker is not None and worker.poll() is None:
   try:
    os.killpg(worker.pid,signal.SIGTERM)
    try:worker.wait(timeout=2)
    except subprocess.TimeoutExpired:os.killpg(worker.pid,signal.SIGKILL);worker.wait()
   except ProcessLookupError:pass
  if msr is not None:os.close(msr)
  restoration=restore(s);save(out/'restoration.json',restoration)
  status['elapsed_s']=time.monotonic()-t0;status['restoration_verified']=restoration['verified'];save(out/'status.json',status)
  print(json.dumps(status,indent=2),flush=True)
  # Give the invoking user access without recursively changing unrelated paths.
  if 'SUDO_UID' in os.environ:
   uid,gid=int(os.environ['SUDO_UID']),int(os.environ['SUDO_GID'])
   for p in [*out.rglob('*'),out]:os.chown(p,uid,gid)
  if not restoration['verified']:raise RuntimeError('RESTORATION FAILED: '+str(restoration))
 return 0 if status['state']=='complete' else 2
if __name__=='__main__':
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('--run',action='store_true');a.add_argument('--output',type=P);a.add_argument('--restore',type=P);args=a.parse_args()
 if args.restore:
  if os.geteuid()!=0:raise SystemExit('restore requires sudo')
  r=restore(json.loads(args.restore.read_text()));print(json.dumps(r,indent=2));raise SystemExit(0 if r['verified'] else 1)
 elif args.run:
  if not args.output:raise SystemExit('--output required')
  raise SystemExit(run(args.output.resolve()))
 else:print(json.dumps(preflight(),indent=2))
