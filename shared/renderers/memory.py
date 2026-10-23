import os
"""Reproduce report panels from the frozen consolidated run; never acquire data."""
from pathlib import Path
import csv
import hashlib
import json
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

HERE = Path(__file__).resolve().parent
RUN = Path(json.loads(os.environ['REPORT_SOURCES'])['base'])
OUT = Path(os.environ['REPORT_DEST'])
OUT.mkdir(exist_ok=True)
BLUE, ORANGE = '#24649a', '#bb6c16'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,
    'axes.labelsize':9,'xtick.labelsize':8,'ytick.labelsize':8,
    'legend.fontsize':8,'legend.frameon':False,'axes.spines.top':False,
    'axes.spines.right':False,'axes.axisbelow':True,'axes.grid':False,
    'savefig.facecolor':'white','svg.hashsalt':'project2-report-20261022'})
used=[]
def read(name):
    path=RUN/'tables'/f'{name}.csv'
    used.append({'path':str(path.relative_to(RUN)), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    return list(csv.DictReader(path.open()))
def panel(ax,name,xlabel,ylabel,log=False,cache=False,legend=True):
    rows=read(name)
    for i,s in enumerate(dict.fromkeys(r['series'] for r in rows)):
        rr=[r for r in rows if r['series']==s]
        x=np.array([float(r['x']) for r in rr]);y=np.array([float(r['y']) for r in rr])
        col=rr[0].get('color') or [BLUE,ORANGE][i%2]
        marker=rr[0].get('marker') or ['o','s'][i%2]
        ax.plot(x,y,label=s,color=col,marker=marker,markersize=3,
                linestyle=rr[0].get('linestyle') or '-',linewidth=1.4)
        ax.fill_between(x,[float(r['y_q25']) for r in rr],
                        [float(r['y_q75']) for r in rr],color=col,alpha=.14,linewidth=0)
    ax.set(xlabel=xlabel,ylabel=ylabel)
    ax.grid(axis='y',color='#dfe3e8',lw=.6)
    if log: ax.set_xscale('log',base=2)
    if cache:
        for label,v in [('L1',49152),('L2',1310720),('L3',25165824)]:
            ax.axvline(v,color='#777',lw=.7,ls='--')
            ax.text(v,.98,label,transform=ax.get_xaxis_transform(),ha='right',va='top',fontsize=7.5,color='#555')
        ax.axvspan(25165824,201326592,color='#858585',alpha=.07,lw=0)
        ax.set_xticks([4096,32768,262144,2097152,16777216,201326592],['4 KiB','32 KiB','256 KiB','2 MiB','16 MiB','192 MiB'])
        ax.set_xlim(3500,230000000)
        ax.margins(y=.15)
    else: ax.set_ylim(bottom=0)
    if log and not cache:
        ticks=[8,32,128,512,1024] if 'granularity' in name else [64,128,256,512,1024]
        if name.startswith('09'): ticks=[4,8,16,32,64,192]
        ax.set_xticks(ticks,[str(t) for t in ticks])
    if legend: ax.legend(loc='best')
    return rows
manifest=[]
def save(fig,name):
    fig.savefig(OUT/f'{name}.png',dpi=240)
    fig.savefig(OUT/f'{name}.svg')
    manifest.append({'figure':name,'width_pt':468,'height_pt':round(fig.get_figheight()*72,2),
                     'tables':list({r['path']:r for r in used}.values())})
    used.clear();plt.close(fig)
def make(rows=1,cols=1,height=2.8):
    return plt.subplots(rows,cols,figsize=(6.5,height),layout='constrained',squeeze=False)
def bars(name,table,labels,ylabel):
    fig,aa=make();ax=aa[0,0];rr=read(table);y=np.array([float(r['y']) for r in rr])
    ax.bar(range(len(rr)),y,color=BLUE,width=.55,
           yerr=[y-[float(r['y_q25']) for r in rr],[float(r['y_q75']) for r in rr]-y],capsize=4)
    ax.set_xticks(range(len(rr)),labels);ax.set_ylabel(ylabel);ax.grid(axis='y',color='#dfe3e8',lw=.6)
    ax.set_ylim(0,max(float(r['y_q75']) for r in rr)*1.23)
    for i,v in enumerate(y):ax.text(i,float(rr[i]['y_q75'])+ax.get_ylim()[1]*.025,f'{v:.2f}',ha='center',fontsize=9)
    save(fig,name)

bars('fig1','01_baseline',['16 KiB\nL1-sized','512 KiB\nL2-sized','8 MiB\nL3-sized','192 MiB\nDRAM-sized'],'Dependent-load latency (ns)')
fig,aa=make(2,height=4.9)
panel(aa[0,0],'02_pattern_latency','Pointer spacing (bytes)','Dependent-load latency (ns)',True)
panel(aa[1,0],'03_granularity_bandwidth','Useful bytes per transfer','Useful bandwidth (GiB/s)',True)
aa[1,0].legend(ncol=2,fontsize=7.8)
save(fig,'fig2a')

fig,aa=make(height=3.0);ax=aa[0,0];rr=read('11_paired_bandwidth_ratio')
for i,s in enumerate(dict.fromkeys(r['series'] for r in rr)):
    r=[r for r in rr if r['series']==s];x=np.array([float(v['x']) for v in r]);y=np.array([float(v['y']) for v in r])
    if i==0:ax.errorbar(x,y,yerr=[y-[float(v['y_q25']) for v in r],[float(v['y_q75']) for v in r]-y],fmt='o-',color=BLUE,capsize=3,markersize=4,linewidth=1.6,zorder=4,label=s)
    else:ax.plot(x,y,color=ORANGE,marker=['s','^','D'][i-1],markerfacecolor='none',markersize=4,linestyle=['--',':','-.'][i-1],linewidth=.9,alpha=.8,label=s)
ax.set(xscale='log',xlabel='Useful bytes per transfer (four-times spacing)',ylabel='Random / sequential bandwidth (×)',ylim=(0,1.18))
ax.set_xticks([8,32,64,128,256,512,1024],['8','32','64','128','256','512','1024'])
ax.axhline(1,color='#555',ls='--',lw=.8);ax.grid(axis='y',color='#dfe3e8',lw=.6);ax.legend(ncol=4,fontsize=7.5,loc='upper left')
save(fig,'fig2b')

fig,aa=make(2,height=4.7)
panel(aa[0,0],'04_mix_gib_s','Writes (%)','Useful bandwidth (GiB/s)')
panel(aa[1,0],'04_mix_ns_per_access','Writes (%)','Average block-processing time (ns)')
save(fig,'fig3')

fig,aa=make(2,2,height=4.9)
for col,study,key in [(0,'threads','Physical cores'),(1,'streams','Independent chains')]:
    for row,metric,label in [(0,'million_accesses_s','Completed loads\n(million/s)'),(1,'chain_latency_ns','Mean chain round-trip\ntime (ns)')]:
        panel(aa[row,col],f'05_intensity_{study}_{metric}',key,label,legend=False)
    aa[0,col].set_title('One chain per core' if col==0 else 'Multiple chains on one core',fontsize=9)
save(fig,'fig4a')

fig,aa=make(height=3.2);ax=aa[0,0];rr=read('06_throughput_latency')
for i,s in enumerate(dict.fromkeys(r['series'] for r in rr)):
    r=[r for r in rr if r['series']==s];x=np.array([float(v['x']) for v in r]);y=np.array([float(v['y']) for v in r])
    ax.errorbar(x,y,xerr=[x-[float(v['x_q25']) for v in r],[float(v['x_q75']) for v in r]-x],
        yerr=[y-[float(v['y_q25']) for v in r],[float(v['y_q75']) for v in r]-y],
        fmt='o-' if i==0 else 's-',color=[BLUE,ORANGE][i],ecolor=[BLUE+'55',ORANGE+'55'][i],
        linewidth=1.4,markersize=3,capsize=2,label='Independent chains, one core' if i==0 else 'One chain per physical core')
    if i==0:
        for v in r:
            if int(v['concurrency']) in [1,24,32,64]:
                ax.annotate(v['concurrency'],(float(v['x']),float(v['y'])),xytext=(3,7),textcoords='offset points',fontsize=8,color=BLUE)
ax.set(xlabel='Mean chain round-trip time (ns)',ylabel='Completed loads (million/s)',ylim=(0,160))
ax.grid(axis='y',color='#dfe3e8',lw=.6);ax.legend(loc='upper left',fontsize=8)
save(fig,'fig4b')

fig,aa=make(2,height=4.9)
panel(aa[0,0],'07_working_set_ns_per_access','Mapped span','Dependent-load latency (ns)',True,True)
panel(aa[1,0],'07_working_set_million_accesses_s','Mapped span','Completed loads (million/s)',True,True)
save(fig,'fig5')
fig,aa=make(2,height=4.9)
panel(aa[0,0],'08_cache_ns_per_access','Mapped span','Dependent-load latency (ns)',True,True,False)
panel(aa[1,0],'08_cache_llc_misses_per_1000','Mapped span','L3 read misses per 1,000 loads',True,True,False)
save(fig,'fig6')

fig,aa=make(2,2,height=4.9)
for col,order in enumerate([0,1]):
    for row,metric,label in [(0,'ns_per_access','Dependent-load\nlatency (ns)'),(1,'dtlb_misses_per_1000','dTLB read misses\nper 1,000 loads')]:
        panel(aa[row,col],f'09_tlb_{order}_{metric}','Mapped span (MiB)',label,True,False,row==0)
    aa[0,col].set_title('Sequential page order' if order==0 else 'Random page order',fontsize=9)
save(fig,'fig7')
bars('fig8','10_cache_reuse',['32 KiB','192 MiB'],'Useful read bandwidth (GiB/s)')
(OUT/'manifest.json').write_text(json.dumps({'run':RUN.name,'figures':manifest,
    'analysis_environment':{'python':sys.version.split()[0],'numpy':np.__version__,'matplotlib':matplotlib.__version__}},indent=2)+'\n')
print(f'Created {len(manifest)} report figures from {RUN.name}')
