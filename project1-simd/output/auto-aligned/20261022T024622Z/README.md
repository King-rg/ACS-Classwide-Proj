# Aligned working-set run

- 53 lengths; 15 trials; five warmups; CPU 0.
- 9,540 validated observations; 64-byte alignment; no tails.
- IQR bands; uncontrolled frequency; separate paired alignment study.
- Commands from `project1-simd/`:

```sh
../.venv-analysis/bin/python experiments/run_auto_comparison.py --extended --aligned
../.venv-analysis/bin/python experiments/plot_auto_comparison.py --source-dir output/auto-aligned/20261022T024622Z
```
