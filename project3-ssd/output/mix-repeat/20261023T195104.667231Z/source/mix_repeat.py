"""Ten-percentage-point read/write sweep on an owned disposable file."""
from block_repeat import ROOT, SIZE, save_json, read_text, temps, table, fio_environment
from pathlib import Path
import argparse, csv, datetime, fcntl, hashlib, json, os, random, shutil, signal, subprocess, time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

TRIALS, DURATION, RAMP = 5, 3, 1
WRITES = list(range(0, 101, 10))


def metrics(j):
    active=[j[d] for d in ['read','write'] if j[d]['total_ios']]
    n=sum(d['total_ios'] for d in active)
    assert n>0 and not j['error']
    return dict(ios=n,iops=sum(d['iops'] for d in active),
        mib_s=sum(d['bw_bytes'] for d in active)/2**20,
        lat_us=sum(d['lat_ns']['mean']*d['total_ios'] for d in active)/n/1000,
        achieved_read_pct=100*j['read']['total_ios']/n)


def render(out):
    meta=json.loads((out/'metadata.json').read_text());assert meta['complete']
    assert meta['raw_sha256']==hashlib.sha256((out/'raw.csv').read_bytes()).hexdigest()
    rows=list(csv.DictReader((out/'raw.csv').open()));assert len(rows)==TRIALS*len(WRITES)
    for row in rows:
        j=json.loads((out/'raw'/f"{row['name']}.json").read_text())['jobs'][0]
        for k,v in metrics(j).items():assert np.isclose(float(row[k]),v,rtol=1e-10)
        for d in [j[k] for k in ['read','write'] if j[k]['total_ios']]:
            assert np.isclose(d['iops'],d['total_ios']/(d['runtime']/1000),rtol=1e-6)
            assert np.isclose(d['bw_bytes'],d['io_bytes']/(d['runtime']/1000),rtol=1e-6)
    for name in ['initialize','verify']:
        assert all(not j['error'] for j in json.loads((out/'raw'/f'{name}.json').read_text())['jobs'])
    assert not (out/'disposable.bin').exists()
    summary=[]
    for writes in WRITES:
        rr=[r for r in rows if int(r['writes_pct'])==writes]
        assert sorted(int(r['trial']) for r in rr)==list(range(TRIALS))
        s=dict(read_pct=100-writes,write_pct=writes,trials=TRIALS)
        for metric in ['iops','mib_s','lat_us','achieved_read_pct']:
            for suffix,v in zip(['median','q25','q75'],np.percentile([float(r[metric]) for r in rr],[50,25,75])):s[metric+'_'+suffix]=float(v)
        summary.append(s)
    table(out/'summary.csv',summary)
    required=[s for s in summary if s['write_pct'] in [0,30,50,100]]
    table(out/'required-ratios.csv',required)
    lines=['| Read/write ratio (%) | Throughput (thousand IOPS) | Mean latency (µs) |',
           '| --- | ---: | ---: |']
    for s in required:
        def fmt(key,scale=1):return f"{s[key+'_median']*scale:.2f} [{s[key+'_q25']*scale:.2f}–{s[key+'_q75']*scale:.2f}]"
        lines.append(f"| {s['read_pct']}/{s['write_pct']} | {fmt('iops',.001)} | {fmt('lat_us')} |")
    (out/'required-ratios.txt').write_text('\n'.join(lines)+'\n')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'xtick.labelsize':9,'ytick.labelsize':9,
        'axes.spines.top':False,'axes.spines.right':False,'axes.axisbelow':True,'legend.frameon':False,'pdf.fonttype':42})
    fig,axes=plt.subplots(2,1,figsize=(8,6),layout='constrained')
    for ax,key,label,scale in zip(axes,['iops','lat_us'],['Throughput (thousand IOPS)','Mean total I/O latency (µs)'],[.001,1]):
        y=[s[key+'_median']*scale for s in summary]
        ax.plot(WRITES,y,'o-',color='#24649a',lw=1.6,ms=4)
        ax.fill_between(WRITES,[s[key+'_q25']*scale for s in summary],[s[key+'_q75']*scale for s in summary],color='#24649a',alpha=.14,lw=0)
        ax.set(xlabel='Writes (%)',ylabel=label,ylim=(0,None),xticks=WRITES)
        ax.grid(axis='y',color='#dfe3e8',lw=.6)
    for ext in ['png','svg','pdf']:fig.savefig(out/f'fig3-read-write-mix.{ext}',dpi=360)
    plt.close(fig)
    save_json(out/'validation.json',dict(observations=len(rows),conditions=len(summary),trials_per_condition=TRIALS,
        raw_json_and_arithmetic_passed=True,uncertainty='Trial IQR, not confidence intervals',raw_sha256=meta['raw_sha256']))
    print('Validated and plotted: '+str(out),flush=True)


