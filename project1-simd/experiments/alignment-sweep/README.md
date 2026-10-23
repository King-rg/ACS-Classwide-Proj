# Alignment and tails

- Run commands from `project1-simd/`.
- Full campaign: `make all`; saved figures: `make reproduce`.
- [Project guide](../../README.md).

## Standalone study

```sh
python3 experiments/alignment-sweep/run.py
../.venv-analysis/bin/python experiments/alignment-sweep/analyze.py
../.venv-analysis/bin/python experiments/alignment-sweep/plot_simple.py
python3 experiments/alignment-sweep/confirm.py
```

- 12 lengths; aligned, shifted, seven-element tail, and combined cases.
- 15 trials, five warmups; shuffled order and pinned execution.
- Analysis defaults to `output/alignment-sweep/LATEST`; optional run-directory argument.
- Outputs: raw trials, metadata, `summary.csv`, plots, `confirmation/`.
- Cross-kernel speedups: equal-weight geometric mean.
- Limits: one tail remainder per precision; timer overhead at small sizes.
