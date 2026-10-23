# Hardware cycles

- Run commands from `project1-simd/`.
- Full campaign: `make all`; saved figures: `make reproduce`.
- [Project guide](../../README.md).

## Standalone study

```sh
python3 experiments/cycles/run.py
../.venv-analysis/bin/python experiments/cycles/analyze.py output/cycles/<timestamp>
```

- Requires accessible, continuously scheduled hardware cycle counters; permissions unchanged.
- CPU 0; five lengths; 64-byte alignment; no tails; 15 trials and five warmups.
- Timing excludes initialization, warmups, resets, and validation.
- Timing includes timer, dispatch, and counter-wrapper overhead.
- User cycles only; no frequency conversion or overhead subtraction.
- First-study empty bracket: median 248 cycles.
- Summaries: medians/IQR; K/M labels use binary multiples.
- Limits: sparse cache coverage; uncontrolled frequency and background activity.
