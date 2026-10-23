# Advanced Computer Systems projects

All three reports are saved as `report.pdf` in each project's top-level directory. Each project README links its report, experiments, and saved evidence.

| Project | Guide | Report PDF |
|---|---|---|
| 1: SIMD | [README](project1-simd/README.md) | [Report (13 pages)](project1-simd/report.pdf) |
| 2: Cache and memory | [README](project2-cache-memory/README.md) | [Report (17 pages)](project2-cache-memory/report.pdf) |
| 3: SSD | [README](project3-ssd/README.md) | [Report (12 pages)](project3-ssd/report.pdf) |

## Setup

Use Linux and Python 3 with NumPy and Matplotlib. Project-specific compiler, counter, huge-page, and FIO requirements are listed in each guide. The existing `.venv-analysis` is retained; to recreate it from the workspace root:

```sh
python3 -m venv .venv-analysis
.venv-analysis/bin/python -m pip install -r project1-simd/requirements.txt
```

## Reproduction

Run projects sequentially, from the workspace root:

```sh
make -C project1-simd all
make -C project2-cache-memory all
make -C project3-ssd all
```

These commands collect fresh measurements for every figure in the reports: 9 SIMD, 11 cache/memory, and 9 SSD figures. Cache/memory includes the 30-trial hierarchy study; SSD includes all four follow-ups. These are long campaigns. Bare `make` means `make all`; `make benchmark` collects measurements without plotting. To reproduce the recorded report figures without benchmarking, run `make -C <project> reproduce`. This uses pinned local datasets. To regenerate a completed fresh campaign, use `make -C <project> plots RUN_DIR=/absolute/path/to/run`. `PYTHON=/path/to/python` overrides the default environment. Do not benchmark projects concurrently.

Only a completed full acquisition updates its `output/LATEST`; failed runs retain evidence and exit nonzero. Optional studies use separate markers and explicit `RUN_DIR` replays are labeled partial. A legacy `LATEST` without a full campaign manifest cannot claim full figure coverage; use `make reproduce` for the historical report. Saved runs retain raw and processed data, environment metadata, commands, and source snapshots. `figures/figure-<id>.png` and `.svg`, per-panel CSVs under `figures/plotted-values/`, and `coverage.json` identify the complete report figure set. Derived analysis remains under `analysis-inputs/`; original data is not modified. `shared/report-coverage.json` pins the inspected report revisions, captions, dataset paths, and hashes. Historical snapshots are not active source code.

## Review and validation

The assignment PDF is retained in this directory. Each project guide maps its experiments to the requirements and links hypothesis, correctness, AI-use, and failure-case evidence. Check these against the report before submission; do not treat historical claims as new validation. The PDFs were checked for successful rendering; this rendering check does not rerun the experiments or validate their conclusions.

```sh
.venv-analysis/bin/python -m unittest discover -s shared/tests -v
```

Shared orchestration and regression tests live in `shared/`. The repository includes the report PDFs, source code, and saved experiment evidence. Local environments, build artifacts, and duplicated reproduction outputs are excluded from version control.
