# Project 1 evidence status — 20261019T002553Z

The original output/timings.csv and output/analysis are unchanged. A prior
TSC-only run is marked incomplete; only this completed run's three process
repeats enter the new analysis. 7,290 rows, 162 cases, 3 variants, 5 trials,
3 processes. Per-process summaries: 1,458; matched speedup records: 972.

| Requirement | Actual evidence | Remaining limitation |
| --- | --- | --- |
| Scalar vs auto vs intrinsics | ordinary.cpp compiled twice, packed-vector reports/disassembly for all six GCC/Clang auto functions; full sweeps | Main sweeps explicitly permit FP reassociation; strict default compiler comparisons are supplemental. |
| L1/L2/LLC/DRAM-regime sweep | 12 KiB–96 MiB per kernel/type, 11 footprint points, CPU-0 48 KiB/1.25 MiB/24 MiB topology, LLC misses and real core cycles | Nominal capacities are not residency guarantees; demand misses are not memory-controller bytes. |
| Controlled alignment/tails | 64-byte allocations, offsets 0/1, N=4096+0/1/3/7 for all kernels/types/variants | Modest N, bounded matrix; finite-input accuracy only. |
| Strides 2/4/8 | alongside stride 1 at ~256 KiB/96 MiB physical footprints; explicit AVX2 gathers and scalar scatter; useful GB/s | Logical N decreases at fixed physical footprint; not a fixed-N sweep. |
| Saved compiler evidence | vectorization-evidence/ targeted per-function excerpts, full reports/objects/disassembly, strict-FP controls | Exact source/flags accompany evidence; no harness-only SIMD inference. |
| Bandwidth/roofline | independent NT triad: 24.322 logical GB/s; cached copy: 16.875 logical GB/s; separate measured FMA 146.908/73.220 GFLOP/s; theoretical 166.4/83.2 GFLOP/s upper estimate | Useful-byte rates and different store/read mixes are reference curves, not strict DRAM roofs; full controller traffic unavailable. |
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
supplements and all 7,290 main timing rows pass independent finite-data checks.
Five new parser/aggregation tests plus the existing analysis tests are required.
The dot validation also applies a finite-data acceptance cap for the very largest
float reductions; max_abs_error is recorded, not hidden behind relative tolerances.

## Reproduction

See README and experiments/PLAN.md. The completed run's source_snapshot captures
numerical build inputs before measurement. postprocessing_snapshot and its hashes
capture later analysis/supplement scripts. Source ID: 431c04832035081f26ff7e6f39e90177cd81da2fd77d4b3bbe016b9bb690ba3a.
No global settings were changed by the scripts; user-enabled perf permission is
recorded. Any rerun creates a new directory; existing analysis revisions remain.

## Additional platform probe

IMC aliases are exposed but user-only uncore read counting returns `<not supported>`;
an explicit unfiltered perf_event_open probe is denied under the current policy (EACCES). See
`uncore-probe.txt`. Consequently no physical DRAM-controller traffic claim is made.
The independent STREAM-style logical bandwidth measurements remain available.

All 7,290 raw rows are also concatenated without changing fields or repeat IDs in
`all_trials.csv`. Core cycles and elapsed time are total batch counts; normalize
by the explicit calls and N fields. All 1,458 summaries and 972 matched comparisons
were independently recomputed from the raw files; the historical raw SHA matches.
