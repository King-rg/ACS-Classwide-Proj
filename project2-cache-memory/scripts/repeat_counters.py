"""Measure cache and TLB impacts with hardware counters in three acquisition rounds."""
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
    # Preserve the explicitly authorized cap_perfmon executable; do not rebuild.
    subprocess.run(['python3', str(root/'scripts/check.py')], cwd=root, check=True)
    cpus = acquisition.select_cpus()
    common = dict(mode='latency', block=8, read_pct=100, streams=1, threads=1)
    sizes_kib = [4,8,16,24,32,40,48,56,64,96,128,256,512,768,1024,
                 1152,1280,1536,2048,4096,8192,12288,16384,20480,24576,
                 28672,32768,49152,65536,98304,131072,196608]
    cases = [dict(study='working_set', bytes=n*1024, spacing=64,
                  random=1, huge=0, **common) for n in sizes_kib]
    cases += [dict(study='tlb', bytes=n*1024**2, spacing=4096,
                   random=order, huge=huge, **common)
              for n in [4,8,12,16,24,32,48,64,96,128,192]
              for order in [0,1] for huge in [0,1]]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = root/'output/counter-studies'/stamp
    output.mkdir(parents=True)
    metadata = acquisition.collect_metadata('counter-studies',45,250,cpus,'cc',
        '-O3 -march=native -std=c11 -Wall -Wextra -Wpedantic',cases)
    metadata.update(rounds=3,trials_per_round=15,order_seed=4320,
        protocol='32 random-chain working-set sizes, 64-byte node spacing, plus 11 page-locality spans with sequential/random traversal and normal/huge pages. One pinned core. Three rounds of fifteen 250 ms trials per condition, shuffled each pass with seed 4320. Fresh process and mapping per trial. Initialization, warm traversal, validation outside timing. Require hardware counters and verified huge-page backing. Preserve authorized executable; no machine-policy changes.',
        benchmark_sha256=hashlib.sha256((root/'build/memory_bench').read_bytes()).hexdigest())
    acquisition.snapshot_sources(output)
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
                assert result['counters_available'], 'Hardware counter group unavailable or multiplexed'
                if case['huge']:
                    assert result['huge_bytes'] >= case['bytes'], 'Huge-page backing incomplete'
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
    figures.plot_cache_misses(summary,metadata,plots)
    figures.plot_page_locality(summary,metadata,plots)
    (output.parent/'LATEST').write_text(stamp+'\n')
    print('COMPLETE '+str(output),flush=True)

if __name__=='__main__':
    main()
