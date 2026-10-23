"""Eight spec-mapped figures, with explicit gaps instead of invented counters."""
from pathlib import Path
import sys,csv,json,collections
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1]
O=Path(sys.argv[1]) if len(sys.argv)>1 else R/'output'/(R/'output/LATEST').read_text().strip()
P=O/'plots';P.mkdir(exist_ok=True);meta=json.loads((O/'metadata.json').read_text());rows=list(csv.DictReader((O/'raw.csv').open()))
keys=['study','mode','bytes','spacing','block','read_pct','random','huge','streams','threads'];G=collections.defaultdict(list)
for row in rows:
 assert row['check']=='pass'
 for k in keys[2:]+['trial','huge_bytes']:row[k]=int(row[k])
 for k in ['elapsed_ns','operations','payload_bytes','ns_per_access','chain_latency_ns','million_accesses_s','gib_s','cycles','llc_read_misses','dtlb_read_misses']:row[k]=float(row[k])
 row['perf']=row['counters_available'].lower()=='true'
 row['cycles_per_access']=row['cycles']/row['operations'] if row['perf'] else float('nan')
 row['llc_misses_per_1000']=1000*row['llc_read_misses']/row['operations'] if row['perf'] else float('nan')
 row['dtlb_misses_per_1000']=1000*row['dtlb_read_misses']/row['operations'] if row['perf'] else float('nan')
 G[tuple(row[k] for k in keys)].append(row)
summary=[]
for key,rr in G.items():
 assert sorted(x['trial'] for x in rr)==list(range(meta['trials']))
 s=dict(zip(keys,key));s['huge_verified']=all(x['huge_bytes']>=x['bytes']*x['threads'] for x in rr);s['counters_available']=all(x['perf'] for x in rr)
 for metric in ['ns_per_access','chain_latency_ns','million_accesses_s','gib_s','cycles_per_access','llc_misses_per_1000','dtlb_misses_per_1000']:
  a=np.array([x[metric] for x in rr]);s[metric]=np.median(a);s[metric+'_q25']=np.percentile(a,25);s[metric+'_q75']=np.percentile(a,75)
 summary.append(s)
