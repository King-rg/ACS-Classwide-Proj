"""Spec-mapped SSD report analysis using FIO total I/O latency."""
from pathlib import Path
import collections
import json
import math
import os
import shutil
import subprocess
import sys
import numpy as np
from report_common import (Figures, command, digest, point, read_csv, stats,
                           write_csv, write_json)

KEYS=['study','rw','bs','qd','span','direct','mix']
METRICS=['iops','mib_s','lat_us','little_law_inflight']+[
    f'{d}_p{p}_us' for d in ['read','write'] for p in [50,95,99,99.9]]


def fio_environment(root):
    env=os.environ.copy()
    env['LD_LIBRARY_PATH']=str(root/'tools/local/usr/lib/x86_64-linux-gnu')+':'+env.get('LD_LIBRARY_PATH','')
    candidates=[os.environ['FIO']] if os.environ.get('FIO') else [shutil.which('fio'),str(root/'tools/local/usr/bin/fio')]
    for candidate in candidates:
        if not candidate: continue
        try:
            version=subprocess.check_output([candidate,'--version'],env=env,text=True,stderr=subprocess.STDOUT)
            if version.strip().startswith('fio-'):
                env['REPORT_FIO']=candidate
                return env
        except (OSError,subprocess.CalledProcessError):
            pass
    raise ValueError('FIO storage benchmark unavailable. Install fio or set FIO to its executable.')


def preflight(root):
    fio_environment(root)
    for name in ['lscpu','lsblk','findmnt']:
        if not shutil.which(name):raise ValueError(f'Missing dependency: {name}')
    if shutil.disk_usage(root).free <= 6*2**30:
        raise ValueError('At least 6 GiB free space is required')


def acquire(root, output):
    env=fio_environment(root)
    env['REPORT_RUN_DIR']=str(output)
    command([sys.executable,root/'scripts/run.py','--profile','full'],env=env,cwd=root)


def expected_cases(full=True):
    cases=[]
    def add(study,rw,bs=4096,qd=1,span=2**30,direct=1,mix=100):
        cases.append((study,rw,bs,qd,span,direct,mix))
    for rw,bs in [('randread',4096),('randwrite',4096),('read',131072),('write',131072)]:add('baseline',rw,bs)
    for rw in ['randread','read']:
        for bs in [4096,16384,32768,65536,131072,262144]:add('block',rw,bs,16)
    for mix in [100,70,50,0]:add('mix','randrw',4096,16,mix=mix)
    for qd in ([1,2,4,8,16,32,64,128,256] if full else [1,2,4,8,16,32,64]):add('queue','randread',4096,qd)
    for span in [16*2**20,64*2**20,256*2**20,2**30]:add('range','randread',4096,16,span)
    for direct in [0,1]:add('pitfall','read',131072,1,16*2**20,direct)
    return set(cases)


def validate(root, run):
    meta=json.loads((run/'metadata.json').read_text())
    rows=read_csv(run/'raw.csv')
    if meta.get('raw_sha256') and digest(run/'raw.csv') != meta['raw_sha256']:
        raise ValueError('Raw CSV checksum mismatch')
    groups=collections.defaultdict(list)
    for r in rows:
        key=tuple(r[k] if k in ['study','rw'] else int(r[k]) for k in KEYS)
        groups[key].append(int(r['trial']))
        j=json.loads((run/'raw'/(r['name']+'.json')).read_text())['jobs'][0]
        if j['error'] or int(r['ios'])<=0:raise ValueError('FIO failed or completed no I/O')
        active=[j[d] for d in ['read','write'] if j[d]['total_ios']]
        n=sum(x['total_ios'] for x in active)
        checks=[(float(r['ios']),n),
                (float(r['iops']),sum(x['iops'] for x in active)),
                (float(r['mib_s'])*2**20,float(r['iops'])*int(r['bs'])),
                (float(r['lat_us']),sum(x['lat_ns']['mean']*x['total_ios'] for x in active)/n/1000),
                (float(r['little_law_inflight']),float(r['iops'])*float(r['lat_us'])/1e6)]
        if any(not math.isclose(a,b,rel_tol=1e-6) for a,b in checks):raise ValueError('FIO derived arithmetic mismatch')
        if json.loads(r['depth_distribution'])!=j['iodepth_level']:raise ValueError('FIO achieved depth mismatch')
        for direction in ['read','write']:
            if not j[direction]['total_ios']:continue
            values=[j[direction]['lat_ns']['percentile'][f'{p:.6f}']/1000 for p in [50,95,99,99.9]]
            if values!=sorted(values):raise ValueError('Unordered percentiles')
            for p,value in zip([50,95,99,99.9],values):
                if not math.isclose(float(r[f'{direction}_p{p}_us']),value):raise ValueError('Percentile parsing mismatch')
    if set(groups)!=expected_cases(meta['profile']=='full') or any(sorted(v)!=list(range(meta['trials'])) for v in groups.values()):
        raise ValueError('Missing or duplicate SSD conditions/trials')
    if len(rows)!=meta['observations']:raise ValueError('Observation count mismatch')
    for name in ['initialize','verify','state']:
        if any(j['error'] for j in json.loads((run/'raw'/f'{name}.json').read_text())['jobs']):raise ValueError(f'{name} failed')
    if (run/'disposable.bin').exists():raise ValueError('Disposable file cleanup incomplete')
    for pattern in ['state_bw*.log','state_lat*.log']:
        files=list(run.glob(pattern))
        if len(files)!=1:raise ValueError(f'Expected one {pattern} time series')
        data=np.loadtxt(files[0],delimiter=',',ndmin=2)
        if (data.shape[1]<3 or not np.all(np.isfinite(data[:,:3]))
                or np.any(data[:,:2]<=0) or np.any(np.diff(data[:,0])<0)
                or np.any(data[:,2]!=1)):
            raise ValueError(f'Invalid write-burst time series: {files[0].name}')


