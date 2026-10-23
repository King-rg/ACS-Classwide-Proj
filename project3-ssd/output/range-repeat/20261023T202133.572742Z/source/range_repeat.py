"""Expanded file-range experiment on an owned disposable regular file."""
from block_repeat import ROOT, save_json, read_text, temps, table, fio_environment
from pathlib import Path
import argparse, csv, datetime, fcntl, hashlib, json, os, random, shutil, signal, subprocess, time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
TRIALS, DURATION, RAMP, SIZE = 8, 6, 2, 16*2**30
RANGES = [16*2**i for i in range(11)]


def metrics(j):
    d=j['read'];assert not j['error'] and d['total_ios']>0 and not j['write']['total_ios']
    p=d['lat_ns']['percentile']
    return dict(ios=d['total_ios'],iops=d['iops'],mib_s=d['bw_bytes']/2**20,
        lat_us=d['lat_ns']['mean']/1000,p95_us=p['95.000000']/1000,p99_us=p['99.000000']/1000)


def render(out):
    meta=json.loads((out/'metadata.json').read_text());assert meta['complete']
    assert meta['raw_sha256']==hashlib.sha256((out/'raw.csv').read_bytes()).hexdigest()
    rows=list(csv.DictReader((out/'raw.csv').open()));assert len(rows)==TRIALS*len(RANGES)
    for row in rows:
        j=json.loads((out/'raw'/f"{row['name']}.json").read_text())['jobs'][0]
        for k,v in metrics(j).items():assert np.isclose(float(row[k]),v,rtol=1e-10)
        d=j['read']
        assert np.isclose(d['iops'],d['total_ios']/(d['runtime']/1000),rtol=1e-6)
        assert np.isclose(d['bw_bytes'],d['io_bytes']/(d['runtime']/1000),rtol=1e-6)
        assert abs(d['io_bytes']-d['total_ios']*4096)<=16*4096
        opts=j['job options'];assert int(opts['size'])==int(row['range_mib'])*2**20
        assert int(opts['iodepth'])==16 and int(opts['direct'])==1 and int(opts['bs'])==4096
    for name in ['initialize','verify']:
        assert all(not j['error'] for j in json.loads((out/'raw'/f'{name}.json').read_text())['jobs'])
    assert not (out/'disposable.bin').exists()
    summary=[]
    for span in RANGES:
        rr=[r for r in rows if int(r['range_mib'])==span]
        assert sorted(int(r['trial']) for r in rr)==list(range(TRIALS))
        s=dict(range_mib=span,trials=TRIALS)
        for metric in ['iops','mib_s','lat_us','p95_us','p99_us']:
            for suffix,v in zip(['median','q25','q75'],np.percentile([float(r[metric]) for r in rr],[50,25,75])):s[metric+'_'+suffix]=float(v)
        summary.append(s)
    table(out/'summary.csv',summary)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'xtick.labelsize':9,'ytick.labelsize':9,
        'axes.spines.top':False,'axes.spines.right':False,'axes.axisbelow':True,'legend.frameon':False,'pdf.fonttype':42})
    fig,axes=plt.subplots(2,1,figsize=(9,6.5),layout='constrained')
    for ax,key,label,scale in zip(axes,['lat_us','iops'],['Mean total I/O latency (µs)','Throughput (thousand IOPS)'],[1,.001]):
        for row in rows:
            ax.scatter(int(row['range_mib']),float(row[key])*scale,s=13,alpha=.25,color='#24649a',edgecolors='none')
        y=[s[key+'_median']*scale for s in summary]
        ax.plot(RANGES,y,'o-',color='#24649a',lw=1.6,ms=4,label='Median of 8 trials')
        ax.fill_between(RANGES,[s[key+'_q25']*scale for s in summary],[s[key+'_q75']*scale for s in summary],color='#24649a',alpha=.14,lw=0,label='Trial IQR')
        ax.set(xlabel='Accessed file range',ylabel=label,ylim=(0,None),xscale='log')
        ax.set_xticks(RANGES,[f'{x} MiB' if x<1024 else f'{x//1024} GiB' for x in RANGES]);ax.minorticks_off()
        ax.grid(axis='y',color='#dfe3e8',lw=.6)
    axes[0].legend(loc='best',ncol=2)
    for ext in ['png','svg','pdf']:fig.savefig(out/f'fig6-file-range.{ext}',dpi=360)
    plt.close(fig)
    save_json(out/'validation.json',dict(observations=len(rows),conditions=len(summary),trials_per_condition=TRIALS,
        raw_json_settings_and_arithmetic_passed=True,uncertainty='Trial IQR, not confidence intervals',raw_sha256=meta['raw_sha256']))
    print('Validated and plotted: '+str(out),flush=True)