with (O/'summary.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=summary[0]);w.writeheader();w.writerows(summary)
def sel(study,**kw):return sorted([s for s in summary if s['study']==study and all(s[k]==v for k,v in kw.items())],key=lambda s:(s['bytes'],s['spacing'],s['block'],s['read_pct'],s['streams'],s['threads']))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','figure.facecolor':'white','savefig.facecolor':'white'})
colors=['#24649a','#bb6c16','#477d62','#8e679b'];files=[]
def save(fig,name):
 fig.savefig(P/(name+'.png'),dpi=220,bbox_inches='tight');fig.savefig(P/(name+'.svg'),bbox_inches='tight');plt.close(fig);files.append(name)
def line(ax,x,ss,m,label,c,ls='-',marker='o'):
 y=[s[m] for s in ss];ax.plot(x,y,label=label,color=c,ls=ls,marker=marker,ms=4);ax.fill_between(x,[s[m+'_q25'] for s in ss],[s[m+'_q75'] for s in ss],color=c,alpha=.13);ax.grid(axis='y',alpha=.18)
def cacheaxis(ax):
 ax.set_xscale('log',base=2);ax.set_xticks([4*1024,64*1024,1024**2,16*1024**2,192*1024**2],['4 KiB','64 KiB','1 MiB','16 MiB','192 MiB']);ax.set_xlabel('Mapped working-set span')
 for c in meta['caches']:
  ax.axvline(c['bytes'],color='#777',ls=':',lw=1);ax.text(c['bytes'],.97,'L'+str(c['level']),transform=ax.get_xaxis_transform(),ha='right',va='top',fontsize=9)
# 1: unloaded baseline, representative nominal capacities, not measured residency.
base=[sel('working_set',bytes=n,random=1)[0] for n in [16*1024,512*1024,8*1024**2,192*1024**2]]
fig,ax=plt.subplots(figsize=(9,4.5),layout='constrained');y=np.array([s['ns_per_access'] for s in base]);lo=np.array([s['ns_per_access_q25'] for s in base]);hi=np.array([s['ns_per_access_q75'] for s in base]);ax.bar(range(4),y,yerr=[y-lo,hi-y],capsize=4,color=colors[0]);ax.set_xticks(range(4),['L1-sized\n16 KiB','L2-sized\n512 KiB','LLC-sized\n8 MiB','DRAM-sized\n192 MiB']);ax.set_ylabel('Dependent-load latency (ns)');ax.set_title('Unloaded random pointer-chain baseline');ax.grid(axis='y',alpha=.15)
for i,v in enumerate(y):ax.text(i,hi[i]+max(y)*.03,f'{v:.2f}',ha='center');ax.set_ylim(0,max(hi)*1.2)
save(fig,'01_zero_queue')
# 2: independent latency and streaming payload measures.
fig,axs=plt.subplots(1,2,figsize=(13,4.7),layout='constrained')
for order,c in [(0,colors[0]),(1,colors[1])]:
 ss=sorted(sel('pattern_latency',random=order),key=lambda s:s['spacing']);line(axs[0],[s['spacing'] for s in ss],ss,'ns_per_access','Sequential' if order==0 else 'Random',c)
 for gap in [1,4]:
  ss=sorted([s for s in sel('pattern_bandwidth',random=order) if s['spacing']==gap*s['block']],key=lambda s:s['block']);line(axs[1],[s['block'] for s in ss],ss,'gib_s',('Sequential' if order==0 else 'Random')+(' · dense' if gap==1 else ' · 4× spacing'),c,'-' if gap==1 else '--')
axs[0].set_xscale('log',base=2);axs[0].set_xticks([64,256,1024],['64','256','1024']);axs[0].set_xlabel('Pointer spacing (bytes)');axs[0].set_ylabel('Dependent-load latency (ns)');axs[0].set_title('96 MiB pointer chain');axs[0].legend(frameon=False)
axs[1].set_xscale('log',base=2);axs[1].set_xticks([8,64,256,1024],['8','64','256','1024']);axs[1].set_xlabel('Useful bytes per transfer');axs[1].set_ylabel('Useful bandwidth (GiB/s)');axs[1].set_title('96 MiB transfer sweep');axs[1].legend(frameon=False,fontsize=9);save(fig,'02_pattern_granularity')
# 3: ns/block is block service time, not an individual DRAM response latency.
fig,axs=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
for ax,metric,label in zip(axs,['gib_s','ns_per_access'],['Useful bandwidth (GiB/s)','Average block processing time (ns)']):
 for order,c in [(0,colors[0]),(1,colors[1])]:
  ss=[sel('mix',read_pct=r,random=order)[0] for r in [100,70,50,0]];line(ax,range(4),ss,metric,'Sequential' if order==0 else 'Random',c)
 ax.set_xticks(range(4),['100/0','70/30','50/50','0/100']);ax.set_xlabel('Read/write ratio (%)');ax.set_ylabel(label);ax.set_ylim(bottom=0);ax.legend(frameon=False)
fig.suptitle('Read/write mix · 96 MiB · 1 KiB transfers');save(fig,'03_read_write_mix')
# 4: chain latency includes intervening work with multiple chains.
fig,axs=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
for ax,study,param,title in zip(axs,['intensity_threads','intensity_streams'],['threads','streams'],['Separate physical cores','Independent chains on one core']):
 ss=sorted(sel(study),key=lambda s:s[param]);ax.plot([s['million_accesses_s'] for s in ss],[s['chain_latency_ns'] for s in ss],'-o',color=colors[0])
 for s in ss:ax.annotate(str(s[param]),(s['million_accesses_s'],s['chain_latency_ns']),xytext=(5,5),textcoords='offset points')
 ax.set_xlabel('Completed dependent loads (million/s)');ax.set_ylabel('Mean chain round-trip time (ns)');ax.set_title(title);ax.grid(alpha=.18)
save(fig,'04_intensity')
# 5: working set and annotated capacities.
fig,axs=plt.subplots(1,2,figsize=(13,4.7),layout='constrained')
for order,c in [(0,colors[0]),(1,colors[1])]:
 ss=sel('working_set',random=order)
 for ax,m,label in zip(axs,['ns_per_access','million_accesses_s'],['Dependent-load latency (ns)','Completed dependent loads (million/s)']):line(ax,[s['bytes'] for s in ss],ss,m,'Sequential' if order==0 else 'Random',c);cacheaxis(ax);ax.set_ylabel(label);ax.legend(frameon=False)
save(fig,'05_working_set')
# 6: never plot denied counters as zero.
fig,axs=plt.subplots(1,2,figsize=(13,4.7),layout='constrained');ss=sel('working_set',random=1);line(axs[0],[s['bytes'] for s in ss],ss,'ns_per_access','Random chain',colors[0]);cacheaxis(axs[0]);axs[0].set_ylabel('Dependent-load latency (ns)');axs[0].set_title('Measured runtime impact')
if all(s['counters_available'] for s in ss):line(axs[1],[s['bytes'] for s in ss],ss,'llc_misses_per_1000','LLC read misses',colors[1]);cacheaxis(axs[1]);axs[1].set_ylabel('LLC read misses / 1,000 loads')
else:axs[1].axis('off');axs[1].text(.5,.5,'Counter correlation unavailable\n\nperf_event_open was denied or the group\ncould not run without multiplexing.\nTiming alone does not establish cache misses.',ha='center',va='center',transform=axs[1].transAxes)
save(fig,'06_cache_miss_impact')
# 7: verified huge page labels; request without backing is explicitly marked.
fig,axs=plt.subplots(1,2,figsize=(13,4.7),layout='constrained')
for ax,order in zip(axs,[0,1]):
 for huge,c in [(0,colors[0]),(1,colors[1])]:
  ss=sel('tlb',random=order,huge=huge);label='4 KiB pages' if not huge else ('Verified THP backing' if all(s['huge_verified'] for s in ss) else 'THP requested; backing incomplete')
  line(ax,[s['bytes']/1024**2 for s in ss],ss,'ns_per_access',label,c)
 ax.set_xscale('log',base=2);ax.set_xticks([4,16,64,192],['4','16','64','192']);ax.set_xlabel('Mapped span (MiB), one load per 4 KiB');ax.set_ylabel('Dependent-load latency (ns)');ax.set_title('Sequential pages' if order==0 else 'Random pages');ax.legend(frameon=False,fontsize=9)
save(fig,'07_tlb_pages')
# 8: warm cache versus beyond LLC under otherwise matched transfer code.
fig,ax=plt.subplots(figsize=(8,4.5),layout='constrained');ss=sel('pitfall');m=np.array([s['gib_s'] for s in ss]);lo=np.array([s['gib_s_q25'] for s in ss]);hi=np.array([s['gib_s_q75'] for s in ss]);ax.bar(range(2),m,color=colors[:2],yerr=[m-lo,hi-m],capsize=4);ax.set_xticks([0,1],['Reused 32 KiB buffer','Reused 192 MiB buffer']);ax.set_ylabel('Useful read bandwidth (GiB/s)');ax.set_title('Pitfall: cache reuse is not DRAM bandwidth');ax.grid(axis='y',alpha=.15);save(fig,'08_cache_reuse_pitfall')
# Save a baseline table and explicit availability/status.
with (O/'latency_table.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=['regime','span_bytes','latency_ns','q25_ns','q75_ns','cycles_per_load']);w.writeheader()
 for label,s in zip(['L1-sized','L2-sized','LLC-sized','DRAM-sized'],base):w.writerow(dict(regime=label,span_bytes=s['bytes'],latency_ns=s['ns_per_access'],q25_ns=s['ns_per_access_q25'],q75_ns=s['ns_per_access_q75'],cycles_per_load=s['cycles_per_access'] if s['counters_available'] else 'unavailable'))
coverage={'profile':meta['profile'],'trials':len(rows),'configurations':len(summary),'correctness':'all passed','hardware_counters':all(s['counters_available'] for s in summary),'huge_pages_verified':all(s['huge_verified'] for s in sel('tlb',huge=1)),'missing_required_evidence':[]}
if not coverage['hardware_counters']:coverage['missing_required_evidence']=['Cache-miss/runtime correlation','TLB-miss/runtime correlation','Core cycles per access']
(O/'coverage.json').write_text(json.dumps(coverage,indent=2))
# Narrative pilot report and inspectable gallery.
parts=['# Project 2 pilot results' if meta['profile']=='quick' else '# Project 2 results',f"{len(rows)} validated observations across {len(summary)} configurations. {meta['trials']} trials per configuration; median and interquartile range. This is a short pilot, not a claim of a stable hardware limit." if meta['profile']=='quick' else f"{len(rows)} validated observations; {meta['trials']} trials per configuration.",'## Unloaded latency baseline','| Nominal regime | Span | Median ns/load |','|---|---:|---:|']
for label,s in zip(['L1-sized','L2-sized','LLC-sized','DRAM-sized'],base):parts.append(f"| {label} | {s['bytes']/1024:g} KiB | {s['ns_per_access']:.2f} |")
parts+=['','The labels refer to nominal cache capacities. Sequential prefetching, software overhead, page translation and other machine activity also affect observed latency. No core-cycle conversion is invented when counters are inaccessible.','## Required figures']
labels=['Zero-queue approximation: unloaded dependent-load baseline','Pattern and transfer-granularity sweep','Read/write mix sweep','Intensity: throughput versus chain latency','Working-set sweep across cache capacities','Cache-miss impact: timing plus counter availability','Page locality and verified huge pages','Pitfall: warm cache mistaken for DRAM bandwidth']
for file,label in zip(files,labels):parts += ['### '+label,f'![{label}]({(P/(file+".png")).resolve()})','']
intensity=sorted(sel('intensity_streams'),key=lambda x:x['streams'])
small,large=sel('pitfall')
parts+=['## Observations',f"The small reused buffer measured {small['gib_s']:.2f} GiB/s versus {large['gib_s']:.2f} GiB/s for the 192 MiB buffer, a {small['gib_s']/large['gib_s']:.1f}× difference. The small-buffer result is cache bandwidth, not DRAM bandwidth.",f"Across {intensity[0]['streams']} to {intensity[-1]['streams']} independent chains, throughput increased from {intensity[0]['million_accesses_s']:.2f} to {intensity[-1]['million_accesses_s']:.2f} million loads/s, while mean chain round-trip time changed from {intensity[0]['chain_latency_ns']:.2f} to {intensity[-1]['chain_latency_ns']:.2f} ns. The tested pilot range does not by itself establish a stable saturation knee."]
parts+=['## Interpretation and limits',f"Huge-page backing verified for all THP cases: **{coverage['huge_pages_verified']}**. Hardware counters available throughout: **{coverage['hardware_counters']}**.",'The cache/TLB studies include measured timing, but a denied counter means the required miss correlation remains open. No missing counter is rendered as a zero.','Bandwidth counts useful payload, not actual DRAM bus traffic. Average block processing time in the mix study is not an individual memory-request latency.','For the intensity sweep, throughput × mean chain round-trip time estimates the number of software-active chains. This is a consistency check of the software concurrency, not an independent estimate of hardware MSHR occupancy. A short pilot may not exhibit a definitive saturation knee.','The page-locality sweep holds one data access per 4 KiB of mapped span; its touched cache-line footprint is smaller than its virtual span. THP can change translation locality without requiring a whole-span data working set.','## Reproduction','Run `make full`, then use the plotting command in the project README. Raw CSVs, processed tables, run metadata, source snapshots and SHA-256 are retained beside these figures.','## AI-use note','Codex assisted with this C harness, acquisition/plotting scripts and setup documentation. Pointer-ring uniqueness, bounds, data checksums, writes, and input rejection were exercised. Counter results and huge-page backing are checked rather than assumed.']
(O/'REPORT.md').write_text('\n\n'.join(parts).replace('|\n\n|','|\n|'));print(json.dumps(coverage,indent=2));print(O/'REPORT.md')
