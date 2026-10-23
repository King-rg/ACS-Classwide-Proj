# Hardware cycle study

Run `python3 experiments/cycles/run.py` from the repository root, then `.venv-analysis/bin/python experiments/cycles/analyze.py output/cycles/<timestamp>`.

Requires Linux per-process hardware counters accessible to the invoking user (the original system setting was perf_event_paranoid=4; temporarily 2 for this study). The script does not change permissions. It pins to CPU 0 and requires the pinned cycle event to be continuously scheduled. This is a separate five-length run of the main scalar/auto kernels, with 64-byte allocation alignment, no tails, 15 trials, five warmups, single-call timing, reference/input/guard validation, and matching compiler flags. No whole-process perf totals are used.

The cycle bracket excludes initialization, warmups, resets, and validation, but includes timer calls and dispatch plus user-mode counter-wrapper overhead. Kernel and hypervisor cycles are excluded. No frequency conversion or overhead subtraction is applied. Empty-bracket results are stored with the run (median 248 cycles for the first study); this overhead particularly affects small inputs. Frequency and background activity are uncontrolled. Summary values are medians with the middle 50% of trial measurements. K/M on plots are binary multiples. The five lengths span cache and DRAM sizes but are not a dense cache-transition sweep.