def acquire():
    env=fio_environment(ROOT);fio=env['REPORT_FIO'];cpu=min(os.sched_getaffinity(0))
    assert shutil.disk_usage(ROOT).free>SIZE + 8*2**30
    out=ROOT/'output/range-repeat'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    out.mkdir(parents=True)
    for sub in ['raw','configs','source']:(out/sub).mkdir()
    for name in ['range_repeat.py','block_repeat.py']:shutil.copy2(ROOT/'scripts'/name,out/'source'/name)
    (out/'protocol.txt').write_text('Range sweep: eleven powers-of-two file-offset spans from 16 MiB to 16 GiB, eight shuffled rounds (seed 4320). Same initialized 16 GiB file, offset zero, 4 KiB random reads, direct I/O, QD 16, one CPU-pinned job. Six measured seconds after two seconds ramp per trial. Mean and per-trial p95/p99 latency, IOPS, temperature and achieved depth are preserved. Historical data are not pooled.\n')
    def command(args):return subprocess.check_output(args,env=env,text=True,stderr=subprocess.STDOUT)
    meta=dict(complete=False,trials=TRIALS,runtime_s=DURATION,ramp_s=RAMP,ranges_mib=RANGES,file_bytes=SIZE,cpu=cpu,
        fio=command([fio,'--version']).strip(),os=command(['uname','-a']),cpu_info=command(['lscpu']),
        storage=command(['lsblk','-o','NAME,MODEL,SIZE,TRAN,ROTA,FSTYPE,MOUNTPOINTS']),filesystem=command(['findmnt','-T',str(ROOT)]),
        governor=read_text(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor'),smt=read_text('/sys/devices/system/cpu/smt/active'),
        temperature_start=temps(),commands=[],prior_run='20261022T215132.687552Z',prior_runtime_s=10)
    target=out/'disposable.bin';owned=False;rows=[];start=time.monotonic()
    def run(name,opts):
        assert target.is_file() and not target.is_symlink()
        base=dict(filename=str(target),ioengine='libaio',direct=1,bs=4096,iodepth=16,numjobs=1,size=SIZE,
            allow_file_create=0,thread=1,cpus_allowed=cpu,refill_buffers=1,buffer_compress_percentage=0,
            randrepeat=1,randseed=1234,group_reporting=1,lat_percentiles=1,percentile_list='50:95:99:99.9')
        base.update(opts)
        conf=out/'configs'/f'{name}.fio';conf.write_text('[global]\n'+'\n'.join(f'{k}={v}' for k,v in base.items())+f'\n\n[{name}]\n')
        args=[fio,str(conf),'--output-format=json','--output='+str(out/'raw'/f'{name}.json')];meta['commands'].append(args)
        subprocess.run(args,env=env,check=True,stdout=subprocess.DEVNULL)
        j=json.loads((out/'raw'/f'{name}.json').read_text())['jobs'];assert len(j)==1 and not j[0]['error'];return j[0]
    print('Run directory: '+str(out),flush=True);save_json(out/'metadata.json',meta)
    try:
        fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_NOFOLLOW,0o600);owned=True
        try:os.posix_fallocate(fd,0,SIZE)
        finally:os.close(fd)
        run('initialize',dict(rw='write',bs=131072,end_fsync=1))
        run('verify',dict(rw='write',size=16*2**20,verify='crc32c',do_verify=1,verify_fatal=1,end_fsync=1))
        rng=random.Random(4320)
        for trial in range(TRIALS):
            ranges=list(RANGES);rng.shuffle(ranges)
            for span in ranges:
                name=f'{len(rows):03d}_{trial}_{span}';before=temps();stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
                j=run(name,dict(rw='randread',size=span*2**20,time_based=1,runtime=DURATION,ramp_time=RAMP,invalidate=1,randseed=1234+trial))
                row=dict(name=name,trial=trial,range_mib=span,started=stamp,**metrics(j),
                    depth_distribution=json.dumps(j['iodepth_level']),temperature_before=json.dumps(before),temperature_after=json.dumps(temps()))
                rows.append(row)
                with (out/'raw.csv').open('a',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=row)
                    if len(rows)==1:w.writeheader()
                    w.writerow(row)
                save_json(out/'progress.json',dict(completed=len(rows),total=TRIALS*len(RANGES),elapsed_s=time.monotonic()-start))
                print(f'{len(rows)}/{TRIALS*len(RANGES)} trials; {span} MiB; elapsed {(time.monotonic()-start)/60:.1f} min',flush=True)
        meta['complete']=True
    finally:
        if owned:target.unlink(missing_ok=True)
        meta.update(observations=len(rows),temperature_end=temps(),elapsed_s=time.monotonic()-start,
            raw_sha256=hashlib.sha256((out/'raw.csv').read_bytes()).hexdigest() if rows else None)
        save_json(out/'metadata.json',meta)
    render(out)
    (ROOT/'output/LATEST_RANGE_REPEAT').write_text(str(out.relative_to(ROOT/'output'))+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plot',type=Path);a=p.parse_args()
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt('Terminated')))
    if a.plot:render(a.plot.resolve())
    else:
        with (ROOT/'output/.pipeline.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);acquire()
