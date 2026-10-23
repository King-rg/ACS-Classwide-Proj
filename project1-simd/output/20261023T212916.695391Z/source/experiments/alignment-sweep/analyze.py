"""Summarize the matched alignment/tail sweep for the report figures."""
from collections import defaultdict
from pathlib import Path
import csv
import sys
import numpy as np

root = Path(__file__).resolve().parents[2]
runs = root / 'output/alignment-sweep'
run = Path(sys.argv[1]) if len(sys.argv) > 1 else runs / (runs / 'LATEST').read_text().strip()
groups = defaultdict(list)
with (run / 'raw.csv').open() as source:
    for row in csv.DictReader(source):
        assert row['correct'] == 'pass'
        key = (row['kernel'], row['datatype'], int(row['base']), row['condition'], row['implementation'])
        groups[key].append(float(row['elapsed_ns']) / int(row['n']))
assert groups and all(len(values) == 15 for values in groups.values())
medians = {key: np.median(values) for key, values in groups.items()}
bases = sorted({key[2] for key in groups})
summary = []
for kernel in ['axpy', 'dot', 'multiply']:
    for datatype in ['float', 'double']:
        for base in bases:
            for condition in ['clean', 'shifted', 'tail', 'combined']:
                auto = medians[kernel, datatype, base, condition, 'auto']
                scalar = medians[kernel, datatype, base, condition, 'scalar']
                clean = medians[kernel, datatype, base, 'clean', 'auto']
                summary.append(dict(kernel=kernel, datatype=datatype, base=base,
                                    condition=condition, auto_ns_element=auto,
                                    scalar_ns_element=scalar, speedup=scalar / auto,
                                    auto_cost_ratio=auto / clean))
with (run / 'summary.csv').open('w') as target:
    writer = csv.DictWriter(target, fieldnames=summary[0])
    writer.writeheader()
    writer.writerows(summary)
print(f'Validated {sum(map(len, groups.values()))} measurements; wrote {len(summary)} summary rows.')
