# Pattern and granularity follow-up

4230 validated fresh-process measurements: 3 rounds × 15 trials × 94 conditions. Each timed interval targets 250 ms. Every trial retains the pilot’s full warm traversal/pass. CPU 0. All samples retained.

Sequential and random orders are adjacent pairs, with alternating order and shuffled condition groups. Bands show the middle half of observations, not confidence intervals. Separate round medians expose run-to-run drift.

## Four-times spacing

| Transfer bytes | Sequential GiB/s | Random GiB/s | Median paired random/sequential | Paired IQR | Round medians |
|---:|---:|---:|---:|---:|---|
| 8 | 4.294 | 0.916 | 0.219× | 0.209–0.229× | 0.232×, 0.210×, 0.210× |
| 16 | 4.806 | 1.675 | 0.364× | 0.331–0.383× | 0.384×, 0.341×, 0.340× |
| 24 | 5.239 | 2.177 | 0.424× | 0.399–0.465× | 0.465×, 0.405×, 0.419× |
| 32 | 4.765 | 2.728 | 0.566× | 0.546–0.584× | 0.566×, 0.572×, 0.560× |
| 48 | 7.413 | 3.758 | 0.530× | 0.496–0.557× | 0.562×, 0.516×, 0.512× |
| 64 | 7.249 | 5.308 | 0.742× | 0.712–0.755× | 0.749×, 0.744×, 0.714× |
| 96 | 8.267 | 6.740 | 0.852× | 0.798–0.877× | 0.881×, 0.837×, 0.830× |
| 128 | 9.654 | 8.389 | 0.913× | 0.854–0.974× | 0.977×, 0.881×, 0.857× |
| 160 | 10.833 | 8.894 | 0.856× | 0.812–0.887× | 0.889×, 0.825×, 0.836× |
| 192 | 11.918 | 10.711 | 0.915× | 0.884–0.942× | 0.933×, 0.921×, 0.892× |
| 224 | 11.184 | 9.980 | 0.908× | 0.862–0.940× | 0.922×, 0.906×, 0.877× |
| 256 | 10.815 | 9.742 | 0.931× | 0.867–1.019× | 1.023×, 0.931×, 0.882× |
| 320 | 11.573 | 9.813 | 0.870× | 0.844–0.970× | 0.970×, 0.856×, 0.844× |
| 384 | 12.028 | 10.111 | 0.871× | 0.819–0.987× | 0.999×, 0.819×, 0.840× |
| 512 | 11.789 | 10.606 | 0.931× | 0.875–1.014× | 1.014×, 0.930×, 0.905× |
| 768 | 13.703 | 12.396 | 0.939× | 0.876–0.961× | 0.964×, 0.895×, 0.927× |
| 1024 | 12.886 | 12.296 | 0.978× | 0.928–0.990× | 0.983×, 0.938×, 0.982× |



![Pattern and granularity sweep](plots/02_pattern_granularity.png)

![Paired bandwidth comparison](plots/paired_bandwidth_ratio.png)

## Interpretation limits

The kernel and fixed mapped span are unchanged. Dense sweeps add measured intermediate sizes and remeasure the original sizes. Trial duration and acquisition schedule differ from the pilot, so differences between campaigns cannot isolate a hardware mechanism. At four-times spacing, useful payload is about 24 MiB within the 96 MiB mapped span. Cache-line traffic depends on block size and alignment, and can exceed that payload. The access-order array also occupies cache. Repeated passes can reuse cache contents. The 8-byte case uses 32-byte spacing and touches more cache-line bytes than its payload.

Hardware counters available on all measurements: False. No CPU-frequency or background-load controls were changed. Timing alone cannot identify prefetch or cache-set effects.

## Reproduction

`python3 scripts/repeat_pattern.py` then `../.venv-analysis/bin/python scripts/analyze_pattern_repeat.py`. Acquisition sources, commands, raw observations, summaries, and raw-data hash are retained in this run. The original pilot and its latest-run marker are unchanged.