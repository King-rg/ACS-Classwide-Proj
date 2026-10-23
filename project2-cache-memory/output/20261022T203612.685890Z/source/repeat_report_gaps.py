"""Restore required report evidence using long-run baselines and paired reuse trials.
Run from repository root: .venv-analysis/bin/python project2-cache-memory/scripts/repeat_report_gaps.py
Pass an existing output directory to regenerate plots without acquisition.
"""
from pathlib import Path
import csv, datetime, hashlib, json, subprocess, sys
import numpy as np
import matplotlib.pyplot as plt
import run as acquisition
import analysis as figures

ROOT = acquisition.ROOT
BASE = ROOT / 'output/counter-studies/20261022T183157Z'

def read(path):
    with path.open() as f:
        return list(csv.DictReader(f))

def write(path, rows):
    with path.open('w') as f:
        w = csv.DictWriter(f, fieldnames=rows[0]); w.writeheader(); w.writerows(rows)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def acquire():
    cpus = acquisition.select_cpus()
    cases = [dict(study='pitfall', mode='bandwidth', bytes=n, spacing=1024,
                  block=1024, read_pct=100, random=0, huge=0, streams=1, threads=1)
             for n in [32*1024, 192*1024**2]]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = ROOT/'output/report-gaps-long'/stamp; out.mkdir(parents=True)
    meta = acquisition.collect_metadata('report-gaps-long',45,250,cpus[:1],'cc',
        '-O3 -march=native -std=c11 -Wall -Wextra -Wpedantic',cases)
    meta.update(rounds=3,trials_per_round=15,benchmark_sha256=digest(ROOT/'build/memory_bench'),
        baseline_source=str(BASE),baseline_raw_sha256=digest(BASE/'raw.csv'),
        protocol='45 paired trials in three rounds of 15, 250 ms target each. Alternate small/large order each pair. One pinned P-core, fresh process/allocation each trial, warm-up and initialization outside timing. Preserve existing executable and machine policies. Baselines reused from verified counter-enabled long run.')
    (out/'PLAN.md').write_text('Hypothesis: repeated reads of 32 KiB will have higher useful bandwidth than the same kernel over 192 MiB because of cache reuse. Compare paired ratios and round medians; do not label small-buffer bandwidth as DRAM bandwidth. Frequency and background activity remain uncontrolled.\n'+meta['protocol']+'\n')
    acquisition.snapshot_sources(out)
    (out/'metadata.json').write_text(json.dumps(meta,indent=2))
    print('OUTPUT '+str(out),flush=True)
    with (out/'raw.csv').open('w') as f:
        writer=None
        for trial in range(45):
            order=cases if trial%2==0 else cases[::-1]
            for case in order:
                command=[str(ROOT/'build/memory_bench'),case['mode'],
                         *[str(case[k]) for k in ['bytes','spacing','block','read_pct','random','huge','streams']],
                         '250',str(cpus[0])]
                result=json.loads(subprocess.check_output(command,text=True))
                assert result['check']=='pass' and result['elapsed_ns']>=250e6
                row=dict(case,trial=trial,round=trial//15+1,trial_in_round=trial%15,**result)
                if writer is None: writer=csv.DictWriter(f,fieldnames=row);writer.writeheader()
                writer.writerow(row);f.flush();meta['commands'].append(command)
            if (trial+1)%15==0: print(f'Round {trial//15+1}/3 complete',flush=True)
    meta['finished']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    meta['raw_sha256']=digest(out/'raw.csv')
    (out/'metadata.json').write_text(json.dumps(meta,indent=2))
    (out.parent/'LATEST').write_text(stamp+'\n')
    return out

def analyze(out):
    meta=json.loads((out/'metadata.json').read_text())
    assert digest(out/'raw.csv')==meta['raw_sha256']
    assert digest(BASE/'raw.csv')==meta['baseline_raw_sha256']
    raw=read(out/'raw.csv'); assert len(raw)==90
    summary=figures.summarize_rows(raw,meta);write(out/'summary.csv',summary)
    br=[r for r in read(BASE/'raw.csv') if r['study']=='working_set' and int(r['bytes']) in [16384,524288,8388608,201326592]]
    assert len(br)==180 and all(r['random']=='1' and r['streams']=='1' and r['threads']=='1' and r['check']=='pass' and r['counters_available'].lower()=='true' for r in br)
    write(out/'baseline_raw.csv',br)
    bs=sorted(figures.summarize_rows(br,{'trials':45}),key=lambda r:r['bytes'])
    labels=['L1-sized','L2-sized','LLC-sized','DRAM-sized']
    sizes=['16 KiB','512 KiB','8 MiB','192 MiB']
    table=[dict(regime=l,span=s,trials=45,median_ns=r['ns_per_access'],q25_ns=r['ns_per_access_q25'],q75_ns=r['ns_per_access_q75'],median_core_cycles=r['cycles_per_access'],q25_core_cycles=r['cycles_per_access_q25'],q75_core_cycles=r['cycles_per_access_q75']) for l,s,r in zip(labels,sizes,bs)]
    write(out/'latency_table.csv',table)
    rounds=[]
    for rnd in range(1,4):
        rr=[dict(r,trial=r['trial_in_round']) for r in read(out/'raw.csv') if int(r['round'])==rnd]
        rounds.extend(dict(round=rnd,**r) for r in figures.summarize_rows(rr,{'trials':15}))
    write(out/'round_summary.csv',rounds)
    pairs=[]
    for t in range(45):
        pair=sorted([r for r in raw if r['trial']==t],key=lambda r:r['bytes'])
        pairs.append(dict(trial=t,round=t//15+1,small_gib_s=pair[0]['gib_s'],large_gib_s=pair[1]['gib_s'],ratio=pair[0]['gib_s']/pair[1]['gib_s']))
    write(out/'paired_ratios.csv',pairs)
    plots=out/'plots';plots.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':12,'axes.titleweight':'bold'})
    def bars(rows,metric,names,title,ylabel,filename,footer):
        med=np.array([r[metric] for r in rows]);lo=np.array([r[metric+'_q25'] for r in rows]);hi=np.array([r[metric+'_q75'] for r in rows])
        fig,ax=plt.subplots(figsize=(9,5.4))
        ax.bar(range(len(rows)),med,color=['#24649a']*len(rows),width=.58)
        ax.errorbar(range(len(rows)),med,yerr=[med-lo,hi-med],fmt='none',ecolor='#25313c',capsize=5,lw=1.5)
        for i,v in enumerate(med):ax.text(i,hi[i]+max(hi)*.035,f'{v:.2f}',ha='center',weight='bold')
        ax.set_xticks(range(len(rows)),names);ax.set_ylabel(ylabel);ax.set_title(title,pad=18)
        ax.set_ylim(0,max(hi)*1.22);ax.set_axisbelow(True);ax.grid(axis='y',alpha=.18)
        fig.subplots_adjust(bottom=.23,top=.84,left=.12,right=.97)
        fig.text(.12,.065,footer,fontsize=10,color='#475569')
        fig.savefig(plots/(filename+'.png'),dpi=200);fig.savefig(plots/(filename+'.svg'));plt.close(fig)
    bars(bs,'ns_per_access',[l+'\n'+s for l,s in zip(labels,sizes)],'Unloaded latency across representative working sets','Dependent-load latency (ns/load)','baseline_long',
         '45 trials per size · 3 rounds × 15 · 250 ms target · median and interquartile range\nOne dependent random chain; nominal cache regimes. Source: counter run 20261022T183157Z.')
    ss=sorted(summary,key=lambda r:r['bytes'])
    ratio=float(np.median([p['ratio'] for p in pairs]))
    bars(ss,'gib_s',['Reused 32 KiB buffer\nCache-sized','192 MiB span\nLarger than LLC'],f'Cache reuse raises measured bandwidth: {ratio:.1f}× paired median','Useful read bandwidth (GiB/s)','cache_reuse_long',
         '45 paired trials · 3 rounds × 15 · 250 ms target · median and interquartile range\nSame sequential read kernel, 1 KiB blocks, one pinned core; alternating buffer order.')
    validation=dict(baseline_trials=len(br),new_trials=len(raw),all_checks_passed=True,
        min_new_trial_ms=min(float(r['elapsed_ns'])/1e6 for r in raw),
        paired_ratio_median=ratio,paired_ratio_q25=float(np.percentile([p['ratio'] for p in pairs],25)),paired_ratio_q75=float(np.percentile([p['ratio'] for p in pairs],75)),
        per_round_ratio_medians=[float(np.median([p['ratio'] for p in pairs if p['round']==n])) for n in [1,2,3]],
        baseline_source=str(BASE),limitations='Uncontrolled frequency/background activity. Baseline includes translation and loop overhead; cache-size labels do not prove individual-load residency. Error bars are observation spread, not confidence intervals. Useful payload bandwidth is not controller traffic.')
    (out/'validation.json').write_text(json.dumps(validation,indent=2))
    print(json.dumps(dict(output=str(out),baseline=table,reuse=[{k:r[k] for k in ['bytes','gib_s','gib_s_q25','gib_s_q75']} for r in ss],validation=validation),indent=2),flush=True)

if __name__=='__main__':
    analyze(Path(sys.argv[1]) if len(sys.argv)>1 else acquire())
