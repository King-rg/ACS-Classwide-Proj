#!/usr/bin/env python3
"""Derive report-ready tables and a gap ledger from completed evidence."""
import csv,json,statistics,sys
from pathlib import Path
import analyze_evidence as analysis

root=Path(sys.argv[1]);out=root/'analysis'
s=list(csv.DictReader((out/'per_repeat_summary.csv').open()));ratios=list(csv.DictReader((out/'per_repeat_speedups.csv').open()))
cal=list(csv.DictReader((out/'calibration_summary.csv').open()))
def summarize(values):
 return dict(median=statistics.median(values),low=min(values),high=max(values))
def format_range(values):
 r=summarize(values);return f"{r['median']:.3f} [{r['low']:.3f}–{r['high']:.3f}]"
large=[];compression=[];facts=[]
for kernel in ['axpy','dot','multiply']:
 for dtype in ['float','double']:
  big=[r for r in s if r['kernel']==kernel and r['datatype']==dtype and r['study']=='working_set' and int(r['footprint_bytes'])>95*1024**2]
  small=[r for r in s if r['kernel']==kernel and r['datatype']==dtype and r['study']=='working_set' and int(r['footprint_bytes'])<13*1024]
  def speed(rows,impl):
   repeat={}
   for r in rows:repeat.setdefault(r['repeat'],{})[r['implementation']]=float(r['median_ns'])
   return [x['scalar']/x[impl] for x in repeat.values()]
  a=speed(big,'auto');v=speed(big,'simd');a0=speed(small,'auto')
  bigauto=[r for r in big if r['implementation']=='auto'];smallauto=[r for r in small if r['implementation']=='auto']
  cpe=[float(r['median_core_cycles_per_element']) for r in bigauto]
  misses=[float(r['median_llc_misses_per_1000_elements']) for r in bigauto]
  large.append([kernel+' / '+dtype,format_range(a),format_range(v),f'{statistics.median(cpe):.3f}',f'{statistics.median(misses):.2f}'])
  compression.append([kernel+' / '+dtype,format_range(a0),format_range(a),f"{statistics.median(float(r['median_core_cycles_per_element']) for r in smallauto):.3f}",f'{statistics.median(cpe):.3f}'])
  facts.append(dict(kernel=kernel,datatype=dtype,n=int(bigauto[0]['n']),auto_speedup=summarize(a),simd_speedup=summarize(v),
                    small_auto_speedup=summarize(a0),large_auto_cpe=statistics.median(cpe),large_auto_llc_per1000=statistics.median(misses)))
strict={}
for label in ['strict-gcc','strict-clang','relaxed-clang']:
 with (root/label/'raw.csv').open() as f:rows=list(csv.DictReader(f))
 summary=analysis.summaries(rows);comparison=analysis.compare(summary)
 analysis.write_csv(root/label/'summary.csv',summary);analysis.write_csv(root/label/'speedups.csv',comparison)
 strict[label]={r['datatype']:float(r['speedup']) for r in comparison if r['kernel']=='dot' and r['implementation']=='auto'}
# Preserve post-run analysis/supplement sources too, distinct from the pre-run snapshot.
import hashlib,shutil
post=root/'postprocessing_snapshot';post.mkdir(exist_ok=True)
for source in Path('experiments').glob('*'):
 if source.is_file():shutil.copy2(source,post/source.name)
