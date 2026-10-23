# Project 2: Cache and memory

- [Report PDF](report.pdf) — 17 pages, 11 figures.
- Studies: latency, bandwidth, concurrency, cache misses, page locality.

## Requirements

- Linux; GCC or Clang; Make; NumPy; Matplotlib.
- CPU 0 affinity, hardware counters, perf load sampling.
- Hierarchy study: supported Intel P-core PMU.
- Huge-page cases: verified huge-page backing.
- Acquisition stops when required hardware evidence is unavailable.

## Commands

- Run from this project directory; benchmark projects sequentially.
- [Workspace setup](../README.md); override Python with `PYTHON=/path/to/python`.

| Command | Result |
|---|---|
| `make all` | Build, validate, benchmark, and plot |
| `make reproduce` | Replot pinned report data |
| `make benchmark` | Collect measurements only |
| `make plots` | Plot the latest complete campaign |
| `make plots RUN_DIR=/absolute/path/to/run` | Plot a selected run |

- Outputs: `figures/`, plotted-value CSVs, and `coverage.json`.
- Failed runs retain partial evidence; `LATEST` stays on the previous complete acquisition.
- Legacy partial runs: use `make reproduce` for full report coverage.

## Studies and evidence

- [Saved campaign](output/20261022T203612.685890Z/); [correctness checks](scripts/check.py).
- Baselines: 16 KiB, 512 KiB, 8 MiB, 192 MiB random chains.
- Pattern, transfer size, read/write mix, core count, chain count.
- Hierarchy: 30 paired trials across 32 sizes.
- TLB and cache-reuse comparisons.
- Full acquisition: substantially longer than 47 minutes on the recorded system.

## Optional AMAT runs

| Command | Scope |
|---|---|
| `PROJECT2_SCOPE=amat-focused make all` | Focused AMAT |
| `PROJECT2_SCOPE=amat-focused PROJECT2_AMAT_METHOD=mixed make all` | Mixed residency |
| `PROJECT2_SCOPE=amat-hierarchy make all` | Hierarchy study |

- Separate markers: `LATEST_AMAT`, `LATEST_HIERARCHY`.

## Limits

- Pointer-chain latency approximates unloaded access cost.
- Useful bandwidth excludes write allocation and unused cache-line bytes.
- Software-active chains do not measure controller occupancy.
- AMAT parameters are effective benchmark costs.
