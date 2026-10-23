"""Direct throughput–latency comparison from the validated long intensity run."""
from pathlib import Path
import csv, json, hashlib
import numpy as np
import matplotlib.pyplot as plt
import plot as common

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'output/intensity-dense/20261022T175507Z'
OUT=RUN/'direct-comparison'

def main():
    OUT.mkdir(exist_ok=True)
    with (RUN/'raw.csv').open() as f: raw=list(csv.DictReader(f))
    meta=json.loads((RUN/'metadata.json').read_text())
    assert len(raw)==1035 and meta['trials']==45 and meta['target_ms']==250
    summary=common.summarize_rows(raw,meta)
    with (RUN/'summary.csv').open() as f: saved=list(csv.DictReader(f))
    fields=['study','bytes','spacing','block','read_pct','random','huge','streams','threads']
    for r in summary:
        old=next(s for s in saved if all(str(r[k])==s[k] for k in fields))
        for k in ['chain_latency_ns','million_accesses_s']:
            for suffix in ['', '_q25','_q75']:
                assert np.isclose(r[k+suffix],float(old[k+suffix]))
    plt.rcParams.update({'font.size':12,'axes.titleweight':'bold'})
    fig,ax=plt.subplots(figsize=(10,6))
    reviewed=[]
    for study,param,color,marker,label in [
        ('intensity_streams','streams','#24649a','o','Independent chains on one core'),
        ('intensity_threads','threads','#b26a19','s','Physical cores, one chain per core')]:
        rows=sorted([r for r in summary if r['study']==study],key=lambda r:r[param])
        x=np.array([r['chain_latency_ns'] for r in rows]);y=np.array([r['million_accesses_s'] for r in rows])
        xerr=np.array([[r['chain_latency_ns']-r['chain_latency_ns_q25'] for r in rows],[r['chain_latency_ns_q75']-r['chain_latency_ns'] for r in rows]])
        yerr=np.array([[r['million_accesses_s']-r['million_accesses_s_q25'] for r in rows],[r['million_accesses_s_q75']-r['million_accesses_s'] for r in rows]])
        ax.errorbar(x,y,xerr=xerr,yerr=yerr,fmt='none',ecolor=color,alpha=.24,capsize=2,lw=1)
        ax.plot(x,y,marker=marker,color=color,lw=1.6,ms=5,label=label)
        for r in rows:
            reviewed.append({k:r[k] for k in ['study','streams','threads','bytes','chain_latency_ns','chain_latency_ns_q25','chain_latency_ns_q75','million_accesses_s','million_accesses_s_q25','million_accesses_s_q75']})
    ax.set(xlabel='Mean chain round-trip time (ns)',ylabel='Completed dependent loads (million/s)',xlim=(0,680),ylim=(0,145))
    ax.grid(alpha=.15);ax.set_axisbelow(True)
    ax.legend(loc='lower right',frameon=False,fontsize=10)
    fig.subplots_adjust(left=.11,right=.97,top=.97,bottom=.13)
    for ext in ['png','svg']:fig.savefig(OUT/f'throughput_latency.{ext}',dpi=200)
    plt.close(fig)
    with (OUT/'chart_data.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=reviewed[0]);w.writeheader();w.writerows(reviewed)
    (OUT/'validation.json').write_text(json.dumps({'source':str(RUN),'raw_sha256':hashlib.sha256((RUN/'raw.csv').read_bytes()).hexdigest(),'trials':len(raw),'configurations':len(summary),'summary_matches_raw':True,'metric':'software chain round-trip time, not isolated hardware request latency'},indent=2))
    print(OUT)

if __name__=='__main__':main()
