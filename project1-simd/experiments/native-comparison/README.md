# AVX versus native

- Run commands from `project1-simd/`.
- Full campaign: `make all`; saved figures: `make reproduce`.
- [Project guide](../../README.md).

## Standalone study

```sh
python3 experiments/native-comparison/run.py
../.venv-analysis/bin/python experiments/native-comparison/analyze.py output/native-comparison/<timestamp>
```

- Two auto-vectorized builds: `-mavx` and `-march=native`; no scalar baseline.
- Shared flags: `-O3 -ffast-math -ffp-contract=off`; strict validation harness.
- CPU 0; alternating calls; aligned buffers; 15 trials and five warmups.
- Lengths: 32,768; 1,048,576; 8,388,608.
- Metric: matched AVX/native timing ratio; above 1 favors native.
- Recorded checks: 540 observations; 12 functions; 13 lengths; two offsets.
- Recorded assembly: 32-byte vectors; no FMA or ZMM instructions.
- Limits: IQRs are not confidence intervals; uncontrolled frequency/background work.
