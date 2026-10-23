"""Bounded FIO studies against one newly-created disposable regular file only."""
from pathlib import Path
import argparse,os,subprocess,json,datetime,shutil,random,csv,hashlib,signal
signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt("Terminated")))
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--profile',choices=['quick','full'],default='full');a=p.parse_args()
full=a.profile=='full'; trials=5 if full else 3; duration=10 if full else 1; size=2**30
O=Path(os.environ['REPORT_RUN_DIR']) if os.environ.get('REPORT_RUN_DIR') else R/'output'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');O.mkdir(parents=True,exist_ok=True)
(O/'configs').mkdir();(O/'raw').mkdir();(O/'source').mkdir()
for f in (R/'scripts').glob('*.py'):shutil.copy2(f,O/'source'/f.name)
shutil.copy2(R/'PLAN.md',O/'source'/'PLAN.md')
fio=os.environ.get('REPORT_FIO') or shutil.which('fio') or str(R/'tools/local/usr/bin/fio'); env=os.environ.copy();env['LD_LIBRARY_PATH']=str(R/'tools/local/usr/lib/x86_64-linux-gnu')+':'+env.get('LD_LIBRARY_PATH','')
def cmd(args):return subprocess.check_output(args,env=env,text=True,stderr=subprocess.STDOUT)
assert cmd([fio,'--version']).strip().startswith('fio-')
assert shutil.disk_usage(R).free>size+5*2**30,'Need 6 GiB free'
target=O/'disposable.bin'
cpu=min(os.sched_getaffinity(0))
def read(path):
 try:return Path(path).read_text().strip()
 except OSError:return None
def temps():return {str(f):read(f) for f in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')}
meta={'profile':a.profile,'trials':trials,'runtime_s':duration,'file_bytes':size,'cpu':cpu,'fio':cmd([fio,'--version']).strip(),'os':cmd(['uname','-a']),'cpu_info':cmd(['lscpu']),'storage':cmd(['lsblk','-o','NAME,MODEL,SIZE,TRAN,ROTA,FSTYPE,MOUNTPOINTS']),'filesystem':cmd(['findmnt','-T',str(R)]),'governor':read(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor'),'smt':read('/sys/devices/system/cpu/smt/active'),'temperature_start':temps(),'data_pattern':'refill_buffers=1, buffer_compress_percentage=0; pseudo-random data','state':'Existing mounted system SSD; no erase, trim or whole-device conditioning','duration_note':'Short burst profile; not steady-state certification','commands':[]}
(O/'metadata.json').write_text(json.dumps(meta,indent=2))
def run(name,opts):
 assert target.is_file() and not target.is_symlink()
 base=dict(filename=str(target),ioengine='libaio',direct=1,bs=4096,iodepth=1,numjobs=1,size=size,allow_file_create=0,thread=1,cpus_allowed=cpu,refill_buffers=1,buffer_compress_percentage=0,randrepeat=1,randseed=1234,group_reporting=1,percentile_list='50:95:99:99.9',lat_percentiles=1)
 base.update(opts)
 conf=O/'configs'/f'{name}.fio';conf.write_text('[global]\n'+'\n'.join(f'{k}={v}' for k,v in base.items())+f'\n\n[{name}]\n')
 args=[fio,str(conf),'--output-format=json','--output='+str(O/'raw'/f'{name}.json')];meta['commands'].append(args)
 subprocess.run(args,env=env,check=True,stdout=subprocess.DEVNULL)
 j=json.loads((O/'raw'/f'{name}.json').read_text());assert all(x['error']==0 for x in j['jobs']),name
 return j['jobs'][0]
rows=[]
owned=False
try:
 fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_NOFOLLOW,0o600)
 owned=True
 try:os.posix_fallocate(fd,0,size)
 finally:os.close(fd)
 # Complete file initialization and CRC write/read validation, outside timing.
 run('initialize',dict(rw='write',bs=131072,iodepth=16,end_fsync=1))
 run('verify',dict(rw='write',size=16*2**20,verify='crc32c',do_verify=1,verify_fatal=1,end_fsync=1))
 cases=[]
 def add(study,rw,bs=4096,qd=1,span=size,direct=1,mix=100):cases.append(dict(study=study,rw=rw,bs=bs,qd=qd,span=span,direct=direct,mix=mix))
 for rw,bs in [('randread',4096),('randwrite',4096),('read',131072),('write',131072)]:add('baseline',rw,bs)
 for rw in ['randread','read']:
  for bs in [4096,16384,32768,65536,131072,262144]:add('block',rw,bs,16)
 for mix in [100,70,50,0]:add('mix','randrw',4096,16,mix=mix)
 for qd in ([1,2,4,8,16,32,64,128,256] if full else [1,2,4,8,16,32,64]):add('queue','randread',4096,qd)
 for span in [16*2**20,64*2**20,256*2**20,size]:add('range','randread',4096,16,span)
 for direct in [0,1]:add('pitfall','read',131072,1,16*2**20,direct)
 jobs=[(trial,c) for trial in range(trials) for c in cases];random.Random(4320).shuffle(jobs)
 for i,(trial,c) in enumerate(jobs):
  name=f'{i:03d}_{c["study"]}_{trial}'
  if c['study']=='pitfall' and not c['direct']:
   run(name+'_warm',dict(rw='read',direct=0,size=c['span'],bs=c['bs']))
  j=run(name,dict(rw=c['rw'],bs=c['bs'],iodepth=c['qd'],size=c['span'],direct=c['direct'],rwmixread=c['mix'],time_based=1,runtime=duration,invalidate=0 if not c['direct'] else 1))
  row=dict(c,trial=trial,name=name)
  active=[j[d] for d in ['read','write'] if j[d]['total_ios']]
  total=sum(x['total_ios'] for x in active);row['ios']=total;row['iops']=sum(x['iops'] for x in active);row['mib_s']=sum(x['bw_bytes'] for x in active)/2**20
  row['lat_us']=sum(x['lat_ns']['mean']*x['total_ios'] for x in active)/total/1000
  for d in ['read','write']:
   for pct in [50,95,99,99.9]:row[f'{d}_p{pct}_us']=j[d].get('lat_ns',{}).get('percentile',{}).get(f'{pct:.6f}',float('nan'))/1000
  row['little_law_inflight']=row['iops']*row['lat_us']/1e6
  row['depth_distribution']=json.dumps(j['iodepth_level']);rows.append(row)
  with (O/'raw.csv').open('a',newline='') as stream:
   writer=csv.DictWriter(stream,fieldnames=row);
   if len(rows)==1:writer.writeheader()
   writer.writerow(row)
  if i%10==0:print(f'{i+1}/{len(jobs)} trials',flush=True)
 # Bounded write burst with one-second bandwidth and mean-latency logs.
 run('state',dict(rw='write',bs=131072,iodepth=16,time_based=1,runtime=20 if full else 6,write_bw_log=str(O/'state'),write_lat_log=str(O/'state'),log_avg_msec=1000,end_fsync=1))
 with (O/'raw.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 meta['temperature_end']=temps();meta['validation']='FIO CRC32C write/read verification passed; all timed jobs returned error=0';meta['observations']=len(rows)
 print(O,flush=True)
finally:
 if owned:target.unlink(missing_ok=True)
 meta['observations']=len(rows);meta['raw_sha256']=hashlib.sha256((O/'raw.csv').read_bytes()).hexdigest() if (O/'raw.csv').exists() else None
 (O/'metadata.json').write_text(json.dumps(meta,indent=2))
