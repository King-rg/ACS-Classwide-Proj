import os
"""Report-styled figures from the completed hierarchy experiment; no acquisition."""
from pathlib import Path
import sys,math,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'shared'))
from report_common import read_csv,digest,write_json
from project2_hierarchy import summarize
RUN=Path(json.loads(os.environ['REPORT_SOURCES'])['hierarchy'])
OUT=Path(os.environ['REPORT_DEST']);OUT.mkdir(exist_ok=True)
rows=summarize(read_csv(RUN/'raw.csv'));x=np.array([r['bytes'] for r in rows])
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.labelsize':9,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'legend.frameon':False,'axes.spines.top':False,'axes.spines.right':False,'axes.axisbelow':True,'savefig.facecolor':'white','svg.hashsalt':'project2-hierarchy-report'})
def curve(ax,key,color,label,support=None):
 def v(s=''):return np.array([np.nan if r[key+s] is None else r[key+s] for r in rows])
 y=v();ax.plot(x,y,color=color,lw=1.4,label=label)
 ax.fill_between(x,v('_q25'),v('_q75'),color=color,alpha=.14,lw=0)
 good=np.isfinite(y);solid=np.array([r[support]>=math.ceil(.8*r['trials']) for r in rows]) if support else good
 ax.scatter(x[good&solid],y[good&solid],s=9,color=color,zorder=3)
 ax.scatter(x[good&~solid],y[good&~solid],s=13,facecolors='white',edgecolors=color,zorder=3)
def decorate(ax):
 ax.set_xscale('log',base=2);ax.set_xlim(3500,230000000)
 ax.set_xticks([4096,32768,262144,2097152,16777216,201326592],['4 KiB','32 KiB','256 KiB','2 MiB','16 MiB','192 MiB'])
 ax.grid(axis='y',color='#dfe3e8',lw=.6)
 for label,value in [('L1',49152),('L2',1310720),('L3',25165824)]:
  ax.axvline(value,color='#777',lw=.7,ls='--');ax.text(value,.98,label,transform=ax.get_xaxis_transform(),ha='right',va='top',fontsize=7.5,color='#555')
 ax.axvspan(25165824,201326592,color='#858585',alpha=.07,lw=0);ax.margins(y=.15)
def save(fig,name):
 for ext in ['png','svg','pdf']:fig.savefig(OUT/f'{name}.{ext}',dpi=240)
 plt.close(fig)
fig,axs=plt.subplots(3,1,figsize=(6.5,6.0),sharex=True,layout='constrained')
for ax,key,label,color,support in zip(axs,['m','h_ns','p_ns'],['DRAM-served fraction, m','Cache-hit time, h (ns)','Extra miss cost, p (ns)'],['#24649a','#24649a','#bb6c16'],[None,'h_supported_trials','p_supported_trials']):
 curve(ax,key,color,label,support);decorate(ax);ax.set_ylabel(label)
axs[0].set_ylim(-.03,1.17);axs[-1].set_xlabel('Working-set size');save(fig,'fig6a')
fig,ax=plt.subplots(figsize=(6.5,3.2),layout='constrained')
curve(ax,'measured_ns','#24649a','Timed access');curve(ax,'amat_ns','#bb6c16','Reconstructed AMAT','amat_supported_trials');decorate(ax)
ax.set(xlabel='Working-set size',ylabel='Average time per read (ns)');ax.legend(loc='upper left');save(fig,'fig6b')
write_json(OUT/'manifest.json',dict(run=str(RUN),raw_sha256=digest(RUN/'raw.csv'),trials=30,width_pt=468,fig6a_height_pt=432,fig6b_height_pt=230.4))
print(OUT)
