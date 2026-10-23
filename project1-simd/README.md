# Project 1: SIMD

- [Report PDF](report.pdf) — 13 pages, 9 figures.
- Kernels: AXPY, dot product, elementwise multiply.
- Comparisons: scalar/auto-vectorized C11; float32/float64.

## Requirements

- Linux x86 with AVX/FMA; GCC, Make, `taskset`, `objdump`, `perf`.
- NumPy, Matplotlib, accessible hardware cycle counters.

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

| Study | Guide or evidence |
|---|---|
| Working set and datatype | [Saved campaign](output/20261022T213456.581536Z/) |
| Alignment and tails | [Guide](experiments/alignment-sweep/README.md) |
| Hardware cycles | [Guide](experiments/cycles/README.md) |
| AVX/native comparison | [Guide](experiments/native-comparison/README.md) |
| Stride, reduction, roofline | [Guide](experiments/supplemental-c/README.md) |
| Correctness | [Checks](tests/correctness.c) |

## Limits

- Relaxed reassociation in benchmarks; strict validation harness.
- Small timings include timer/dispatch overhead.
- Cache markers and modeled traffic are not hardware measurements.
- IQRs are not confidence intervals; frequency and background work vary.
