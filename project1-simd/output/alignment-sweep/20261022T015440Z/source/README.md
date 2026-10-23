# Direct alignment/tail working-set comparison

Run from the repository root:

```bash
python3 experiments/alignment-sweep/run.py
.venv-analysis/bin/python experiments/alignment-sweep/analyze.py
```

The run script calls the existing kernel executables with ordinary `--sizes` and
`--offset` controls. It deliberately retains the prior working-set single-call
protocol and random inputs instead of the batched, binary-fraction alignment mode.
Fifteen trials and five warmups are used for every condition. Each case is pinned;
case order is randomized. The four cases are clean, shifted one element, seven
added elements, and both. The clean length is divisible by eight. Historical data
from `output/auto-extended` is kept separate because it did not enforce clean
alignment or exact vector multiples.

Outputs include raw case CSVs, a combined CSV, summary, metadata, source snapshots,
a direct relative-cost plot and a speedup plot with the actual historical series.
Time per element normalizes the seven added elements. Cost bands show timing IQR
scaled by the clean median, not an uncertainty interval for the ratio. One tail
remainder is tested at each precision; this is not an exhaustive remainder sweep.
