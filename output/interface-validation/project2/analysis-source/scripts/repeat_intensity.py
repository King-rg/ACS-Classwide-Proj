"""Measure a denser concurrency sweep with three interleaved acquisition rounds."""
from pathlib import Path
import csv
import datetime
import hashlib
import json
import random
import subprocess
import run as acquisition
import analysis as figures


def write_csv(path, rows):
    with path.open('w') as target:
        writer = csv.DictWriter(target, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def main():
    root = acquisition.ROOT
    subprocess.run(['make', '-f', 'build.mk', '-C', str(root), 'check'], check=True)
    cpus = acquisition.select_cpus()
    common = dict(mode='latency', bytes=96*1024**2, spacing=64, block=8,
                  read_pct=100, random=1, huge=0)
    chains = [1,2,3,4,6,8,10,12,16,20,24,28,32,40,48,56,64]
    cases = [dict(study='intensity_threads', threads=n, streams=1, **common)
             for n in range(1, len(cpus)+1)]
    cases += [dict(study='intensity_streams', threads=1, streams=n, **common)
              for n in chains]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = root/'output/intensity-dense'/stamp
    output.mkdir(parents=True)
    metadata = acquisition.collect_metadata('intensity-dense',45,250,cpus,'cc',
        '-O3 -march=native -std=c11 -Wall -Wextra -Wpedantic',cases)
    metadata.update(rounds=3,trials_per_round=15,order_seed=4320,
        protocol='96 MiB per worker; 64-byte node spacing; random dependent chains. All physical P-core counts and 17 chain counts through 64. Three rounds of 15 trials, 250 ms each. Conditions shuffled per pass with seed 4320; fresh process/allocation per trial. Initialization, full warm traversal and validation outside timing. No machine-policy changes.',
        benchmark_sha256=hashlib.sha256((root/'build/memory_bench').read_bytes()).hexdigest())
    acquisition.snapshot_sources(output)
    (output/'PLAN.md').write_text(metadata['protocol']+'\nAssess whether throughput plateaus; do not equate software chain latency with independently measured hardware request latency. Thread footprint grows with worker count.\n')
    (output/'metadata.json').write_text(json.dumps(metadata,indent=2))
    print('OUTPUT '+str(output),flush=True)
    rng=random.Random(4320)
    rows=[]
    with (output/'raw.csv').open('w') as target:
        writer=None
        for trial in range(45):
            shuffled=cases.copy()
            rng.shuffle(shuffled)
            for case in shuffled:
                command=[str(root/'build/memory_bench'),case['mode'],
                    *[str(case[k]) for k in ['bytes','spacing','block','read_pct','random','huge','streams']],
                    '250',','.join(map(str,cpus[:case['threads']]))]
                result=json.loads(subprocess.check_output(command,text=True))
                assert result['check']=='pass' and result['elapsed_ns']>0
                row=dict(case,trial=trial,round=trial//15+1,trial_in_round=trial%15,**result)
                if writer is None:
                    writer=csv.DictWriter(target,fieldnames=row)
                    writer.writeheader()
                writer.writerow(row)
                target.flush()
                rows.append(row)
                metadata['commands'].append(command)
            print(f'Round {trial//15+1}/3, trial {trial%15+1}/15 complete',flush=True)
    assert len(rows)==len(cases)*45
    metadata['finished']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    metadata['raw_sha256']=hashlib.sha256((output/'raw.csv').read_bytes()).hexdigest()
    (output/'metadata.json').write_text(json.dumps(metadata,indent=2))
    with (output/'raw.csv').open() as source:
        rows=list(csv.DictReader(source))
    summary=figures.summarize_rows(rows,metadata)
    write_csv(output/'summary.csv',summary)
    rounds=[]
    for r in range(1,4):
        selected=[dict(row,trial=row['trial_in_round']) for row in rows if int(row['round'])==r]
        rounds += [dict(round=r,**x) for x in figures.summarize_rows(selected,dict(metadata,trials=15))]
    write_csv(output/'round_summary.csv',rounds)
    plots=output/'plots'
    plots.mkdir()
    figures.plot_intensity(summary,metadata,plots)
    (output.parent/'LATEST').write_text(stamp+'\n')
    print('COMPLETE '+str(output),flush=True)

if __name__=='__main__':
    main()
