# Project 3: SSD Performance Profiling

FIO measures a newly created disposable regular file, using aligned direct I/O except for the labeled page-cache comparison.

## Prerequisites

Linux, FIO with libaio, NumPy, Matplotlib, and more than 24 GiB free for the complete suite. The base and block/mix studies use 1 GiB disposable files; range and burst use 16 GiB files, sequentially. A valid system FIO is preferred, then the retained `tools/local` installation; `FIO=/path/to/fio` overrides discovery. Hardware performance counters and huge pages are not required.

## Report

The [report PDF](report.pdf) contains 12 pages.

## Reproduction

Run from this project directory:

| Command | Result |
|---|---|
| `make all` (or `make`) | Build, validate, acquire every report study, and generate plots/tables. |
| `make reproduce` | Recreate every recorded report figure from pinned historical datasets, without acquisition. |
| `make benchmark` | Build, validate, and acquire measurements only. |
| `make plots` | Render the latest completed full campaign without acquisition. |
| `make plots RUN_DIR=/absolute/path/to/run` | Render a selected full campaign, or an explicitly partial legacy study. |

`PYTHON=/path/to/python` overrides `../.venv-analysis/bin/python`. See the [workspace setup](../README.md). Run acquisitions sequentially. Failed acquisitions retain partial evidence without replacing the successful-run marker. Plotting failures can be retried using saved data. Every rendering writes a new output directory; `figures/` contains numbered PNG/SVG exports and per-panel plotted values, and `coverage.json` checks the complete figure list. Original historical inputs remain unchanged. A legacy `LATEST` is not a complete multi-study campaign; use `make reproduce` for the recorded report.

## Experiments and evidence

| Requirement | Base campaign output |
|---|---|
| QD=1 baselines | 4 KiB random and 128 KiB sequential read/write, mean/p95/p99. |
| Block size and read/write mix | Throughput and latency from matched runs. |
| Queue depth and Little's Law | Throughput/latency curve, achieved-depth evidence, operational knee. |
| Tail latency | p50/p95/p99/p99.9 at QD 8 and near-knee QD. |
| Range and device state | File-range sweep and bounded write burst. |
| Misleading setup | Buffered/direct repeated-read page-cache comparison. |

The [base campaign](output/20261022T215132.687552Z/) uses five ten-second trials per configuration, with initialization and CRC32C validation outside timing. The [figure coverage manifest](../shared/report-coverage.json) identifies the saved datasets. See the [validation implementation](../shared/project3.py) and [report PDF](report.pdf) for hypotheses, correctness, AI-use disclosure, and limitations.

Replot the report's saved follow-ups from this project directory:

```sh
../.venv-analysis/bin/python scripts/block_repeat.py --plot output/block-repeat/20261023T193248.684097Z --first-trials 5
../.venv-analysis/bin/python scripts/mix_repeat.py --plot output/mix-repeat/20261023T195104.667231Z
../.venv-analysis/bin/python scripts/range_repeat.py --plot output/range-repeat/20261023T202133.572742Z
../.venv-analysis/bin/python scripts/burst_repeat.py --plot output/burst-repeat/20261023T203649.085439Z
```

The complete `make all` command now acquires these four follow-ups automatically and renders all nine report figures. The standalone commands above remain available; they write derived files in their selected run. Prefer `make reproduce` for isolated, read-only reproduction of historical inputs. Omitting `--plot` acquires a fresh follow-up. The block report uses the first five paired trials; all acquired trials remain retained. Range uses eight rounds over eleven spans; burst averages five 60-second writes after 30-second idle intervals. Idle time does not reset SSD state.

## Limitations and safety

The runner refuses raw disks and existing target files, and removes only its own disposable file. No cache dropping, trim, or system-policy changes are performed. An uncatchable termination may leave the disposable file for manual removal.

Requested QD is a cap; the first depth reaching 90% of observed peak IOPS is an operational knee, not proof of saturation. Tail summaries are medians of trial percentiles, not pooled quantiles. File-offset range is not physical LBA placement. Bursts do not establish steady state or SLC exhaustion, and writes do not imply power-loss durability without per-I/O fsync.
