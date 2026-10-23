"""Seven spec-mapped figures from saved FIO measurements; median and trial IQR."""
from pathlib import Path
import csv,json,collections,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image,ImageOps,ImageDraw
R=Path(__file__).resolve().parents[1];O=Path(sys.argv[1]) if len(sys.argv)>1 else R/'output'/(R/'output/LATEST').read_text().strip();P=O/'plots';P.mkdir(exist_ok=True)
rows=list(csv.DictReader((O/'raw.csv').open()));meta=json.loads((O/'metadata.json').read_text())
keys=['study','rw','bs','qd','span','direct','mix'];metrics=['iops','mib_s','lat_us','little_law_inflight']+[f'{d}_p{p}_us' for d in ['read','write'] for p in [50,95,99,99.9]]
g=collections.defaultdict(list)
for r in rows:
 for k in keys[2:]+['trial','ios']:r[k]=int(r[k])
 for k in metrics:r[k]=float(r[k])
 assert r['ios']>0 and r['iops']>0 and r['lat_us']>0
 g[tuple(r[k] for k in keys)].append(r)
ss=[]
for key,rr in g.items():
 assert sorted(r['trial'] for r in rr)==list(range(meta['trials']))
 s=dict(zip(keys,key))
 for m in metrics:
  vals=[r[m] for r in rr];s[m]=float(np.median(vals));s[m+'_lo']=float(np.percentile(vals,25));s[m+'_hi']=float(np.percentile(vals,75))
 ss.append(s)
