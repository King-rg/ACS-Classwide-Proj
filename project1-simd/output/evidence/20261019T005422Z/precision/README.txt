# Float32 versus float64

- Source: ../repeat-{0,1,2}/raw.csv; 9,180 trials.
- Nine panels: kernel rows, scalar/auto/SIMD columns.
- X: total active footprint (MiB); Y: ns per processed element.
- Markers: median of three process medians; five trials each.
- Shading: observed range, not confidence intervals.
- Matched footprint, not equal element count; rounding differs by up to 96 bytes.
- 612 checked points; 18 curves; 34 markers each.
- No new measurements; frequency and SMT uncontrolled.
- Requires a new precision output directory.
- Historical plotting command:

```sh
.venv-analysis/bin/python experiments/plot_precision.py output/evidence/20261019T005422Z
```
