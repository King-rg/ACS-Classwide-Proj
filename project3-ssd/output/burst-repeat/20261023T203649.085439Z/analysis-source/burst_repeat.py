"""Repeated, bounded sequential-write time series on an owned regular file."""
from block_repeat import ROOT, save_json, read_text, temps, table, fio_environment
from pathlib import Path
import argparse, csv, datetime, fcntl, hashlib, json, os, shutil, signal, subprocess, time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
TRIALS, DURATION, IDLE, SIZE = 5, 60, 30, 16*2**30


def render(out):
    meta=json.loads((out/'metadata.json').read_text());assert meta['complete']
    assert not (out/'disposable.bin').exists()
    traces=[];summary=[]
    for trial in range(1,TRIALS+1):
        raw=json.loads((out/'raw'/f'burst{trial}.json').read_text());j=raw['jobs'][0];d=j['write'];opts=raw['global options']
        assert not j['error'] and d['runtime']>=DURATION*1000 and not j['read']['total_ios']
        assert int(opts['direct'])==1 and int(opts['bs'])==131072 and int(opts['iodepth'])==16
        assert int(opts['size'])==SIZE and int(opts['log_avg_msec'])==250
        assert np.isclose(d['bw_bytes'],d['io_bytes']/(d['runtime']/1000),rtol=1e-6)
        assert d['io_bytes']==d['total_ios']*131072
        stats=dict(trial=trial,written_gib=d['io_bytes']/2**30,mean_mib_s=d['bw_bytes']/2**20,mean_lat_us=d['lat_ns']['mean']/1000)
        for metric,scale in [('bw',1/1024),('lat',1/1000)]:
            files=list((out/'logs').glob(f'burst{trial}_{metric}*.log'));assert len(files)==1
            data=np.loadtxt(files[0],delimiter=',',ndmin=2)
            assert np.all(np.isfinite(data[:,:3])) and np.all(data[:,2]==1)
            assert np.all(np.diff(data[:,0])>0) and data[-1,0]>=59000
            widths=np.diff(np.r_[0,data[:,0]])
            for row,width in zip(data,widths):
                traces.append(dict(trial=trial,metric=metric,end_s=row[0]/1000,window_ms=width,value=row[1]*scale,partial=width<200))
            # Time-weighted bandwidth for fixed early/late windows; no latency averaging across unequal I/O counts.
            if metric=='bw':
                starts=np.r_[0,data[:-1,0]]
                for label,a,b in [('first10',0,10000),('last10',50000,60000)]:
                    overlap=np.maximum(0,np.minimum(data[:,0],b)-np.maximum(starts,a))
                    stats[label+'_mib_s']=float(np.sum(data[:,1]*scale*overlap)/sum(overlap))
        summary.append(stats)
    for name in ['initialize','verify']:
        assert all(not j['error'] for j in json.loads((out/'raw'/f'{name}.json').read_text())['jobs'])
    table(out/'time-series.csv',traces);table(out/'summary.csv',summary)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'xtick.labelsize':9,'ytick.labelsize':9,
        'axes.spines.top':False,'axes.spines.right':False,'axes.axisbelow':True,'legend.frameon':False,'pdf.fonttype':42})
    # Align nominal 250 ms windows; require all five trials for every plotted point.
    averaged=[]
    for metric in ['bw','lat']:
        aligned={}
        for trial in range(1,TRIALS+1):
            rr=[r for r in traces if r['trial']==trial and r['metric']==metric and not r['partial']]
            bins={}
            for r in rr:
                index=round(r['end_s']/.25)
                assert abs(r['end_s']-index*.25)<=.005 and index not in bins
                bins[index]=r['value']
            aligned[trial]=bins
        common=set.intersection(*(set(bins) for bins in aligned.values()))
        for index in sorted(common):
            values=[aligned[t][index] for t in range(1,TRIALS+1)]
            averaged.append(dict(metric=metric,end_s=index*.25,trials=TRIALS,mean=float(np.mean(values))))
    common_times=set.intersection(*(set(r['end_s'] for r in averaged if r['metric']==m) for m in ['bw','lat']))
    averaged=[r for r in averaged if r['end_s'] in common_times]
    assert len(common_times)==239 and max(common_times)==59.75
    table(out/'averaged-time-series.csv',averaged)
    fig,axes=plt.subplots(2,1,figsize=(9,6),sharex=True,layout='constrained')
    for ax,metric,color,label in zip(axes,['bw','lat'],['#24649a','#bb6c16'],['Throughput (MiB/s)','Mean total I/O latency (µs)']):
        rr=[r for r in averaged if r['metric']==metric]
        ax.plot([r['end_s'] for r in rr],[r['mean'] for r in rr],color=color,lw=1.4)
        ax.set(xlim=(0,60),ylim=(0,None),xticks=list(range(0,61,10)),ylabel=label)
        ax.grid(axis='y',color='#dfe3e8',lw=.6)
    axes[1].set_xlabel('Time in write burst (s)')
    for ext in ['png','svg','pdf']:fig.savefig(out/f'fig7-write-burst.{ext}',dpi=360)
    plt.close(fig)
    hashes={str(f.relative_to(out)):hashlib.sha256(f.read_bytes()).hexdigest() for sub in ['raw','logs','configs'] for f in (out/sub).glob('*') if f.is_file()}
    save_json(out/'validation.json',dict(trials=TRIALS,measured_seconds=TRIALS*DURATION,log_window_ms=250,
        raw_json_settings_arithmetic_and_logs_passed=True,total_written_gib=sum(s['written_gib'] for s in summary),sha256=hashes))
    print('Validated and plotted: '+str(out),flush=True)


