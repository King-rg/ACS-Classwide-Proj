#!/usr/bin/env python3
"""Validate and plot a real frequency_sweep.py run, including partial stopped runs."""
import csv,json,sys,pathlib,statistics,math,hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
P=pathlib.Path
p=P(sys.argv[1]).resolve()
status=json.loads((p/'status.json').read_text());restore=json.loads((p/'restoration.json').read_text())
rows=[json.loads(l) for l in (p/'measurements.jsonl').read_text().splitlines()] if (p/'measurements.jsonl').exists() else []
t=[json.loads(l) for l in (p/'telemetry.jsonl').read_text().splitlines()] if (p/'telemetry.jsonl').exists() else []
def csvwrite(name,records):
 if not records:return
 fields=list(dict.fromkeys(k for r in records for k in r))
 with (p/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in records)
csvwrite('measurements.csv',rows);csvwrite('telemetry.csv',t)
summary=[]
for key in sorted({(r['requested_khz'],r['workload']) for r in rows}):
 group=[r for r in rows if (r['requested_khz'],r['workload'])==key]
 assert sorted(r['interval'] for r in group)==[0,1,2,3]
 for r in group:
  assert r['cycles']>0 and r['running']==r['enabled'] and r['cpu_s']>0
  expected=r['calls']*(8192*128 if key[1]=='compute' else 2048*2)
  assert r['operations']==expected
  assert math.isclose(r['gflops'],expected/r['wall_s']/1e9,rel_tol=1e-12)
  assert math.isclose(r['effective_mhz'],r['cycles']/r['cpu_s']/1e6,rel_tol=1e-12)
 g=[r for r in group if not r['warmup']];s={'requested_khz':key[0],'workload':key[1],'repeats':len(g)}
 for metric in ('gflops','effective_mhz','utilization'):
  values=[r[metric] for r in g];s[metric]=statistics.median(values);s[metric+'_min']=min(values);s[metric+'_max']=max(values)
 summary.append(s)
csvwrite('summary.csv',summary)
validation={'checked_intervals':len(rows),'summary_points':len(summary),'restoration_verified':restore['verified'],'state':status,'source_hashes':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in p.glob('*.jsonl')}}
(p/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
if '--validate-only' in sys.argv:
 print(json.dumps(validation,indent=2));sys.exit(0)
if not summary:
 print('No complete workload measurements: '+json.dumps(status));sys.exit(0)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','pdf.fonttype':42})
colors={'compute':'#24649a','dot':'#c76b14'};labels={'compute':'AVX2/FMA register compute (float32)','dot':'Assignment AVX2 dot product (float32; 16 KiB)'}
def finish(fig,name,title,note):
 fig.suptitle(title,x=.07,ha='left',fontsize=23,fontweight='bold',color='#173849')
 fig.text(.07,.03,note,fontsize=10,color='#445666',va='bottom')
 fig.subplots_adjust(left=.09,right=.96,top=.85,bottom=.20,wspace=.22,hspace=.30)
 for ext in ('png','svg','pdf'):fig.savefig(p/f'{name}.{ext}',dpi=300,facecolor='white')
 im=Image.open(p/f'{name}.png');assert im.width==5400;im.thumbnail((1600,1200));im.save(p/f'{name}_preview.png');plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(18,10))
for mode in colors:
 g=[s for s in summary if s['workload']==mode];x=[s['requested_khz']/1e6 for s in g]
 for ax,metric,scale in [(axes[0],'gflops',1),(axes[1],'effective_mhz',.001)]:
  y=[s[metric]*scale for s in g];lo=[(s[metric]-s[metric+'_min'])*scale for s in g];hi=[(s[metric+'_max']-s[metric])*scale for s in g]
  ax.errorbar(x,y,yerr=[lo,hi],color=colors[mode],marker='o' if mode=='compute' else 's',linestyle='-' if mode=='compute' else '--',capsize=4,label=labels[mode])
for ax in axes:ax.set_xlabel('Requested min/max frequency (GHz)');ax.set_xlim(left=0);ax.set_ylim(bottom=0);ax.grid(alpha=.18)
axes[0].set_ylabel('Throughput (GFLOP/s; higher is faster)');axes[1].set_ylabel('Measured execution clock (GHz)')
maxf=max(s['requested_khz'] for s in summary)/1e6;axes[1].plot([0,maxf],[0,maxf],':',color='#555555',label='Requested = measured')
axes[0].legend(fontsize=10,loc='best');axes[1].legend(fontsize=10,loc='best')
note='Median and range of 3 consecutive 0.75 s intervals after 0.75 s warmup per workload. CPU 0 pinned; sibling remains online.\nClock: user core cycles / thread CPU time; requests are not guaranteed locks. No new independent process repeats.\n'+f"Run state: {status['state']}; restoration verified: {restore['verified']}. Short test does not establish maximum sustained stable frequency."
finish(fig,'performance_vs_frequency','Single-core SIMD performance versus requested frequency',note)
if t:
 fig,axes=plt.subplots(2,1,figsize=(18,10),sharex=True)
 for mode in colors:
  g=[r for r in t if r['workload']==mode]
  axes[0].scatter([r['elapsed_s'] for r in g],[r['delivered_mhz_wall']/1000 for r in g],s=15,color=colors[mode],label=labels[mode])
 axes[0].plot([r['elapsed_s'] for r in t],[r['requested_khz']/1e6 for r in t],color='#555555',linestyle=':',label='Requested min/max')
 axes[0].set_ylabel('CPU0 delivered clock (GHz)');axes[0].set_ylim(bottom=0);axes[0].legend(fontsize=9,ncol=3)
 axes[1].plot([r['elapsed_s'] for r in t],[r['package_max_c'] for r in t],color='#c76b14',label='Maximum across package/core sensors')
 plan=json.loads((p/'plan.json').read_text());axes[1].axhline(plan['stop_temperature_c'],color='#555555',linestyle='--',label='Conservative stop threshold')
 axes[1].set_ylabel('Temperature (°C)');axes[1].set_xlabel('Elapsed test time (seconds)');axes[1].legend(fontsize=10)
 for ax in axes:ax.grid(alpha=.18);ax.set_xlim(left=0)
 finish(fig,'clock_temperature_timeline','Measured clock and temperature during the bounded sweep','Clock: CPU0 APERF delta / wall time, including idle; sampled about every 0.25 s. APERF/MPERF ratio is retained in telemetry.csv.\nTemperature is package-wide maximum, not solely the tested core. Gaps are cooldowns. Throttle counters are retained in telemetry.csv.\n'+f"Run state: {status['state']}; restoration verified: {restore['verified']}. "+status.get('reason','Factory thermal and power protections unchanged.'))
print(json.dumps(validation,indent=2));print(p)