def acquire():
    env=fio_environment(ROOT);fio=env['REPORT_FIO'];cpu=min(os.sched_getaffinity(0))
    assert shutil.disk_usage(ROOT).free>6*2**30
    out=ROOT/'output/mix-repeat'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    out.mkdir(parents=True)
    for sub in ['raw','configs','source']:(out/sub).mkdir()
    for name in ['mix_repeat.py','block_repeat.py']:shutil.copy2(ROOT/'scripts'/name,out/'source'/name)
    (out/'protocol.txt').write_text('Hypothesis: intermediate write fractions may perform similarly while write-heavy conditions lose throughput. Test all write fractions 0..100 in steps of 10, with five rounds in shuffled mix order (seed 4320). 4 KiB random I/O, QD 16, one pinned job, aligned direct I/O, 1 GiB disposable file; 3 seconds measured after 1 second ramp. Table includes required 100/0, 70/30, 50/50, 0/100 read/write ratios from the same trials as the plot. Do not pool historical measurements.\n')
    def command(args):return subprocess.check_output(args,env=env,text=True,stderr=subprocess.STDOUT)
    meta=dict(complete=False,trials=TRIALS,runtime_s=DURATION,ramp_s=RAMP,writes_pct=WRITES,file_bytes=SIZE,cpu=cpu,
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
            mixes=list(WRITES);rng.shuffle(mixes)
            for writes in mixes:
                name=f'{len(rows):03d}_{trial}_{writes}';before=temps();stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
                j=run(name,dict(rw='randrw',rwmixread=100-writes,time_based=1,runtime=DURATION,ramp_time=RAMP,invalidate=1,randseed=1234+trial))
                row=dict(name=name,trial=trial,writes_pct=writes,started=stamp,**metrics(j),
                    depth_distribution=json.dumps(j['iodepth_level']),temperature_before=json.dumps(before),temperature_after=json.dumps(temps()))
                rows.append(row)
                with (out/'raw.csv').open('a',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=row)
                    if len(rows)==1:w.writeheader()
                    w.writerow(row)
                save_json(out/'progress.json',dict(completed=len(rows),total=TRIALS*len(WRITES),elapsed_s=time.monotonic()-start))
                print(f'{len(rows)}/55 trials; {100-writes}/{writes} mix',flush=True)
        meta['complete']=True
    finally:
        if owned:target.unlink(missing_ok=True)
        meta.update(observations=len(rows),temperature_end=temps(),elapsed_s=time.monotonic()-start,
            raw_sha256=hashlib.sha256((out/'raw.csv').read_bytes()).hexdigest() if rows else None)
        save_json(out/'metadata.json',meta)
    render(out)
    (ROOT/'output/LATEST_MIX_REPEAT').write_text(str(out.relative_to(ROOT/'output'))+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plot',type=Path);a=p.parse_args()
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt('Terminated')))
    if a.plot:render(a.plot.resolve())
    else:
        with (ROOT/'output/.pipeline.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);acquire()
