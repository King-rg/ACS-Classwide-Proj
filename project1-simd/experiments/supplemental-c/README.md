# Supplemental C studies

- Run commands from `project1-simd/`.
- Full campaign: `make all`; saved figures: `make reproduce`.
- [Project guide](../../README.md).

## Standalone commands

```sh
python3 experiments/supplemental-c/run.py
../.venv-analysis/bin/python experiments/supplemental-c/analyze.py output/supplemental-c/RUN_TIMESTAMP
python3 experiments/supplemental-c/validate.py output/supplemental-c/20261021T232708Z
../.venv-analysis/bin/python experiments/supplemental-c/plot_stride_speedup.py output/supplemental-c/RUN_TIMESTAMP
```

## Method and outputs

- Studies: alignment/tails, runtime stride, strict/relaxed reduction, roofline.
- AVX 256-bit; no AVX2 gathers or AVX-512 masking.
- Short cases batch updates; not directly comparable to single-call latency.
- Fixed physical span for stride tests; useful element count falls with stride.
- Useful traffic: two reads and one write per update; not measured DRAM traffic.
- Roofline: separate streaming triad and register-FMA calibration.
- Outputs: `raw.csv`, `summary.csv`, `findings.json`, `metadata.json`, source snapshots.
- Confirmation replay: separate `_rerun.csv`; evidence hashes in `manifest.sha256`.

## Recorded validation

- Run: `output/supplemental-c/20261021T232708Z`.
- 2,670 primary trials; 360 independent confirmations; 28 sanitizer cases.
- Cycles measured separately in the hardware-cycle study; cache misses unavailable.
- No permission, governor, frequency, or SMT changes.
