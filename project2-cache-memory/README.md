# Project 2: Cache and Memory Performance Profiling

A C11 benchmark measures cache/DRAM latency, bandwidth, concurrency, cache misses, and page locality.

## Prerequisites

Linux, GCC or Clang, Make, NumPy, Matplotlib, perf load sampling, CPU 0 affinity and the supported Intel P-core PMU for the hierarchy study, working hardware counters, and verified huge-page backing for huge-page cases. Acquisition fails when required evidence is unavailable; scripts do not change machine policy or restore binary capabilities after rebuilds.

## Report

The [report PDF](report.pdf) contains 17 pages.

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

## Experiments and evidence

| Requirement | Full campaign study |
|---|---|
| Per-level latency | Current-run 16 KiB, 512 KiB, 8 MiB, 192 MiB random-chain baselines and measured cycles. |
| Pattern/granularity and read/write mix | Sequential/random, spacing/transfer-size sweeps, eleven read percentages. |
| Intensity and Little's Law | Physical-core and chain-count sweeps; throughput versus latency. |
| Working set and cache misses | 32 sizes from 4 KiB to 192 MiB with simultaneous LLC counters. |
| TLB effects | Normal/verified huge pages with dTLB counters. |
| Misleading setup | Paired small/large-span cache-reuse comparison. |

The full suite includes all 11 report figures and the 30-paired-trial, 32-size hierarchy study. The main campaign uses three rounds of fifteen trials, targeting 250 ms per trial; allow substantially more than 47 minutes including setup on the recorded six-core configuration. The [saved full campaign](output/20261022T203612.685890Z/) contains raw data, summaries, metadata, plots, and tables.

See the [correctness checks](scripts/check.py) for validation logic and the [report PDF](report.pdf) for methodology, hypotheses, AI-use disclosure, and the cache-reuse pitfall.

Optional AMAT campaigns use `PROJECT2_SCOPE=amat-focused make all` (add `PROJECT2_AMAT_METHOD=mixed` for mixed residency) or `PROJECT2_SCOPE=amat-hierarchy make all`. Their saved runs use `LATEST_AMAT` or `LATEST_HIERARCHY`, separately from the full-suite `LATEST`. Experimental methodology belongs in the final report.

## Limitations

Pointer-chain latency approximates unloaded access cost. Useful bandwidth excludes write allocation and unused cache-line bytes. Throughput-derived block/chain times and software-active chains are not isolated device latency or controller occupancy. IQRs and bootstrap intervals have different meanings; AMAT parameters are effective benchmark costs, with quality flags retained.
