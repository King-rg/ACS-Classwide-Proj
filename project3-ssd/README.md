# Project 3: SSD

- [Report PDF](report.pdf) — 12 pages, 9 figures.
- FIO with temporary files and direct I/O; buffered reads only for the page-cache comparison.

## Requirements

- Linux, FIO with libaio, NumPy, Matplotlib.
- More than 24 GiB free; 1 GiB base/block/mix files and 16 GiB range/burst files.
- System FIO preferred; override with `FIO=/path/to/fio`.
- No hardware counters or huge pages required.

## Commands

- Run from this project directory; benchmark projects sequentially.
- [Workspace setup](../README.md); override Python with `PYTHON=/path/to/python`.

| Command | Result |
|---|---|
| `make all` | Build, validate, benchmark, and plot |
| `make reproduce` | Replot pinned report data |
| `make benchmark` | Collect measurements only |
| `make plots` | Plot the latest complete campaign |
| `make plots RUN_DIR=/absolute/path/to/run` | Plot a selected run |

- Outputs: `figures/`, plotted-value CSVs, and `coverage.json`.
- Failed runs retain partial evidence; `LATEST` stays on the previous complete acquisition.
- Legacy partial runs: use `make reproduce` for full report coverage.

## Studies and evidence

- [Base campaign](output/20261022T215132.687552Z/): five 10-second trials per configuration.
- [Dataset manifest](../shared/report-coverage.json); [validation code](../shared/project3.py).
- Baselines, block size, read/write mix, queue depth, tail latency, file range, write bursts, page cache.
- Full suite includes all four follow-up studies.
- Standalone replay commands below modify derived files in the selected run.
- Omitting `--plot` collects new measurements.

```sh
../.venv-analysis/bin/python scripts/block_repeat.py --plot output/block-repeat/20261023T193248.684097Z --first-trials 5
../.venv-analysis/bin/python scripts/mix_repeat.py --plot output/mix-repeat/20261023T195104.667231Z
../.venv-analysis/bin/python scripts/range_repeat.py --plot output/range-repeat/20261023T202133.572742Z
../.venv-analysis/bin/python scripts/burst_repeat.py --plot output/burst-repeat/20261023T203649.085439Z
```

## Limits and safeguards

- Raw disks and existing target files refused; only created test files removed.
- No cache dropping, trim, or machine-policy changes.
- Forced termination may leave a temporary file.
- Queue-depth knee does not prove saturation; file ranges are not physical LBAs.
- Tail values summarize trial percentiles, not pooled requests.
- Short bursts do not establish steady state or power-loss durability.
