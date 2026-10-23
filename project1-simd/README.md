# Project 1: SIMD Advantage Profiling

Three single-threaded C11 kernels compare scalar and auto-vectorized AXPY, dot product, and elementwise multiply for float32 and float64.

## Prerequisites

Linux x86 with AVX/FMA, GCC, Make, `taskset`, `objdump`, `perf`, NumPy, Matplotlib, and access to user-space hardware cycle counters. Missing required cycle counters stops acquisition; scripts do not change permissions or frequency policy.

## Report

The [report PDF](report.pdf) contains 13 pages.

## Reproduction

Run from this project directory:

| Command | Result |
|---|---|
| `make all` (or `make`) | Build, validate, acquire every report study, and generate plots/tables. |
| `make reproduce` | Recreate every recorded report figure from pinned historical datasets, without acquisition. |
| `make benchmark` | Build, validate, and acquire measurements only. |
| `make plots` | Render the latest completed full campaign without acquisition. |
| `make plots RUN_DIR=/absolute/path/to/run` | Render a selected full campaign, or an explicitly partial legacy study. |

`PYTHON=/path/to/python` overrides `../.venv-analysis/bin/python`. See the [workspace setup](../README.md). Run acquisitions sequentially. Failed acquisitions retain partial evidence without replacing the successful-run marker. Plotting failures can be retried using saved data. Every rendering writes a new output directory; `figures/` contains numbered PNG/SVG exports and per-panel plotted values, and `coverage.json` checks the complete figure list. Original historical inputs remain unchanged. A legacy `LATEST` is not a complete multi-study campaign; use `make reproduce` for the recorded report.

The full suite renders all nine report figures, including the bandwidth-limit comparison and all alignment/stride panels.

## Experiments and evidence

| Requirement | Campaign study / evidence |
|---|---|
| Scalar/SIMD, datatype, cache locality | `studies/working-set`: runtime, speedup, throughput, cache markers. |
| Alignment and tails | `studies/alignment`: aligned, shifted, tail-only, and combined cases. |
| Stride, reduction semantics, roofline | `studies/supplemental`: bandwidth, strict/relaxed dot, register-FMA calibration. |
| Compiler/ISA comparison | `studies/native`: AVX versus native auto-vectorization. |
| Cycles and vectorization verification | `studies/cycles`, compiler reports, and disassembly saved with the run. |

The [saved full campaign](output/20261022T213456.581536Z/) retains measurements, source snapshots, tables, and plots. [Correctness checks](tests/correctness.c) and retained validation results document checks. See the [report PDF](report.pdf) for hypotheses, the negative-case discussion, AI-use disclosure, and limitations.

Standalone experiment guides: [alignment](experiments/alignment-sweep/README.md), [cycles](experiments/cycles/README.md), [native](experiments/native-comparison/README.md), [supplemental](experiments/supplemental-c/README.md).

## Limitations

The main comparison uses relaxed reassociation; the validation harness is strict. Small single-call timings include timer/dispatch overhead. Cache-capacity markers do not prove residency. Roofline traffic is modeled, with empirical bandwidth and register-FMA peak. Trial IQRs are not confidence intervals; frequency and background activity can affect results.