(root/'postprocessing-hashes.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in post.iterdir() if p.is_file()},indent=2)+'\n')
metadata=json.load((root/'manifest.json').open())
cal_rates={r['kind']:float(r['median_rate']) for r in cal}
result=dict(run_id=metadata['run_id'],source_id=metadata['source_id'],large_table=[['Kernel/type','Auto speedup × [range]','Intrinsics speedup × [range]','Auto core cycles/element','Auto LLC misses/1000']]+large,
            compression_table=[['Kernel/type','12 KiB auto × [range]','96 MiB auto × [range]','12 KiB auto cycles/el','96 MiB auto cycles/el']]+compression,
            facts=facts,calibration=cal,strict_dot_auto_speedups=strict)
(out/'report_values.json').write_text(json.dumps(result,indent=2)+'\n')
status=f'''# Project 1 evidence status — {metadata['run_id']}

The original output/timings.csv and output/analysis are unchanged. A prior
TSC-only run is marked incomplete; only this completed run's three process
repeats enter the new analysis. {metadata['expected_rows']:,} rows, {metadata['cases']} cases, 3 variants, 5 trials,
{metadata['repeats']} processes. Per-process summaries: {len(s):,}; matched speedup records: {len(ratios):,}.

| Requirement | Actual evidence | Remaining limitation |
| --- | --- | --- |
| Scalar vs auto vs intrinsics | ordinary.cpp compiled twice, packed-vector reports/disassembly for all six GCC/Clang auto functions; full sweeps | Main sweeps explicitly permit FP reassociation; strict default compiler comparisons are supplemental. |
| L1/L2/LLC/DRAM-regime sweep | 12 KiB–96 MiB per kernel/type, 11 footprint points, CPU-0 48 KiB/1.25 MiB/24 MiB topology, LLC misses and real core cycles | Nominal capacities are not residency guarantees; demand misses are not memory-controller bytes. |
| Controlled alignment/tails | 64-byte allocations, offsets 0/1, N=4096+0/1/3/7 for all kernels/types/variants | Modest N, bounded matrix; finite-input accuracy only. |
| Strides 2/4/8 | alongside stride 1 at ~256 KiB/96 MiB physical footprints; explicit AVX2 gathers and scalar scatter; useful GB/s | Logical N decreases at fixed physical footprint; not a fixed-N sweep. |
| Saved compiler evidence | vectorization-evidence/ targeted per-function excerpts, full reports/objects/disassembly, strict-FP controls | Exact source/flags accompany evidence; no harness-only SIMD inference. |
| Bandwidth/roofline | independent NT triad: {cal_rates['nt_triad']:.3f} logical GB/s; cached copy: {cal_rates['cached_copy']:.3f} logical GB/s; separate measured FMA {cal_rates['fma_f32']:.3f}/{cal_rates['fma_f64']:.3f} GFLOP/s; theoretical 166.4/83.2 GFLOP/s upper estimate | Useful-byte rates and different store/read mixes are reference curves, not strict DRAM roofs; full controller traffic unavailable. |
| Core cycles/element | grouped P-core userspace cycles/instructions/LLC-misses per timed batch; enabled==running, no migration | Counts include the small batch/clock wrapper; exclude kernel/hypervisor. TSC ticks recorded separately. |
| Run controls/repeats | CPU 0 affinity, 3 processes, 5 trials, source hashes/build logs, per-process metadata/frequency samples, explicit batch reset policy | powersave/DVFS and active SMT sibling NOT disabled or isolated; no fixed-frequency claim. |
| Verified negative case | Clang strict float/double dot loops reject FP reordering and contain no packed arithmetic; relaxed builds vectorize; strict-vs-relaxed actual measurements saved | Compiler/FP-semantics negative case, not a fabricated memory-bound slowdown. |

## Interpretation

Large working-set core-cycle costs and LLC misses increase while many SIMD gains
compress. These measurements support a streaming/memory-traffic explanation but
frequency/scheduling and read/write differences remain alternatives. Do not label
any single slowdown as proved bandwidth saturation. In particular, the original
uncontrolled double-AXPY slowdown is not reused as the verified failure case.

Report-ready values: analysis/report_values.json. Actual environment/counter
mapping: manifest.json, pmu-events.json, environment*.json, repeat-*/environment*.json.
TSC CPUID and calibration: repeat-*/tsc.json. Raw calls and total elapsed/cycle
counts remain inspectable; per-call and per-element values are derived explicitly.

## Validation

Original twelve kernels were not modified. GCC and Clang new-variant checks cover
480 size/stride/offset/variant configurations over float/double plus hand fixtures;
all three kernels are checked in each. Clang ASan/UBSan passes. Strict GCC/Clang
supplements and all {metadata['expected_rows']:,} main timing rows pass independent finite-data checks.
Five new parser/aggregation tests plus the existing analysis tests are required.
The dot validation also applies a finite-data acceptance cap for the very largest
float reductions; max_abs_error is recorded, not hidden behind relative tolerances.

## Reproduction

See README and experiments/PLAN.md. The completed run's source_snapshot captures
numerical build inputs before measurement. postprocessing_snapshot and its hashes
capture later analysis/supplement scripts. Source ID: {metadata['source_id']}.
No global settings were changed by the scripts; user-enabled perf permission is
recorded. Any rerun creates a new directory; existing analysis revisions remain.
'''
(root/'EVIDENCE_STATUS.md').write_text(status)
print(json.dumps(result,indent=2))
