#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <linux/perf_event.h>
#include <math.h>
#include <pthread.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

static void check(int condition, const char *message) {
    if (!condition) {
        perror(message);
        exit(2);
    }
}

static uint64_t clock_ns(void) {
    struct timespec timestamp;
    clock_gettime(CLOCK_MONOTONIC_RAW, &timestamp);
    return (uint64_t)timestamp.tv_sec * 1000000000ULL + timestamp.tv_nsec;
}

static uint64_t random_next(uint64_t *state) {
    *state ^= *state << 13;
    *state ^= *state >> 7;
    *state ^= *state << 17;
    return *state;
}

static void shuffle_indices(size_t *indices, size_t count, uint64_t *seed) {
    for (size_t i = count - 1; i > 0; --i) {
        size_t swap_index = random_next(seed) % (i + 1), saved = indices[i];
        indices[i] = indices[swap_index];
        indices[swap_index] = saved;
    }
}

static uint64_t *allocate_mapping(size_t span_bytes, int huge) {
    const size_t alignment = 2 * 1024 * 1024;
    size_t total = span_bytes + alignment;
    void *raw =
        mmap(NULL, total, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    check(raw != MAP_FAILED, "mmap");
    uintptr_t aligned = ((uintptr_t)raw + alignment - 1) & ~(alignment - 1);
    size_t prefix = aligned - (uintptr_t)raw;
    if (prefix) {
        check(munmap(raw, prefix) == 0, "unmap prefix");
    }
    size_t suffix = total - prefix - span_bytes;
    if (suffix) {
        check(munmap((void *)(aligned + span_bytes), suffix) == 0, "unmap suffix");
    }
    check(madvise((void *)aligned, span_bytes, huge ? MADV_HUGEPAGE : MADV_NOHUGEPAGE) ==
              0,
          "madvise");
    return (uint64_t *)aligned;
}

static size_t mapped_huge_bytes(void *address) {
    FILE *smaps = fopen("/proc/self/smaps", "r");
    check(smaps != NULL, "smaps");
    char line[512];
    unsigned long start, end;
    int mapping_matches = 0;
    size_t huge_kib = 0;
    while (fgets(line, sizeof line, smaps)) {
        if (sscanf(line, "%lx-%lx", &start, &end) == 2) {
            mapping_matches = (uintptr_t)address >= start && (uintptr_t)address < end;
        } else if (mapping_matches &&
                   sscanf(line, "AnonHugePages: %zu kB", &huge_kib) == 1) {
            fclose(smaps);
            return huge_kib * 1024;
        }
    }
    fclose(smaps);
    return 0;
}

struct Counters {
    int fd[4];
    int available;
    uint64_t values[4], enabled, running;
};

static void counters_open(struct Counters *counters) {
    memset(counters, 0, sizeof *counters);
    for (int i = 0; i < 4; ++i) {
        counters->fd[i] = -1;
    }
    const uint64_t config[] = {
        PERF_COUNT_HW_CPU_CYCLES, PERF_COUNT_HW_INSTRUCTIONS,
        PERF_COUNT_HW_CACHE_LL | (PERF_COUNT_HW_CACHE_OP_READ << 8) |
            (PERF_COUNT_HW_CACHE_RESULT_MISS << 16),
        PERF_COUNT_HW_CACHE_DTLB | (PERF_COUNT_HW_CACHE_OP_READ << 8) |
            (PERF_COUNT_HW_CACHE_RESULT_MISS << 16)};
    for (int i = 0; i < 4; ++i) {
        struct perf_event_attr attributes = {0};
        attributes.size = sizeof attributes;
        attributes.type = i < 2 ? PERF_TYPE_HARDWARE : PERF_TYPE_HW_CACHE;
        attributes.config = config[i];
        attributes.disabled = i == 0;
        attributes.exclude_kernel = 1;
        attributes.exclude_hv = 1;
        attributes.read_format = PERF_FORMAT_GROUP | PERF_FORMAT_TOTAL_TIME_ENABLED |
                                 PERF_FORMAT_TOTAL_TIME_RUNNING;
        counters->fd[i] =
            syscall(SYS_perf_event_open, &attributes, 0, -1, i ? counters->fd[0] : -1, 0);
        if (counters->fd[i] < 0) {
            for (int j = 0; j < i; ++j) {
                close(counters->fd[j]);
            }
            for (int j = 0; j < 4; ++j) {
                counters->fd[j] = -1;
            }
            return;
        }
    }
    counters->available = 1;
}

static void counters_start(struct Counters *counters) {
    if (counters->available) {
        check(ioctl(counters->fd[0], PERF_EVENT_IOC_RESET, PERF_IOC_FLAG_GROUP) == 0,
              "perf reset");
        check(ioctl(counters->fd[0], PERF_EVENT_IOC_ENABLE, PERF_IOC_FLAG_GROUP) == 0,
              "perf enable");
    }
}

static void counters_stop(struct Counters *counters) {
    if (counters->available) {
        check(ioctl(counters->fd[0], PERF_EVENT_IOC_DISABLE, PERF_IOC_FLAG_GROUP) == 0,
              "perf disable");
        struct {
            uint64_t count, enabled, running, values[4];
        } reading;
        check(read(counters->fd[0], &reading, sizeof reading) == sizeof reading,
              "perf read");
        // Reject multiplexed counters rather than reporting scaled estimates.
        if (reading.count != 4 || reading.enabled != reading.running ||
            reading.running == 0) {
            counters->available = 0;
        } else {
            memcpy(counters->values, reading.values, sizeof counters->values);
            counters->enabled = reading.enabled;
            counters->running = reading.running;
        }
    }
    for (int i = 0; i < 4; ++i) {
        if (counters->fd[i] >= 0) {
            close(counters->fd[i]);
        }
    }
}

struct BenchmarkJob {
    size_t span_bytes, spacing_bytes, block_bytes, streams;
    int cpu, huge, random, read_pct, bandwidth;
    int preparation; /* 0=warm, 1=L3-resident, 2=cache-flushed */
    size_t eviction_bytes;
    uint64_t duration_ns, seed;

    pthread_barrier_t *barrier;

    // Results written by this worker after its timed interval.
    double elapsed_ns;
    uint64_t operations, payload_bytes, checksum;
    size_t huge_page_bytes;
    struct Counters counters;
};

static uint64_t bandwidth_pass(uint64_t *data, const size_t *order, size_t block_count,
                               size_t block_bytes, int read_percent,
                               uint64_t write_value) {
    uint64_t checksum = 0;
    size_t words_per_block = block_bytes / 8;
    // The read/write ratio repeats over groups of ten transfer blocks.
    for (size_t k = 0; k < block_count; ++k) {
        uint64_t *block_data = data + order[k];
        if ((int)(k % 10) < read_percent / 10) {
            for (size_t j = 0; j < words_per_block; ++j) {
                checksum += block_data[j];
            }
        } else {
            for (size_t j = 0; j < words_per_block; ++j) {
                block_data[j] = write_value;
            }
        }
    }
    return checksum;
}

// Build disjoint rings, then traverse each once to validate and warm the data.
static void prepare_pointer_chains(const struct BenchmarkJob *job, uint64_t *data,
                                   const size_t *order, size_t *positions,
                                   size_t entries_per_chain) {
    for (size_t stream = 0; stream < job->streams; ++stream) {
        size_t chain_start = stream * entries_per_chain;
        positions[stream] = order[chain_start];
        for (size_t k = 0; k < entries_per_chain; ++k) {
            data[order[chain_start + k]] =
                order[chain_start + (k + 1) % entries_per_chain];
        }
    }
    unsigned char *seen = calloc(job->span_bytes / job->spacing_bytes, 1);
    check(seen != NULL, "seen allocation");
    for (size_t stream = 0; stream < job->streams; ++stream) {
        size_t position = positions[stream];
        for (size_t k = 0; k < entries_per_chain; ++k) {
            check(position < job->span_bytes / 8 &&
                      position % (job->spacing_bytes / 8) == 0,
                  "ring bound");
            size_t slot = position / (job->spacing_bytes / 8);
            check(!seen[slot], "duplicate ring entry");
            seen[slot] = 1;
            position = data[position];
        }
        check(position == positions[stream], "ring closure");
    }
    free(seen);
}

#include "prepared_access.h"

static void *worker(void *arg) {
    struct BenchmarkJob *job = arg;
    cpu_set_t cpu_set;
    CPU_ZERO(&cpu_set);
    CPU_SET(job->cpu, &cpu_set);
    check(pthread_setaffinity_np(pthread_self(), sizeof cpu_set, &cpu_set) == 0,
          "affinity");
    uint64_t *data = allocate_mapping(job->span_bytes, job->huge);
    for (size_t i = 0; i < job->span_bytes / 8; ++i) {
        data[i] = 1;
    }
    // Indices are offsets in uint64_t elements, not byte addresses.
    size_t entry_count = job->span_bytes / job->spacing_bytes;
    check(entry_count >= job->streams && job->streams <= 64, "chain count");
    size_t *order = malloc(entry_count * sizeof *order);
    check(order != NULL, "order allocation");
    for (size_t i = 0; i < entry_count; ++i) {
        order[i] = i * job->spacing_bytes / 8;
    }
    uint64_t seed = job->seed;
    if (job->random) {
        shuffle_indices(order, entry_count, &seed);
    }
    size_t positions[64] = {0};
    size_t entries_per_chain = entry_count / job->streams;
    entry_count = entries_per_chain * job->streams;
    if (!job->bandwidth) {
        prepare_pointer_chains(job, data, order, positions, entries_per_chain);
    } else {
        // Reads remain one; write blocks always contain a known constant.
        bandwidth_pass(data, order, entry_count, job->block_bytes, job->read_pct, 2);
    }
    job->huge_page_bytes = mapped_huge_bytes(data);
    counters_open(&job->counters);
    // Synchronize workers only after allocation, initialization, and warmup.
    pthread_barrier_wait(job->barrier);
    uint64_t start = clock_ns();
    counters_start(&job->counters);
    uint64_t now = start, operations = 0, checksum = 0, passes = 0;
    if (job->bandwidth) {
        do {
            checksum = bandwidth_pass(data, order, entry_count, job->block_bytes,
                                      job->read_pct, 2);
            ++passes;
            now = clock_ns();
        } while (now - start < job->duration_ns);
        operations = passes * entry_count;
    } else {
        do {
            for (int batch_step = 0; batch_step < 1024; ++batch_step) {
                for (size_t stream = 0; stream < job->streams; ++stream) {
                    positions[stream] = data[positions[stream]];
                }
            }
            operations += 1024 * job->streams;
            now = clock_ns();
        } while (now - start < job->duration_ns);
        for (size_t stream = 0; stream < job->streams; ++stream) {
            checksum += positions[stream];
        }
    }
    // Keep validation and cleanup outside the timed interval.
    counters_stop(&job->counters);
    job->elapsed_ns = now - start;
    job->operations = operations;
    job->payload_bytes =
        job->bandwidth ? passes * entry_count * job->block_bytes : operations * 64;
    job->checksum = checksum;
    if (job->bandwidth) {
        uint64_t expected = 0;
        for (size_t k = 0; k < entry_count; ++k) {
            int is_read_block = (int)(k % 10) < job->read_pct / 10;
            for (size_t w = 0; w < job->block_bytes / 8; ++w) {
                check(data[order[k] + w] == (uint64_t)(is_read_block ? 1 : 2),
                      "bandwidth output");
            }
            if (is_read_block) {
                expected += job->block_bytes / 8;
            }
        }
        check(checksum == expected, "read checksum");
    } else {
        for (size_t stream = 0; stream < job->streams; ++stream) {
            check(positions[stream] < job->span_bytes / 8, "final pointer");
        }
    }
    check(sched_getcpu() == job->cpu, "migration");
    free(order);
    check(munmap(data, job->span_bytes) == 0, "unmap");
    return NULL;
}

static struct BenchmarkJob parse_options(int argc, char **argv) {
    check(argc == 11 || argc == 12 || argc == 13,
          "usage: mode bytes spacing block read_pct random huge streams ms cpu_list [warm|l3-resident|cache-flushed [eviction_bytes]]");
    struct BenchmarkJob base = {0};
    base.bandwidth = !strcmp(argv[1], "bandwidth");
    check(base.bandwidth || !strcmp(argv[1], "latency"), "mode");
    base.span_bytes = strtoull(argv[2], 0, 10);
    base.spacing_bytes = strtoull(argv[3], 0, 10);
    base.block_bytes = strtoull(argv[4], 0, 10);
    base.read_pct = atoi(argv[5]);
    base.random = atoi(argv[6]);
    base.huge = atoi(argv[7]);
    base.streams = strtoull(argv[8], 0, 10);
    base.duration_ns = strtoull(argv[9], 0, 10) * 1000000ULL;
    base.seed = 4320;
    check(base.span_bytes >= 4096 && base.span_bytes <= 512ULL * 1024 * 1024 &&
              base.span_bytes % 4096 == 0,
          "bytes bound");
    check(base.spacing_bytes >= 8 && base.spacing_bytes % 8 == 0 &&
              base.block_bytes >= 8 && base.block_bytes <= base.spacing_bytes &&
              base.block_bytes % 8 == 0,
          "block/spacing");
    check(base.duration_ns >= 1000000 && base.duration_ns <= 1000000000, "duration");
    check(base.streams >= 1 && base.streams <= 64 && base.read_pct >= 0 &&
              base.read_pct <= 100 && base.read_pct % 10 == 0,
          "options");
    if(argc>=12) {
        check(!strcmp(argv[11],"warm") || !strcmp(argv[11],"l3-resident") ||
              !strcmp(argv[11],"cache-flushed"),"preparation");
        base.preparation=!strcmp(argv[11],"l3-resident")?1:!strcmp(argv[11],"cache-flushed")?2:0;
    }
    if(argc==13)base.eviction_bytes=strtoull(argv[12],0,10);
    if(base.preparation) {
        check(!base.bandwidth && base.random==1 && base.huge==0 && base.streams==1 &&
              base.span_bytes==8*1024*1024 && base.spacing_bytes==64 && base.block_bytes==8 &&
              base.read_pct==100,"prepared test configuration");
        check(base.preparation==1 ? (base.eviction_bytes==2*1024*1024 ||
              base.eviction_bytes==4*1024*1024 || base.eviction_bytes==8*1024*1024) :
              base.eviction_bytes==0,"eviction size");
    } else check(argc!=13,"warm test does not take eviction size");
    return base;
}

int main(int argc, char **argv) {
    struct BenchmarkJob base = parse_options(argc, argv);
    struct BenchmarkJob jobs[8];
    pthread_t threads[8];
    pthread_barrier_t barrier;
    int thread_count = 0;
    char *cpu_list = strdup(argv[10]), *token_state = NULL;
    for (char *cpu_token = strtok_r(cpu_list, ",", &token_state); cpu_token;
         cpu_token = strtok_r(NULL, ",", &token_state)) {
        check(thread_count < 8, "thread limit");
        jobs[thread_count] = base;
        jobs[thread_count].cpu = atoi(cpu_token);
        jobs[thread_count].barrier = &barrier;
        ++thread_count;
    }
    check(thread_count > 0, "CPU list");
    if(base.preparation) {
        check(thread_count==1,"prepared tests require one CPU");
        int result=prepared_benchmark(&jobs[0]);
        free(cpu_list);return result;
    }
    pthread_barrier_init(&barrier, NULL, thread_count);
    for (int i = 0; i < thread_count; ++i) {
        check(pthread_create(&threads[i], NULL, worker, &jobs[i]) == 0, "pthread_create");
    }
    double max_elapsed_ns = 0, total_elapsed_ns = 0;
    uint64_t operations = 0, payload_bytes = 0, huge_page_bytes = 0,
             counter_values[4] = {0};
    int counters_available = 1;
    for (int i = 0; i < thread_count; ++i) {
        pthread_join(threads[i], NULL);
        if (jobs[i].elapsed_ns > max_elapsed_ns) {
            max_elapsed_ns = jobs[i].elapsed_ns;
        }
        total_elapsed_ns += jobs[i].elapsed_ns;
        operations += jobs[i].operations;
        payload_bytes += jobs[i].payload_bytes;
        huge_page_bytes += jobs[i].huge_page_bytes;
        counters_available &= jobs[i].counters.available;
        for (int k = 0; k < 4; ++k) {
            counter_values[k] += jobs[i].counters.values[k];
        }
    }
    printf("{\"elapsed_ns\":%.0f,\"operations\":%" PRIu64 ",\"payload_bytes\":%" PRIu64
           ",\"ns_per_access\":%.9g,\"chain_latency_ns\":%.9g,\"million_accesses_s\":%."
           "9g,\"gib_s\":%.9g,\"threads\":%d,\"streams\":%zu,\"huge_bytes\":%" PRIu64
           ",\"counters_available\":%s,\"cycles\":%" PRIu64 ",\"instructions\":%" PRIu64
           ",\"llc_read_misses\":%" PRIu64 ",\"dtlb_read_misses\":%" PRIu64
           ",\"check\":\"pass\"}\n",
           max_elapsed_ns, operations, payload_bytes, total_elapsed_ns / operations,
           total_elapsed_ns / operations * base.streams,
           operations / max_elapsed_ns * 1000,
           payload_bytes / max_elapsed_ns * 1e9 / 1073741824, thread_count, base.streams,
           huge_page_bytes, counters_available ? "true" : "false", counter_values[0],
           counter_values[1], counter_values[2], counter_values[3]);
    pthread_barrier_destroy(&barrier);
    free(cpu_list);
    return 0;
}
