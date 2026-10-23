# Report figures

Each image is a standalone panel. CSV tables contain its plotted values.

## 01_baseline

Unloaded random pointer-chain baseline; nominal L1/L2/LLC/DRAM-sized spans.

![01_baseline](plots/01_baseline.png)

[Plotted data](tables/01_baseline.csv)

## 02_pattern_latency

02 pattern latency

![02_pattern_latency](plots/02_pattern_latency.png)

[Plotted data](tables/02_pattern_latency.csv)

## 03_granularity_bandwidth

Sequential/random transfers across a fixed 96 MiB span.

![03_granularity_bandwidth](plots/03_granularity_bandwidth.png)

[Plotted data](tables/03_granularity_bandwidth.csv)

## 04_mix_gib_s

96 MiB span; 1 KiB blocks. Block processing time is throughput-derived, not isolated load latency.

![04_mix_gib_s](plots/04_mix_gib_s.png)

[Plotted data](tables/04_mix_gib_s.csv)

## 04_mix_ns_per_access

96 MiB span; 1 KiB blocks. Block processing time is throughput-derived, not isolated load latency.

![04_mix_ns_per_access](plots/04_mix_ns_per_access.png)

[Plotted data](tables/04_mix_ns_per_access.csv)

## 05_intensity_streams_million_accesses_s

05 intensity streams million accesses s

![05_intensity_streams_million_accesses_s](plots/05_intensity_streams_million_accesses_s.png)

[Plotted data](tables/05_intensity_streams_million_accesses_s.csv)

## 05_intensity_streams_chain_latency_ns

05 intensity streams chain latency ns

![05_intensity_streams_chain_latency_ns](plots/05_intensity_streams_chain_latency_ns.png)

[Plotted data](tables/05_intensity_streams_chain_latency_ns.csv)

## 05_intensity_threads_million_accesses_s

05 intensity threads million accesses s

![05_intensity_threads_million_accesses_s](plots/05_intensity_threads_million_accesses_s.png)

[Plotted data](tables/05_intensity_threads_million_accesses_s.csv)

## 05_intensity_threads_chain_latency_ns

05 intensity threads chain latency ns

![05_intensity_threads_chain_latency_ns](plots/05_intensity_threads_chain_latency_ns.png)

[Plotted data](tables/05_intensity_threads_chain_latency_ns.csv)

## 06_throughput_latency

Concurrency sweep. Chain round-trip time includes interleaved software work; it is not isolated hardware latency.

![06_throughput_latency](plots/06_throughput_latency.png)

[Plotted data](tables/06_throughput_latency.csv)

## 07_working_set_ns_per_access

07 working set ns per access

![07_working_set_ns_per_access](plots/07_working_set_ns_per_access.png)

[Plotted data](tables/07_working_set_ns_per_access.csv)

## 07_working_set_million_accesses_s

07 working set million accesses s

![07_working_set_million_accesses_s](plots/07_working_set_million_accesses_s.png)

[Plotted data](tables/07_working_set_million_accesses_s.csv)

## 08_cache_ns_per_access

08 cache ns per access

![08_cache_ns_per_access](plots/08_cache_ns_per_access.png)

[Plotted data](tables/08_cache_ns_per_access.csv)

## 08_cache_llc_misses_per_1000

08 cache llc misses per 1000

![08_cache_llc_misses_per_1000](plots/08_cache_llc_misses_per_1000.png)

[Plotted data](tables/08_cache_llc_misses_per_1000.csv)

## 09_tlb_0_ns_per_access

Sequential page order; one access per 4 KiB.

![09_tlb_0_ns_per_access](plots/09_tlb_0_ns_per_access.png)

[Plotted data](tables/09_tlb_0_ns_per_access.csv)

## 09_tlb_0_dtlb_misses_per_1000

Sequential page order; one access per 4 KiB.

![09_tlb_0_dtlb_misses_per_1000](plots/09_tlb_0_dtlb_misses_per_1000.png)

[Plotted data](tables/09_tlb_0_dtlb_misses_per_1000.csv)

## 09_tlb_1_ns_per_access

Random page order; one access per 4 KiB.

![09_tlb_1_ns_per_access](plots/09_tlb_1_ns_per_access.png)

[Plotted data](tables/09_tlb_1_ns_per_access.csv)

## 09_tlb_1_dtlb_misses_per_1000

Random page order; one access per 4 KiB.

![09_tlb_1_dtlb_misses_per_1000](plots/09_tlb_1_dtlb_misses_per_1000.png)

[Plotted data](tables/09_tlb_1_dtlb_misses_per_1000.csv)

## 10_cache_reuse

Same sequential 1 KiB read kernel; the cache-sized buffer does not measure DRAM bandwidth.

![10_cache_reuse](plots/10_cache_reuse.png)

[Plotted data](tables/10_cache_reuse.csv)

## 11_paired_bandwidth_ratio

Ratios paired by trial; pooled median and IQR, with per-round medians slightly offset horizontally for readability.

![11_paired_bandwidth_ratio](plots/11_paired_bandwidth_ratio.png)

[Plotted data](tables/11_paired_bandwidth_ratio.csv)
