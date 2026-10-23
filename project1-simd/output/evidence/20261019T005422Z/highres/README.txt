# Dense working-set charts

- Source: ../all_trials.csv; 9,180 trials; 34 footprints.
- Panels: AXPY/dot/multiply by float32/float64.
- Runtime: 18 curves, 612 markers; speedup: 12 curves, 408 markers.
- Median of three process medians/ratios; five trials per process.
- Shading: observed range, not confidence intervals.
- X-axis: total active-array footprint; cache markers do not prove residency.
- CPU 0; AVX2; aligned buffers; two warmups; batched timing.
- Frequency and SMT activity uncontrolled.
- Evidence: plotted_points.csv and validation JSON files.
- Formats: PNG (5400 x 4050), SVG, PDF; optional linear-runtime companion.
- Rerendering requires a new highres directory.
- Commands use historical script locations:

```sh
.venv-analysis/bin/python experiments/run_evidence.py --cpu 0 --repeats 3 --sweep dense
.venv-analysis/bin/python experiments/plot_dense.py <NEW_DIRECTORY>
.venv-analysis/bin/python experiments/validate_dense.py <NEW_DIRECTORY>
.venv-analysis/bin/python experiments/plot_dense.py <DIRECTORY> --linear-runtime
```
