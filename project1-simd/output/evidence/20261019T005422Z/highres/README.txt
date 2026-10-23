LOCAL DENSE WORKING-SET LINE CHARTS

No report or Google Drive document was read, edited, or opened for this task.
Earlier raw datasets, plotted figures, and the prior LATEST evidence pointer remain
unchanged. This is a complete NEW 34-footprint sweep; no historical runs are pooled.

Files:
  working_set_speedup_highres.png / .svg / .pdf
  working_set_runtime_highres.png / .svg / .pdf
  PNGs: 5400 x 4050 pixels at 300 dpi; SVG/PDF retain vector lines/text.
  Six panels per chart: AXPY, dot product, multiply x float32/float64.
  34 measured points per curve; runtime has 18 series / 612 markers;
  speedup has 12 measured series / 408 markers plus the 1x scalar reference.

Data:
  ../all_trials.csv: 9,180 actual new raw trials.
  ../repeat-{0,1,2}/raw.csv: original process-separated rows.
  per_repeat_summary.csv and per_repeat_speedups.csv: call-normalized per-process
  values. Every implementation/size has 3 process repeats x 5 validated trials.
  plotted_points.csv: all exact marker configurations and median/range values.
  validation.json, independent_validation.json, render_validation.json:
  provenance, independent raw-to-point checks and rendered SVG marker counts.

Meaning:
  Runtime is median of the 3 process median times per call (shown in microseconds).
  Speedup is median of 3 matched scalar/variant median ratios. Each within-process
  comparison matches call count, N, type, alignment, stride, seed and other settings.
  Shading is the observed range of the 3 process medians/ratios, NOT a confidence
  interval. Lines connect actual measured points without smoothing or fabricated
  observations. Close points near cache boundaries are intentional.
  X is TOTAL physical active footprint across the kernel's arrays (2 for AXPY/dot,
  3 for multiply), rounded down to vector-multiple element counts. It is not N or
  a single array's size. Dotted capacities are topology references, not proof of
  exact cache residency or causality. At a fixed footprint, types can have different N.

Method:
  Same numerical kernels/build flags as the earlier completed evidence run;
  CPU 0 pinned, AVX2, -O3 -ffast-math -ffp-contract=off; scalar vectorization disabled.
  Coefficient 1.25; actual 64-byte aligned arrays, offset 0, stride 1.
  Two warmup batches and common pilot-selected batch counts; AXPY resets before
  each batch and repeatedly updates y within the batch, just as before.
  Hardware user-space core cycles/instructions/LLC events and separate TSC ticks
  remain in raw CSV. Every measured row passed independent result/padding checks;
  CPU tags remain stable and counters show no multiplexing.
  Frequency and SMT sibling activity are not isolated. Variability remains visible.
  These new shapes must not be treated as a causal cache/bandwidth proof alone.

Reproduce from project root:
  .venv-analysis/bin/python experiments/run_evidence.py --cpu 0 --repeats 3 --sweep dense
  # Use the NEW path printed by that command, then:
  .venv-analysis/bin/python experiments/plot_dense.py <NEW_DIRECTORY>
  .venv-analysis/bin/python experiments/validate_dense.py <NEW_DIRECTORY>
  .venv-analysis/bin/python -m unittest discover -s experiments -p 'test_*.py' -v

The chart script refuses an existing highres directory to preserve plot revisions;
rename/move that directory before rerendering the same data. Numerical build inputs
are captured in source_snapshot; final plotting scripts are in
plotting_source_snapshot with SHA-256 hashes.

LINEAR RUNTIME COMPANION
Both axes are linear with zero baselines: footprint in MiB, runtime in milliseconds.
Same 612 measured markers/18 series/34 sizes and uncertainty; no new experiments.
Original logarithmic outputs are unchanged (SHA-256 checked).
Render with: .venv-analysis/bin/python experiments/plot_dense.py <DIRECTORY> --linear-runtime
Outputs: working_set_runtime_highres_linear.{png,svg,pdf}, runtime_linear_preview.png.
Small footprints naturally cluster near zero on this scale.
