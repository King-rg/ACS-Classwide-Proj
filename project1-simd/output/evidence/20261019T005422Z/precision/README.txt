Float32 versus float64 local chart
Source: ../repeat-{0,1,2}/raw.csv (9,180 trials)
Reproduce: .venv-analysis/bin/python experiments/plot_precision.py output/evidence/20261019T005422Z
The plotting script requires a new precision output directory to prevent overwriting.

Nine panels: kernel rows and scalar/auto/SIMD columns. Both precision series share each panel's axes.
X: actual total footprint across active arrays, MiB, linear.
Y: median elapsed ns per call divided by processed element count, linear.
Each marker: median of three process medians, each from five trials.
Shading: observed range of process medians, not a confidence interval.
Matching uses the same nominal byte footprint, not equal N. Float32 processes about twice the elements. Rounding can change actual footprints by up to 96 bytes.
This is per-element cost at matched footprint, not equal-N precision speedup.
DVFS and SMT are not isolated. No new measurements were run.

Validation: all 612 points independently recomputed from raw trials; 18 SVG data curves each contain 34 markers. PNG is 5400 x 4050 at 300 dpi. PNG and PDF preview inspected locally.
All outputs are local; report untouched.
