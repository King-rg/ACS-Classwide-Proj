"""Paired, denser Figure 2 follow-up using a new disposable regular file."""
from pathlib import Path
import argparse, csv, datetime, fcntl, hashlib, json, os, random, shutil, signal, subprocess, sys, time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / 'shared'))
from project3 import fio_environment

BLOCKS = [4, 16, 32, 40, 48, 56, 64, 72, 80, 96, 112, 128, 192, 256]
TRIALS, DURATION, RAMP, SIZE = 10, 3, 1, 2**30


def save_json(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n')


def read_text(path):
    try: return Path(path).read_text().strip()
    except OSError: return None


def temps():
    return {str(p): read_text(p) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')}


def table(path, rows):
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)


def render(out, first_trials=None, plots=True):
    meta = json.loads((out/'metadata.json').read_text())
    assert meta['complete'] or first_trials is not None, 'Incomplete acquisition requires explicit subset selection'
    trials = TRIALS if first_trials is None else first_trials
    assert 1 <= trials <= TRIALS
    assert hashlib.sha256((out/'raw.csv').read_bytes()).hexdigest() == meta['raw_sha256']
    rows = list(csv.DictReader((out/'raw.csv').open()))
    rows = [r for r in rows if int(r['trial']) < trials]
    assert len(rows) == len(BLOCKS)*trials*2
    table(out/'selected-trials.csv', rows)
    for r in rows:
        j = json.loads((out/'raw'/f"{r['name']}.json").read_text())['jobs'][0]
        assert not j['error'] and j['read']['total_ios'] > 0
        for key, v in [('iops', j['read']['iops']), ('mib_s', j['read']['bw_bytes']/2**20), ('lat_us', j['read']['lat_ns']['mean']/1000)]:
            assert np.isclose(float(r[key]), v, rtol=1e-10)
        d = j['read']
        assert np.isclose(float(r['iops']), d['total_ios']/(d['runtime']/1000), rtol=1e-6)
        assert np.isclose(float(r['mib_s'])*2**20, d['io_bytes']/(d['runtime']/1000), rtol=1e-6)
        # FIO ramp-boundary accounting can differ by the outstanding queue;
        # non-dividing block sizes can also end with a short request.
        assert abs(d['io_bytes']-d['total_ios']*int(r['bs_kib'])*1024) <= 16*int(r['bs_kib'])*1024
    for name in ['initialize', 'verify']:
        assert all(not j['error'] for j in json.loads((out/'raw'/f'{name}.json').read_text())['jobs'])
    assert not (out/'disposable.bin').exists()
    summary=[]
    for pattern in ['read', 'randread']:
        for bs in BLOCKS:
            rr = [r for r in rows if r['rw']==pattern and int(r['bs_kib'])==bs]
            assert sorted(int(r['trial']) for r in rr) == list(range(trials))
            s = {'rw':pattern, 'bs_kib':bs, 'trials':len(rr)}
            for metric in ['iops','mib_s','lat_us']:
                for suffix, value in zip(['median','q25','q75'], np.percentile([float(r[metric]) for r in rr],[50,25,75])):
                    s[metric+'_'+suffix] = float(value)
            summary.append(s)
    table(out/'summary.csv',summary)
    paired=[]
    for bs in BLOCKS:
        ratios=[]
        for trial in range(trials):
            pair={r['rw']:float(r['mib_s']) for r in rows if int(r['bs_kib'])==bs and int(r['trial'])==trial}
            ratios.append(pair['read']/pair['randread'])
        paired.append(dict(bs_kib=bs, **dict(zip(['median','q25','q75'],map(float,np.percentile(ratios,[50,25,75]))))))
    table(out/'paired-ratios.csv', paired)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.labelsize':10,'xtick.labelsize':8,
        'ytick.labelsize':9,'legend.fontsize':9,'legend.frameon':False,'axes.spines.top':False,
        'axes.spines.right':False,'axes.axisbelow':True,'savefig.facecolor':'white','pdf.fonttype':42})
    if plots:
        fig, axes = plt.subplots(3,1,figsize=(9,9),layout='constrained')
        for ax,metric,label,scale in zip(axes,['iops','mib_s','lat_us'],
            ['Throughput (thousand IOPS)','Throughput (MiB/s)','Mean total I/O latency (µs)'],[.001,1,1]):
            for pattern,color,marker,label2 in [('read','#24649a','o','Sequential read'),('randread','#bb6c16','s','Random read')]:
                rr=[r for r in summary if r['rw']==pattern]
                x=[r['bs_kib'] for r in rr]; y=np.array([r[metric+'_median'] for r in rr])*scale
                ax.plot(x,y,color=color,marker=marker,lw=1.5,ms=4,label=label2)
                ax.fill_between(x,[r[metric+'_q25']*scale for r in rr],[r[metric+'_q75']*scale for r in rr],color=color,alpha=.14,lw=0)
            ax.set(xlabel='Block size (KiB)',ylabel=label,xscale='log',ylim=(0,None))
            ax.set_xticks(BLOCKS,[str(x) for x in BLOCKS]);ax.minorticks_off()
            ax.grid(axis='y',color='#dfe3e8',lw=.6);ax.legend(loc='best')
        for ext in ['png','svg','pdf']:fig.savefig(out/f'fig2-block-size.{ext}',dpi=360)
        plt.close(fig)
    save_json(out/'validation.json',{'observations':len(rows),'conditions':len(summary),'all_raw_json_and_arithmetic_checks_passed':True,
        'trials_per_condition':trials,'selection':'First complete trials, selected at user request' if first_trials else 'All planned trials',
        'uncertainty':f'Median and interquartile range of {trials} trials; not confidence intervals',
        'raw_sha256':meta['raw_sha256']})
    print(('Validated and plotted: ' if plots else 'Validated: ')+str(out),flush=True)