def summarize(run):
    raw=read_csv(run/'raw.csv')
    groups=collections.defaultdict(list)
    for row in raw:
        for k in KEYS[2:]+['trial','ios']:row[k]=int(row[k])
        for k in METRICS:row[k]=float(row[k])
        groups[tuple(row[k] for k in KEYS)].append(row)
    ss=[]
    for key,rr in groups.items():
        s=dict(zip(KEYS,key))
        for metric in METRICS:
            s[metric],s[metric+'_q25'],s[metric+'_q75']=stats([r[metric] for r in rr])
        ss.append(s)
    return raw,ss


def near_knee(queue):
    queue=sorted(queue,key=lambda r:r['qd'])
    peak=max(s['iops'] for s in queue)
    return next(s for s in queue if s['iops']>=.9*peak)


def state_points(data, scale):
    """Retain short final log windows and label them rather than hiding them."""
    points=[]
    previous=0.0
    for row in data:
        elapsed=float(row[0])
        window=elapsed-previous
        points.append(dict(series='Sequential write burst',x=elapsed/1000,
                           y=float(row[1])*scale,window_ms=window,
                           annotation='Partial final window' if window<900 else ''))
        previous=elapsed
    return points


def plot(root, run):
    raw,ss=summarize(run)
    write_csv(run/'summary.csv',ss)
    f=Figures(run,[dict(path='raw.csv',sha256=digest(run/'raw.csv'))])
    def sel(study,**kw):return [s for s in ss if s['study']==study and all(s[k]==v for k,v in kw.items())]
    def pt(s,x,metric,label,scale=1):
        return dict(series=label,x=x,y=s[metric]*scale,y_q25=s[metric+'_q25']*scale,y_q75=s[metric+'_q75']*scale)
    baseline=sorted(sel('baseline'),key=lambda s:(s['bs'],s['rw']))
    write_csv(run/'latency_table.csv',baseline)
    points=[]
    for i,s in enumerate(baseline):
        direction='read' if 'read' in s['rw'] else 'write'
        points += [pt(s,i,metric,label) for metric,label in [('lat_us','Mean'),(f'{direction}_p95_us','p95'),(f'{direction}_p99_us','p99')]]
    f.bars('01_baselines',points,['4 KiB random\nread','4 KiB random\nwrite','128 KiB sequential\nread','128 KiB sequential\nwrite'],
           'Total I/O latency (µs)','QD=1 baselines. Medians and trial IQR; p95/p99 are per-trial request percentiles.')
    for metric,ylabel in [('iops','IOPS'),('mib_s','Throughput (MiB/s)'),('lat_us','Mean total I/O latency (µs)')]:
        points=[]
        for rw,label in [('read','Sequential read'),('randread','Random read')]:
            points += [pt(s,s['bs']/1024,metric,label) for s in sorted(sel('block',rw=rw),key=lambda s:s['bs'])]
        f.lines('02_block_'+metric,points,'Block size (KiB)',ylabel,'Block-size comparison from the same trials; QD 16, one job, 1 GiB file range.',
                logx=True,ticks=([4,16,32,64,128,256],['4','16','32','64','128','256']))
    for metric,ylabel in [('iops','IOPS'),('lat_us','Mean total I/O latency (µs)')]:
        points=[pt(s,100-s['mix'],metric,'4 KiB random') for s in sorted(sel('mix'),key=lambda s:-s['mix'])]
        f.lines('03_mix_'+metric,points,'Writes (%)',ylabel,'Read/write mixes 100/0, 70/30, 50/50, 0/100; QD 16. Mixed mean latency is weighted by completed I/O counts.',ticks=([0,30,50,100],['0','30','50','100']))
    queue=sorted(sel('queue'),key=lambda s:s['qd'])
    near=near_knee(queue)
    mid=next(s for s in queue if s['qd']==8)
    points=[]
    for s in queue:
        points.append(dict(pt(s,s['lat_us'],'iops','Random read',.001),x_q25=s['lat_us_q25'],x_q75=s['lat_us_q75'],
                           requested_qd=s['qd'],annotation=f'QD {s["qd"]}'+(' *' if s==near else '')))
    f.lines('04_queue_throughput_latency',points,'Mean total I/O latency (µs)','Throughput (thousand IOPS)',
            '* marks the first QD reaching 90% of observed peak IOPS, an operational near-knee estimate, not proof of saturation. 4 KiB random reads; one job.')
    endpoint_improving=queue[-1]['iops']>queue[-2]['iops']
    write_json(run/'queue_analysis.json',dict(near_knee_qd=near['qd'],criterion='first QD reaching 90% of observed peak median IOPS',
        peak_iops=max(s['iops'] for s in queue),endpoint_improving=endpoint_improving,
        interpretation='Endpoint throughput is still improving; saturation is not established.' if endpoint_improving else 'Operational near-knee estimate; repeated trials and achieved depths must be considered before claiming saturation.'))
    write_csv(run/'little_law.csv',[{k:r[k] for k in ['trial','qd','iops','lat_us','little_law_inflight','depth_distribution']} for r in raw if r['study']=='queue'])
    points=[]
    for s,label in ([(mid,f'QD 8 (mid-range and near-knee)')] if mid==near else [(mid,'QD 8 (mid-range)'),(near,f'QD {near["qd"]} (near-knee estimate)')]):
        points += [pt(s,i,f'read_p{p}_us',label) for i,p in enumerate([50,95,99,99.9])]
    f.lines('05_tail_latency',points,'Request percentile','Total I/O latency (µs)',
            'Median and trial IQR of per-trial percentiles, not pooled request quantiles. 4 KiB random reads.',ticks=([0,1,2,3],['p50','p95','p99','p99.9']))
    points=[pt(s,s['span']/2**20,'lat_us','Random read') for s in sorted(sel('range'),key=lambda s:s['span'])]
    f.lines('06_range_latency',points,'File-offset range (MiB)','Mean total I/O latency (µs)',
            '4 KiB random reads at QD 16. File offset ranges do not establish physical LBA placement.',logx=True,ticks=([16,64,256,1024],['16','64','256','1024']))
    for pattern,name,scale,label in [('state_bw*.log','throughput',1/1024,'Throughput (MiB/s)'),('state_lat*.log','latency',1/1000,'Mean total I/O latency (µs)')]:
        path=next(run.glob(pattern))
        f.sources.append(dict(path=path.name,sha256=digest(path)))
        data=np.loadtxt(path,delimiter=',',ndmin=2)
        points=state_points(data,scale)
        f.lines('07_state_'+name,points,'Time in write burst (s)',label,
                'Single bounded 128 KiB sequential-write burst at QD 16; nominal one-second windows, with any short final window labeled. No repeatability interval or steady-state claim.',settings={'source':path.name,'samples':'1 second, with possible partial final window'})
    points=[pt(s,i,'mib_s','Repeated reads') for i,s in enumerate(sorted(sel('pitfall'),key=lambda s:s['direct']))]
    f.bars('08_page_cache_pitfall',points,['Buffered, pre-read','Direct I/O'],'Throughput (MiB/s)',
           'Repeated 16 MiB reads, 128 KiB blocks, QD 1. Direct I/O bypasses the OS page cache, not SSD controller caches.')
    f.complete()
