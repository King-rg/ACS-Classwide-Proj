# Supplemental C experiments

Run from the project root:

```
python3 experiments/supplemental-c/run.py
../.venv-analysis/bin/python experiments/supplemental-c/analyze.py output/supplemental-c/RUN_TIMESTAMP
```

`PLAN.md` records hypotheses and the protocol before acquisition. All runs use
new timestamped directories. `raw.csv` contains every trial, `summary.csv` gives
medians/IQR, `findings.json` supplies report values, and `metadata.json` records
build/run commands, CPU affinity, governor, SMT, compiler, and a raw-data hash.
The run directory keeps source copies, objects, vectorization reports, and
assembly. The assignment programs remain separate and unchanged.

The alignment/tail and roofline cases call the same ordinary AXPY loops as the
main report. Only the stride study adds `restrict` and a runtime stride parameter;
GCC versions it into vector stride-1 and scalar non-unit-stride paths. Stride is
held unknown at compilation; these results do not describe separately specialized
constant-stride kernels or hardware gathers. SIMD is AVX, 256 bits; AVX2 gathers
and AVX-512 masking are not enabled. Tail cleanup is 128-bit and scalar code.

Short cases batch repeated updates and validate the total update. Their raw
latencies should not be directly equated with the main report's single-call
latencies. Values are deterministic binary fractions, initialized outside timing.
Alignment shifts both pointers by one element from separately 64-byte-aligned
allocations. The physical span stays fixed for stride tests, so useful element
count decreases with stride. Useful bandwidth counts two reads plus one write per
updated element; it is not measured DRAM-controller bandwidth.

The roofline uses a separate cached-store streaming triad to measure 17.12 GB/s
of useful traffic in the recorded run. Its approximate physical-traffic conversion
assumes output read-for-ownership plus writeback (16 instead of 12 bytes/element).
AXPY already reads its output and uses 12 bytes/float update in that model.
These are modeled traffic counts, not counters. Register-FMA calibration is a
separate C microbenchmark; FMA is disabled in the assignment kernel builds.
It supplies an empirical peak estimate at the observed, uncontrolled frequency,
not a guaranteed vendor maximum or a non-FMA kernel target.

Recorded run: `output/supplemental-c/20261021T232708Z`.
All 2,670 primary trials passed value/input/gap/guard checks. Independent shifted
4096-element confirmations contain 360 more trials. ASan/UBSan checked 28 small
cases. Performance counters were denied at perf_event_paranoid=4; core cycles per
element were later measured in the separate `experiments/cycles/` study. Cache misses were not measured. No permission, governor,
frequency, or SMT settings were changed. All samples retained, including anomalies.

Reproduce the extra instrumented checks and independent confirmations:

```
python3 experiments/supplemental-c/validate.py output/supplemental-c/20261021T232708Z
```

The confirmation replay writes a separate `_rerun.csv`, preserving the observations
quoted in the report. `source/` includes the final analyzer and validation script;
`manifest.sha256` records source and primary evidence hashes.

Generate the current report’s stride figure after analysis:

```sh
../.venv-analysis/bin/python experiments/supplemental-c/plot_stride_speedup.py output/supplemental-c/RUN_TIMESTAMP
```