def acquire(out=None, plots=True, publish=True):
    env=fio_environment(ROOT);fio=env['REPORT_FIO'];cpu=min(os.sched_getaffinity(0))
    assert shutil.disk_usage(ROOT).free > 6*2**30
    out=Path(out) if out is not None else ROOT/'output/block-repeat'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    out.mkdir(parents=True)
    for name in ['raw','configs','source']:(out/name).mkdir()
    shutil.copy2(__file__,out/'source/block_repeat.py')
    def command(args):return subprocess.check_output(args,env=env,text=True,stderr=subprocess.STDOUT)
    meta={'complete':False,'blocks_kib':BLOCKS,'trials':TRIALS,'runtime_s':DURATION,'ramp_s':RAMP,'file_bytes':SIZE,'cpu':cpu,
        'fio':command([fio,'--version']).strip(),'os':command(['uname','-a']),'cpu_info':command(['lscpu']),
        'storage':command(['lsblk','-o','NAME,MODEL,SIZE,TRAN,ROTA,FSTYPE,MOUNTPOINTS']),
        'filesystem':command(['findmnt','-T',str(ROOT)]),'governor':read_text(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor'),
        'smt':read_text('/sys/devices/system/cpu/smt/active'),'temperature_start':temps(),'commands':[],
        'pairing':'Same block size back-to-back, order alternates by trial and size; size order shuffled with seed 4320',
        'prior_run':'20261022T215132.687552Z','prior_runtime_s':10,'prior_trials':5}
    target=out/'disposable.bin';owned=False;rows=[];start=time.monotonic()
    def run(name,options):
        assert target.is_file() and not target.is_symlink()
        base=dict(filename=str(target),ioengine='libaio',direct=1,bs=4096,iodepth=16,numjobs=1,size=SIZE,
            allow_file_create=0,thread=1,cpus_allowed=cpu,refill_buffers=1,buffer_compress_percentage=0,
            randrepeat=1,randseed=1234,group_reporting=1,lat_percentiles=1,percentile_list='50:95:99:99.9')
        base.update(options)
        conf=out/'configs'/f'{name}.fio';conf.write_text('[global]\n'+'\n'.join(f'{k}={v}' for k,v in base.items())+f'\n\n[{name}]\n')
        args=[fio,str(conf),'--output-format=json','--output='+str(out/'raw'/f'{name}.json')]
        meta['commands'].append(args)
        subprocess.run(args,env=env,check=True,stdout=subprocess.DEVNULL)
        jobs=json.loads((out/'raw'/f'{name}.json').read_text())['jobs'];assert len(jobs)==1 and not jobs[0]['error'],name
        return jobs[0]
    print('Run directory: '+str(out),flush=True)
    save_json(out/'metadata.json',meta)
    try:
        fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_NOFOLLOW,0o600);owned=True
        try:os.posix_fallocate(fd,0,SIZE)
        finally:os.close(fd)
        run('initialize',dict(rw='write',bs=131072,end_fsync=1))
        run('verify',dict(rw='write',size=16*2**20,verify='crc32c',do_verify=1,verify_fatal=1,end_fsync=1))
        rng=random.Random(4320)
        for trial in range(TRIALS):
            sizes=list(BLOCKS);rng.shuffle(sizes)
            for bs in sizes:
                patterns=['read','randread'] if (trial+BLOCKS.index(bs))%2==0 else ['randread','read']
                for order,rw in enumerate(patterns):
                    name=f'{len(rows):03d}_{trial}_{bs}_{rw}'
                    before=temps();stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
                    j=run(name,dict(rw=rw,bs=bs*1024,time_based=1,runtime=DURATION,ramp_time=RAMP,invalidate=1,randseed=1234+trial))
                    d=j['read'];assert d['total_ios']>0
                    row=dict(name=name,trial=trial,bs_kib=bs,rw=rw,pair_order=order,started=stamp,ios=d['total_ios'],
                        iops=d['iops'],mib_s=d['bw_bytes']/2**20,lat_us=d['lat_ns']['mean']/1000,
                        depth_distribution=json.dumps(j['iodepth_level']),temperature_before=json.dumps(before),temperature_after=json.dumps(temps()))
                    rows.append(row)
                    with (out/'raw.csv').open('a',newline='') as f:
                        w=csv.DictWriter(f,fieldnames=row)
                        if len(rows)==1:w.writeheader()
                        w.writerow(row)
                save_json(out/'progress.json',{'completed':len(rows),'total':TRIALS*len(BLOCKS)*2,'elapsed_s':time.monotonic()-start,'last_pair_kib':bs,'trial':trial})
                print(f'{len(rows)}/{TRIALS*len(BLOCKS)*2} trials; {bs} KiB pair; elapsed {(time.monotonic()-start)/60:.1f} min',flush=True)
        meta['complete']=True
    finally:
        if owned:target.unlink(missing_ok=True)
        meta.update(observations=len(rows),temperature_end=temps(),elapsed_s=time.monotonic()-start,
                    raw_sha256=hashlib.sha256((out/'raw.csv').read_bytes()).hexdigest() if rows else None)
        save_json(out/'metadata.json',meta)
    render(out, plots=plots)
    if publish: (ROOT/'output/LATEST_BLOCK_REPEAT').write_text(str(out.relative_to(ROOT/'output'))+'\n')

    return out


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--plot',type=Path);parser.add_argument('--first-trials',type=int);args=parser.parse_args()
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt('Terminated')))
    if args.plot:render(args.plot.resolve(), args.first_trials)
    else:
        with (ROOT/'output/.pipeline.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            acquire()
