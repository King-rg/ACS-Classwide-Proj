# Project 2 pilot results

255 validated observations across 85 configurations. 3 trials per configuration; median and interquartile range. This is a short pilot, not a claim of a stable hardware limit.

## Unloaded latency baseline

| Nominal regime | Span | Median ns/load |
|---|---:|---:|
| L1-sized | 16 KiB | 1.54 |
| L2-sized | 512 KiB | 4.10 |
| LLC-sized | 8192 KiB | 26.93 |
| DRAM-sized | 196608 KiB | 120.47 |



The labels refer to nominal cache capacities. Sequential prefetching, software overhead, page translation and other machine activity also affect observed latency. No core-cycle conversion is invented when counters are inaccessible.

## Required figures

### Zero-queue approximation: unloaded dependent-load baseline

![Zero-queue approximation: unloaded dependent-load baseline](/home/dandisk/ACS-Classwide-Proj/project2-cache-memory/output/20261021T234147Z/plots/01_zero_queue.png)



### Pattern and transfer-granularity sweep

![Pattern and transfer-granularity sweep](/home/dandisk/ACS-Classwide-Proj/project2-cache-memory/output/20261021T234147Z/plots/02_pattern_granularity.png)



### Read/write mix sweep

![Read/write mix sweep](/home/dandisk/ACS-Classwide-Proj/project2-cache-memory/output/20261021T234147Z/plots/03_read_write_mix.png)



### Intensity: throughput versus chain latency

![Intensity: throughput versus chain latency](/home/dandisk/ACS-Classwide-Proj/project2-cache-memory/output/20261021T234147Z/plots/04_intensity.png)



### Working-set sweep across cache capacities

![Working-set sweep across cache capacities](/home/dandisk/ACS-Classwide-Proj/project2-cache-memory/output/20261021T234147Z/plots/05_working_set.png)



### Cache-miss impact: timing plus counter availability

![Cache-miss impact: timing plus counter availability](/home/dandisk/ACS-Classwide-Proj/project2-cache-memory/output/20261021T234147Z/plots/06_cache_miss_impact.png)



### Page locality and verified huge pages

![Page locality and verified huge pages](/home/dandisk/ACS-Classwide-Proj/project2-cache-memory/output/20261021T234147Z/plots/07_tlb_pages.png)



### Pitfall: warm cache mistaken for DRAM bandwidth

![Pitfall: warm cache mistaken for DRAM bandwidth](/home/dandisk/ACS-Classwide-Proj/project2-cache-memory/output/20261021T234147Z/plots/08_cache_reuse_pitfall.png)



## Observations

The small reused buffer measured 155.00 GiB/s versus 18.21 GiB/s for the 192 MiB buffer, a 8.5× difference. The small-buffer result is cache bandwidth, not DRAM bandwidth.

Across 1 to 16 independent chains, throughput increased from 9.48 to 104.31 million loads/s, while mean chain round-trip time changed from 105.54 to 153.39 ns. The tested pilot range does not by itself establish a stable saturation knee.

## Interpretation and limits

Huge-page backing verified for all THP cases: **True**. Hardware counters available throughout: **False**.

The cache/TLB studies include measured timing, but a denied counter means the required miss correlation remains open. No missing counter is rendered as a zero.

Bandwidth counts useful payload, not actual DRAM bus traffic. Average block processing time in the mix study is not an individual memory-request latency.

For the intensity sweep, throughput × mean chain round-trip time estimates the number of software-active chains. This is a consistency check of the software concurrency, not an independent estimate of hardware MSHR occupancy. A short pilot may not exhibit a definitive saturation knee.

The page-locality sweep holds one data access per 4 KiB of mapped span; its touched cache-line footprint is smaller than its virtual span. THP can change translation locality without requiring a whole-span data working set.

## Reproduction

Run `make full`, then use the plotting command in the project README. Raw CSVs, processed tables, run metadata, source snapshots and SHA-256 are retained beside these figures.

## AI-use note

Codex assisted with this C harness, acquisition/plotting scripts and setup documentation. Pointer-ring uniqueness, bounds, data checksums, writes, and input rejection were exercised. Counter results and huge-page backing are checked rather than assumed.