def acquire():
    env=fio_environment(ROOT);fio=env['REPORT_FIO'];cpu=min(os.sched_getaffinity(0))
    assert shutil.disk_usage(ROOT).free>SIZE+8*2**30
    out=ROOT/'output/burst-repeat'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    out.mkdir(parents=True)
    for sub in ['raw','logs','configs','source']:(out/sub).mkdir()
    for name in ['burst_repeat.py','block_repeat.py']:shutil.copy2(ROOT/'scripts'/name,out/'source'/name)
    shutil.copy2(ROOT.parent/'shared/project3.py',out/'source/shared-project3.py')
    (out/'protocol.txt').write_text('Five sequential 60-second write bursts, 30 seconds idle before each, no ramp period. One initialized 16 GiB regular file, repeated overwrites, 128 KiB blocks, direct I/O, QD 16, one pinned job. Nominal 250 ms throughput and total-latency windows, all raw samples retained. No device reset or claim of identical initial device state between bursts. Individual traces preserve transient timing.\n')
    def command(args):return subprocess.check_output(args,env=env,text=True,stderr=subprocess.STDOUT)
    meta=dict(complete=False,trials=TRIALS,runtime_s=DURATION,idle_s=IDLE,file_bytes=SIZE,cpu=cpu,
        fio=command([fio,'--version']).strip(),os=command(['uname','-a']),cpu_info=command(['lscpu']),
        storage=command(['lsblk','-o','NAME,MODEL,SIZE,TRAN,ROTA,FSTYPE,MOUNTPOINTS']),filesystem=command(['findmnt','-T',str(ROOT)]),
        temperature_start=temps(),commands=[],completed=0)
    target=out/'disposable.bin';owned=False;start=time.monotonic();child=None
    def run(name,options):
        nonlocal child
        assert target.is_file() and not target.is_symlink()
        base=dict(filename=str(target),ioengine='libaio',direct=1,bs=131072,iodepth=16,numjobs=1,size=SIZE,
            allow_file_create=0,thread=1,cpus_allowed=cpu,refill_buffers=1,buffer_compress_percentage=0,
            group_reporting=1,lat_percentiles=1,percentile_list='50:95:99:99.9',rw='write')
        base.update(options)
        conf=out/'configs'/f'{name}.fio';conf.write_text('[global]\n'+'\n'.join(f'{k}={v}' for k,v in base.items())+f'\n\n[{name}]\n')
        args=[fio,str(conf),'--output-format=json','--output='+str(out/'raw'/f'{name}.json')];meta['commands'].append(args)
        child=subprocess.Popen(args,env=env,stdout=subprocess.DEVNULL)
        with (out/'temperatures.jsonl').open('a') as f:
            while child.poll() is None:
                f.write(json.dumps(dict(phase=name,elapsed_s=time.monotonic()-start,temperatures=temps()))+'\n');f.flush();time.sleep(1)
        assert child.returncode==0;child=None
        j=json.loads((out/'raw'/f'{name}.json').read_text())['jobs'];assert len(j)==1 and not j[0]['error'];return j[0]
    print('Run directory: '+str(out),flush=True);save_json(out/'metadata.json',meta)
    try:
        fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_NOFOLLOW,0o600);owned=True
        try:os.posix_fallocate(fd,0,SIZE)
        finally:os.close(fd)
        run('initialize',dict(end_fsync=1))
        run('verify',dict(size=16*2**20,verify='crc32c',do_verify=1,verify_fatal=1,end_fsync=1))
        for trial in range(1,TRIALS+1):
            print(f'Idle {IDLE}s before trial {trial}/{TRIALS}',flush=True);time.sleep(IDLE)
            print(f'Starting 60-second trial {trial}/{TRIALS}',flush=True)
            prefix=str(out/'logs'/f'burst{trial}')
            run(f'burst{trial}',dict(time_based=1,runtime=DURATION,write_bw_log=prefix,write_lat_log=prefix,
                log_avg_msec=250,log_unix_epoch=0,end_fsync=1))
            meta['completed']=trial;save_json(out/'metadata.json',meta)
            print(f'Completed trial {trial}/{TRIALS}',flush=True)
        meta['complete']=True
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        if owned:target.unlink(missing_ok=True)
        meta.update(temperature_end=temps(),elapsed_s=time.monotonic()-start)
        save_json(out/'metadata.json',meta)
    render(out)
    (ROOT/'output/LATEST_BURST_REPEAT').write_text(str(out.relative_to(ROOT/'output'))+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plot',type=Path);a=p.parse_args()
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt('Terminated')))
    if a.plot:render(a.plot.resolve())
    else:
        with (ROOT/'output/.pipeline.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);acquire()
