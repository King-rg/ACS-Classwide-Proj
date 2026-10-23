#!/usr/bin/env python3
"""Build, snapshot and run bounded pinned Project-1 experiments without overwrites."""
import argparse, csv, datetime, hashlib, json, os
from pathlib import Path
import shutil, subprocess, sys, time

ROOT=Path(__file__).resolve().parents[1]

def command(args,log):
    with log.open('w') as output:
        result=subprocess.run(args,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,text=True)
    if result.returncode: raise RuntimeError(f'{args} failed; see {log}')

def read(path):
    try: return Path(path).read_text().strip()
    except OSError: return None

def metadata(cpu):
    cache=[]
    for p in sorted(Path(f'/sys/devices/system/cpu/cpu{cpu}/cache').glob('index*')):
        cache.append({k:read(p/k) for k in ['level','type','size','shared_cpu_list','coherency_line_size']})
    return dict(timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),cpu=cpu,
                allowed_affinity=sorted(os.sched_getaffinity(0)),cache=cache,
                sibling_list=read(f'/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list'),
                governor=read(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor'),
                frequency_sample_khz=read(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq'),
                scaling_min_khz=read(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_min_freq'),
                scaling_max_khz=read(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_max_freq'),
                smt_active=read('/sys/devices/system/cpu/smt/active'),
                isolated_cpus=read('/sys/devices/system/cpu/isolated'),
                perf_event_paranoid=read('/proc/sys/kernel/perf_event_paranoid'),
                lscpu=subprocess.check_output(['lscpu'],text=True),
                uname=subprocess.check_output(['uname','-a'],text=True),
                os_release=read('/etc/os-release'),
                limits='Affinity controlled; frequency, SMT sibling activity and OS isolation NOT controlled.')

def cases():
    result=[]
    for kernel in ['axpy','dot','multiply']:
        arrays=3 if kernel=='multiply' else 2
        for dtype,width in [('float',4),('double',8)]:
            for footprint in [12*1024,36*1024,64*1024,256*1024,1024*1024,2*1024**2,8*1024**2,16*1024**2,32*1024**2,64*1024**2,96*1024**2]:
                n=footprint//(arrays*width)//8*8
                result.append((kernel,dtype,'working_set',n,1,0))
            for tail in [0,1,3,7]:
                for offset in [0,1]: result.append((kernel,dtype,'alignment_tail',4096+tail,1,offset))
            for footprint in [256*1024,96*1024**2]:
                for stride in [1,2,4,8]:
                    n=footprint//(arrays*width*stride)//8*8
                    result.append((kernel,dtype,'stride',n,stride,0))
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu',type=int,default=min(os.sched_getaffinity(0)))
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    if args.cpu not in os.sched_getaffinity(0) or not 1<=args.repeats<=5: parser.error('invalid CPU/repeats')
    runid=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=args.out or ROOT/'output/evidence'/runid
    out=out.resolve();out.mkdir(parents=True,exist_ok=False)
    (out/'environment-before.json').write_text(json.dumps(metadata(args.cpu),indent=2)+'\n')
    sources=[*ROOT.glob('src/simd/*'),*ROOT.glob('experiments/*'),ROOT/'Makefile']
    hashes={};snapshot=out/'source_snapshot';snapshot.mkdir()
    for p in sources:
        if p.is_file():
            rel=p.relative_to(ROOT);hashes[str(rel)]=hashlib.sha256(p.read_bytes()).hexdigest()
            dest=snapshot/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    (out/'source-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
    sourceid=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
    allcases=cases()
    (out/'cases.txt').write_text('\n'.join(' '.join(map(str,c)) for c in allcases)+'\n')
    print(f'Run {runid}: {len(allcases)} configurations, {args.repeats} process repeats; output {out}',flush=True)
    builds={}
    for compiler,label in [('g++','gcc'),('clang++','clang')]:
        folder=out/f'build-{label}';command(['bash','experiments/build.sh',compiler,str(folder)],out/f'build-{label}.log')
        builds[label]=str(folder)
    # Permission probes are recorded; never modify perf policy.
    with (out/'perf-probes.txt').open('w') as log:
        for event in ['cycles:u,instructions:u','task-clock']:
            p=subprocess.run(['perf','stat','-e',event,'taskset','-c',str(args.cpu),'true'],capture_output=True,text=True)
            log.write(f'perf stat -e {event} taskset -c {args.cpu} true\nexit={p.returncode}\n{p.stdout}{p.stderr}\n')
    # A bounded Clang smoke matrix verifies its linked variants before GCC measurement.
    smoke=out/'clang-smoke';smoke.mkdir()
    (out/'smoke-cases.txt').write_text('axpy float alignment_tail 19 2 1\ndot double alignment_tail 19 4 1\nmultiply float alignment_tail 19 8 1\n')
    command([str(Path(builds['clang'])/'runner'),str(out/'smoke-cases.txt'),str(smoke),runid,'0',str(args.cpu)],smoke/'run.log')
    for repeat in range(args.repeats):
        folder=out/f'repeat-{repeat}';folder.mkdir()
        (folder/'environment-before.json').write_text(json.dumps(metadata(args.cpu),indent=2)+'\n')
        start=time.monotonic()
        command([str(Path(builds['gcc'])/'runner'),str(out/'cases.txt'),str(folder),runid,str(repeat),str(args.cpu)],folder/'run.log')
        (folder/'environment-after.json').write_text(json.dumps(metadata(args.cpu),indent=2)+'\n')
        print(f'Repeat {repeat} completed in {time.monotonic()-start:.1f}s',flush=True)
    (out/'environment-after.json').write_text(json.dumps(metadata(args.cpu),indent=2)+'\n')
    manifest=dict(run_id=runid,source_id=sourceid,compiler='g++',compiler_version=subprocess.check_output(['g++','--version'],text=True).splitlines()[0],
                  repeats=args.repeats,cases=len(allcases),expected_rows=len(allcases)*3*5*args.repeats,
                  plan='experiments/PLAN.md',builds=builds,cpu=args.cpu,
                  fp_policy='-ffast-math -ffp-contract=off in ALL numerical variants; strict harness; auto_strict evidence separate',
                  batch_policy='AXPY reset per batch; calls repeated updates; shared calls per case/repeat; 2 warmup batches',
                  clock='steady_clock elapsed_ns plus serialized invariant TSC reference ticks; NOT core cycles')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (ROOT/'output/evidence/LATEST').write_text(str(out)+'\n')
    print('COMPLETE',out,flush=True)
if __name__=='__main__': main()
