# Denser local-chart measurements, prospective plan

The report is frozen: no Google Drive/report reads or writes are part of this task.
The numerical kernels and timer/counter/reset policies stay unchanged. This run
remeasures a complete, independent 34-size working-set sweep for all three kernels,
float/double, scalar/compiler-auto/explicit intrinsics, with three process repeats
and five validated trials per combination. It does not pool earlier data.

Expected rows: 34 sizes * 3 kernels * 2 types * 3 variants * 3 processes * 5 trials
= 9,180. Maximum active footprint remains 96 MiB. The shared-case pilot call count,
finite-input relaxed FP flags, CPU-0 affinity, real user-space core counters,
unaltered DVFS/SMT policy, two warmup batches and AXPY repeated-update policy are
identical to the preceding completed evidence run.

The sample grid is log-spaced overall, with extra actual measurements close to
48 KiB L1D, 1.25 MiB L2, and 24 MiB LLC capacity references. Hypothesis: additional
points may expose where speedup compresses; capacity marks alone do not prove
residency or establish a causal bottleneck. Do not smooth noise away or fabricate
samples. Lines will connect actual measured points, each with a visible marker.

Use process-matched scalar/variant median ratios, and summarize across processes.
Show the observed range of three process medians rather than a confidence interval.
Export six-panel (three kernels x two types) large 300-dpi PNGs plus SVG and PDF
vectors. Every plotted point must trace to its 15 validated raw observations;
speedup numerators/denominators must match all configuration fields and call counts
within each process. Save plotting values/validation and source metadata locally.
