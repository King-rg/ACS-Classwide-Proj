#!/usr/bin/env bash
# Run from any directory. Password entry stays in your terminal.
set -u
cd -- "$(dirname -- "$0")/.."
out="$(pwd)/output/frequency/$(date -u +%Y%m%dT%H%M%SZ)"
if [[ ! -x build/frequency/worker ]]; then
 echo 'Missing build/frequency/worker; rebuild with the commands in experiments/FREQUENCY_PLAN.md.' >&2
 exit 1
fi
sudo /usr/bin/python3 experiments/frequency_sweep.py --run --output "$out"
result=$?
if [[ -f "$out/restoration.json" ]]; then
 .venv-analysis/bin/python experiments/analyze_frequency.py "$out" || exit 1
fi
printf 'Output: %s\n' "$out"
exit "$result"
