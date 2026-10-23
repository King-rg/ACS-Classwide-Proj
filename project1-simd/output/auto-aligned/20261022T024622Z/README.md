Aligned, no-tail working-set rerun

Run: .venv-analysis/bin/python experiments/run_auto_comparison.py --extended --aligned
Plot: .venv-analysis/bin/python experiments/plot_auto_comparison.py --source-dir output/auto-aligned/20261022T024622Z

53 distinct rounded lengths; 15 trials, five warmups, single-call timing, CPU 0. All 9,540 observations validated. All array allocations are 64-byte aligned with zero offset; lengths are divisible by eight. Historical data were retained. No frequency isolation; timing bands are interquartile ranges, not confidence intervals. The alignment comparison in Figures 3–4 remains a separate paired run.