with (O/'summary.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=ss[0]);w.writeheader();w.writerows(ss)
def sel(study,**kw):return [s for s in ss if s['study']==study and all(s[k]==v for k,v in kw.items())]
plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white'})
C=['#24649a','#bb6c16','#477d62','#8e679b'];files=[]
def save(fig,name):
 fig.tight_layout();fig.savefig(P/(name+'.png'),dpi=200);fig.savefig(P/(name+'.svg'));plt.close(fig);files.append(name)
def line(ax,xx,rr,m,label,c):
 ax.plot(xx,[s[m] for s in rr],'o-',label=label,color=c,ms=4);ax.fill_between(xx,[s[m+'_lo'] for s in rr],[s[m+'_hi'] for s in rr],color=c,alpha=.13);ax.grid(axis='y',alpha=.15)
rr=sorted(sel('baseline'),key=lambda s:(s['bs'],s['rw']));fig,ax=plt.subplots(figsize=(9,4.5));x=np.arange(4)
for i,m in enumerate(['lat_us','p95','p99']):
 vals=[s[m if i==0 else ('read_' if 'read' in s['rw'] else 'write_')+m+'_us'] for s in rr]
 ms=[m if i==0 else ('read_' if 'read' in s['rw'] else 'write_')+m+'_us' for s in rr]
 ax.bar(x+(i-1)*.24,vals,.24,yerr=[[s[k]-s[k+'_lo'] for s,k in zip(rr,ms)],[s[k+'_hi']-s[k] for s,k in zip(rr,ms)]],capsize=3,label=['Mean','p95','p99'][i],color=C[i])
ax.set(xticks=x,xticklabels=['4 KiB random\n'+s['rw'].replace('rand','') if s['bs']==4096 else '128 KiB sequential\n'+s['rw'] for s in rr],ylabel='Total I/O latency (µs)',title='QD=1 baselines');ax.legend();save(fig,'01_baselines')
fig,axes=plt.subplots(1,2,figsize=(11,4))
for c,rw in zip(C,['read','randread']):
 rr=sorted(sel('block',rw=rw),key=lambda s:s['bs']);xx=[s['bs']/1024 for s in rr]
 for ax,m in zip(axes,['mib_s','lat_us']):line(ax,xx,rr,m,{'read':'Sequential read','randread':'Random read'}[rw],c);ax.set_xscale('log',base=2);ax.set_xlabel('Block size (KiB)');ax.set_xticks(xx,labels=[str(int(v)) for v in xx])
axes[0].set_ylabel('Throughput (MiB/s)');axes[1].set_ylabel('Mean total I/O latency (µs)');axes[0].legend();fig.suptitle('Block size · QD 16 · 1 GiB range');save(fig,'02_block_size')
rr=sorted(sel('mix'),key=lambda s:-s['mix']);fig,axes=plt.subplots(1,2,figsize=(10,4))
for ax,m in zip(axes,['iops','lat_us']):line(ax,range(4),rr,m,'',C[0]);ax.set(xticks=range(4),xticklabels=['100/0','70/30','50/50','0/100'],xlabel='Read/write ratio (%)')
axes[0].set_ylabel('IOPS');axes[1].set_ylabel('Mean total I/O latency (µs)');fig.suptitle('4 KiB random mix · QD 16');save(fig,'03_read_write_mix')
q=sorted(sel('queue'),key=lambda s:s['qd']);peak=max(s['iops'] for s in q);knee=next(s for s in q if s['iops']>=.9*peak);fig,ax=plt.subplots(figsize=(8,4.5))
ax.plot([s['iops']/1000 for s in q],[s['lat_us'] for s in q],'o-',color=C[0])
for s in q:
 ax.errorbar(s['iops']/1000,s['lat_us'],xerr=[[max(0,s['iops']-s['iops_lo'])/1000],[max(0,s['iops_hi']-s['iops'])/1000]],yerr=[[max(0,s['lat_us']-s['lat_us_lo'])],[max(0,s['lat_us_hi']-s['lat_us'])]],color=C[0],alpha=.5)
 ax.annotate(str(s['qd']),(s['iops']/1000,s['lat_us']),xytext=(5,5),textcoords='offset points')
ax.set(xlabel='Throughput (thousand IOPS)',ylabel='Mean total I/O latency (µs)',title='4 KiB random read · labels show requested QD');ax.grid(alpha=.15);save(fig,'04_queue_depth')
mid=min(q,key=lambda s:abs(s['qd']-8));near=knee
fig,ax=plt.subplots(figsize=(8,4.5));xx=np.arange(4)
for i,s in enumerate([mid,near]):
 vals=[s[f'read_p{p}_us'] for p in [50,95,99,99.9]];ax.plot(xx,vals,'o-',color=C[i],label=f'QD {s["qd"]}'+(' (90% of observed peak)' if i else ' (mid-range)'))
 ax.fill_between(xx,[s[f'read_p{p}_us_lo'] for p in [50,95,99,99.9]],[s[f'read_p{p}_us_hi'] for p in [50,95,99,99.9]],color=C[i],alpha=.13)
ax.set(xticks=xx,xticklabels=['p50','p95','p99','p99.9'],ylabel='Total I/O latency (µs)',title='Tail latency · 4 KiB random read');ax.legend();save(fig,'05_tail_latency')
fig,axes=plt.subplots(1,2,figsize=(11,4));rr=sorted(sel('range'),key=lambda s:s['span']);line(axes[0],[s['span']/2**20 for s in rr],rr,'lat_us','Random read',C[0]);axes[0].set(xlabel='File-offset range (MiB)',ylabel='Mean latency (µs)',title='4 KiB random read · QD 16');axes[0].set_xscale('log',base=2);axes[0].set_xticks([16,64,256,1024],labels=['16','64','256','1024'])
logs=list(O.glob('state_bw*.log'));assert logs
arr=np.loadtxt(logs[0],delimiter=',',ndmin=2);axes[1].plot(arr[:,0]/1000,arr[:,1]/1024,'o-',color=C[1]);axes[1].set(xlabel='Time in write burst (s)',ylabel='Throughput (MiB/s)',title='128 KiB sequential write · QD 16');save(fig,'06_range_device_state')
rr=sorted(sel('pitfall'),key=lambda s:s['direct']);fig,ax=plt.subplots(figsize=(7,4.5));ax.bar(['Buffered, pre-read','Direct I/O'],[s['mib_s'] for s in rr],yerr=[[s['mib_s']-s['mib_s_lo'] for s in rr],[s['mib_s_hi']-s['mib_s'] for s in rr]],color=C[:2],capsize=4);ax.set(ylabel='Throughput (MiB/s)',title='Repeated 16 MiB reads · 128 KiB · QD 1');save(fig,'07_page_cache_pitfall')
report=['# Project 3 — SSD performance pilot',f'{len(rows)} measurements, {len(ss)} configurations, {meta["trials"]} trials/configuration, {meta["runtime_s"]} second(s) per timed trial. Medians and interquartile bands describe trial variability, not confidence intervals. FIO total latency includes submission and completion latency; mixed means are weighted by completed I/O count. Percentiles shown are medians of per-trial percentiles, not pooled request quantiles.',
'## Findings',f'The highest observed 4 KiB random-read rate was {peak:,.0f} IOPS. The first QD reaching 90% of that observed maximum was {knee["qd"]}, at {knee["lat_us"]:.1f} µs mean latency. This is an operational near-saturation marker, not proof of the device’s absolute saturation knee. Extend the sweep if the endpoint is still improving.',
f'At that QD, IOPS × mean total latency gives {knee["little_law_inflight"]:.1f} average requests in the measured software path. Compare this with the raw FIO depth distribution; requested QD is a cap, not evidence of achieved controller occupancy.',
f'The buffered/direct median throughput ratio for the repeatedly read 16 MiB file region was {rr[0]["mib_s"]/rr[1]["mib_s"]:.2f}×. This comparison illustrates how cache policy changes the measured path. Direct I/O bypasses the OS page cache but does not bypass SSD controller caches.',
'## Scope and limitations','The SSD is the existing mounted system NVMe device. A newly created 1 GiB regular file was fully initialized before timing, and a 16 MiB CRC32C write/read check passed. All timed jobs reported error=0. Only the disposable file was written and it was removed after measurement. No raw-device writes, global cache drops, trims, or filesystem changes were used.',
'This is a short burst study on a previously used device, not a fresh or certified steady-state SSD test. Writes complete without per-I/O fsync, so write latency does not establish power-loss durability. The write time series has one run; no repeatability interval is claimed. Small file ranges do not establish physical LBA placement, whole-device behavior, or SLC-cache exhaustion. Background I/O, temperature, firmware, and CPU limits can affect results; correlations alone cannot identify throttling or garbage collection.',
'FIO runs one job pinned to the recorded CPU using libaio. Direct I/O and aligned block sizes are used except in the explicitly labeled buffered comparison. No CPU isolation or fixed frequency is claimed. Random refill data is intended to resist compression; device-level compressibility is not measured. Read/write block sweeps use read workloads; writes are measured separately in baseline, mix, and state tests.',
'## Figures']
for f in files:report.append(f'![{f}]({P/f"{f}.png"})')
report+=['## Reproducibility and AI use','Configs and FIO JSON are retained per trial. raw.csv and summary.csv retain processed values, depth distributions, and percentile results. metadata.json records CPU, OS, storage, filesystem, governor, SMT, temperature sensors and commands. Codex generated acquisition, parsing, plotting and documentation; validation used FIO CRC32C and checked all job statuses and trial counts. The student should review and explain methodology before submission.','FIO option reference: https://fio.readthedocs.io/en/latest/fio_doc.html']
(O/'REPORT.md').write_text('\n\n'.join(report)+'\n')
canvas=Image.new('RGB',(2400,2200),'white')
for i,f in enumerate(files):
 im=Image.open(P/(f+'.png'));im.thumbnail((1180,520));x=(i%2)*1200;y=(i//2)*550;canvas.paste(im,(x+(1200-im.width)//2,y+20));ImageDraw.Draw(canvas).text((x+15,y+5),f,fill='black')
canvas.save(O/'plots-overview.png');print(O/'REPORT.md')
