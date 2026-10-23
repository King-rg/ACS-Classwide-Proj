# Alignment and tail sweep

For the current full campaign, use `make all` from `project1-simd/`; use `make plots RUN_DIR=/absolute/path/to/run` to replot it. See the [project guide](../../README.md).

## Standalone historical study

The commands and recorded results below describe the standalone study. Run these commands from `project1-simd/`; they are not required in addition to the current full campaign.

Run from `project1-simd/`:

```sh
python3 experiments/alignment-sweep/run.py
../.venv-analysis/bin/python experiments/alignment-sweep/analyze.py
../.venv-analysis/bin/python experiments/alignment-sweep/plot_simple.py
```

The run script builds the main auto-vectorized executables and uses their
`--sizes` and `--offset` options. It measures 12 base lengths with a clean,
64-byte-aligned baseline, a one-element shift, seven added elements, and both
changes. Each case uses 15 trials, five warmups, single-call timing, and the
original random inputs. Case order is shuffled and execution is pinned.

`analyze.py` writes per-kernel medians and speedups to `summary.csv`.
`plot_simple.py` produces the report's aligned-versus-shifted sweep and the
four-condition comparison at 32,768 elements. Speedups are combined using an
equal-weight geometric mean across kernels. Both scripts accept an optional
run directory and otherwise use `output/alignment-sweep/LATEST`.

Raw trials, metadata, and acquisition sources remain with each run. Historical
working-set runs are not mixed into the matched comparison. A seven-element
tail tests only one remainder per precision, not every possible remainder.
Tiny calls remain sensitive to timer overhead.

`python3 experiments/alignment-sweep/confirm.py` builds the required executables
and repeats selected cases for the latest run. It writes into that run's
`confirmation/` folder.
