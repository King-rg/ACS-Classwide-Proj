# Advanced Computer Systems projects

| Project | Guide | Report |
|---|---|---|
| SIMD | [Setup and experiments](project1-simd/README.md) | [PDF](project1-simd/report.pdf) |
| Cache and memory | [Setup and experiments](project2-cache-memory/README.md) | [PDF](project2-cache-memory/report.pdf) |
| SSD | [Setup and experiments](project3-ssd/README.md) | [PDF](project3-ssd/report.pdf) |

## Setup

- Linux, Python 3, NumPy, Matplotlib.
- Hardware and compiler requirements: project guides.

```sh
python3 -m venv .venv-analysis
.venv-analysis/bin/python -m pip install -r project1-simd/requirements.txt
```

## Run

- Run benchmarks sequentially, from the workspace root.
- Replace `<project>` with a project directory.
- Override Python with `PYTHON=/path/to/python`.

| Command | Result |
|---|---|
| `make -C <project> all` | Build, validate, benchmark, and plot |
| `make -C <project> reproduce` | Replot pinned data without benchmarking |
| `make -C <project> benchmark` | Collect fresh measurements |
| `make -C <project> plots RUN_DIR=/absolute/path/to/run` | Replot a saved run |

## Evidence and checks

- Figures: 9 SIMD, 11 cache/memory, 9 SSD.
- [Dataset paths and hashes](shared/report-coverage.json).
- Run outputs: raw data, metadata, source snapshots, figures, and plotted-value CSVs.
- `output/LATEST`: updated only after complete acquisition.
- Historical source snapshots: reference only.
- PDF rendering checks do not validate experimental conclusions.

```sh
.venv-analysis/bin/python -m unittest discover -s shared/tests -v
```
