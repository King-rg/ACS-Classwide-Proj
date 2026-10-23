# Project 3 — SSD performance pilot

99 measurements, 33 configurations, 3 trials/configuration, 1 second(s) per timed trial. Medians and interquartile bands describe trial variability, not confidence intervals. FIO total latency includes submission and completion latency; mixed means are weighted by completed I/O count. Percentiles shown are medians of per-trial percentiles, not pooled request quantiles.

## Findings

The highest observed 4 KiB random-read rate was 393,518 IOPS. The first QD reaching 90% of that observed maximum was 32, at 81.6 µs mean latency. This is an operational near-saturation marker, not proof of the device’s absolute saturation knee. Extend the sweep if the endpoint is still improving.

At that QD, IOPS × mean total latency gives 31.9 average requests in the measured software path. Compare this with the raw FIO depth distribution; requested QD is a cap, not evidence of achieved controller occupancy.

The buffered/direct median throughput ratio for the repeatedly read 16 MiB file region was 11.10×. This comparison illustrates how cache policy changes the measured path. Direct I/O bypasses the OS page cache but does not bypass SSD controller caches.

## Scope and limitations

The SSD is the existing mounted system NVMe device. A newly created 1 GiB regular file was fully initialized before timing, and a 16 MiB CRC32C write/read check passed. All timed jobs reported error=0. Only the disposable file was written and it was removed after measurement. No raw-device writes, global cache drops, trims, or filesystem changes were used.

This is a short burst study on a previously used device, not a fresh or certified steady-state SSD test. Writes complete without per-I/O fsync, so write latency does not establish power-loss durability. The write time series has one run; no repeatability interval is claimed. Small file ranges do not establish physical LBA placement, whole-device behavior, or SLC-cache exhaustion. Background I/O, temperature, firmware, and CPU limits can affect results; correlations alone cannot identify throttling or garbage collection.

FIO runs one job pinned to the recorded CPU using libaio. Direct I/O and aligned block sizes are used except in the explicitly labeled buffered comparison. No CPU isolation or fixed frequency is claimed. Random refill data is intended to resist compression; device-level compressibility is not measured. Read/write block sweeps use read workloads; writes are measured separately in baseline, mix, and state tests.

## Figures

![01_baselines](/home/dandisk/ACS-Classwide-Proj/project3-ssd/output/20261021T235058Z/plots/01_baselines.png)

![02_block_size](/home/dandisk/ACS-Classwide-Proj/project3-ssd/output/20261021T235058Z/plots/02_block_size.png)

![03_read_write_mix](/home/dandisk/ACS-Classwide-Proj/project3-ssd/output/20261021T235058Z/plots/03_read_write_mix.png)

![04_queue_depth](/home/dandisk/ACS-Classwide-Proj/project3-ssd/output/20261021T235058Z/plots/04_queue_depth.png)

![05_tail_latency](/home/dandisk/ACS-Classwide-Proj/project3-ssd/output/20261021T235058Z/plots/05_tail_latency.png)

![06_range_device_state](/home/dandisk/ACS-Classwide-Proj/project3-ssd/output/20261021T235058Z/plots/06_range_device_state.png)

![07_page_cache_pitfall](/home/dandisk/ACS-Classwide-Proj/project3-ssd/output/20261021T235058Z/plots/07_page_cache_pitfall.png)

## Reproducibility and AI use

Configs and FIO JSON are retained per trial. raw.csv and summary.csv retain processed values, depth distributions, and percentile results. metadata.json records CPU, OS, storage, filesystem, governor, SMT, temperature sensors and commands. Codex generated acquisition, parsing, plotting and documentation; validation used FIO CRC32C and checked all job statuses and trial counts. The student should review and explain methodology before submission.

FIO option reference: https://fio.readthedocs.io/en/latest/fio_doc.html
