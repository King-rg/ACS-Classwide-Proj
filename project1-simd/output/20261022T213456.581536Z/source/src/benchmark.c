#include "benchmark.h"
#include <errno.h>
#include <limits.h>
#include <sys/stat.h>
#include <time.h>

#ifndef SIMD_BUILD_MODE
#define SIMD_BUILD_MODE "unknown"
#endif

void fail(const char *message) {
    fprintf(stderr, "FAIL: %s\n", message);
    exit(EXIT_FAILURE);
}

static size_t integer_option(const char *text, size_t minimum, size_t maximum) {
    if (!*text || strspn(text, "0123456789") != strlen(text))
        fail("Expected an unsigned integer");
    errno = 0;
    unsigned long long value = strtoull(text, NULL, 10);
    if (errno || value < minimum || value > maximum) fail("Option out of range");
    return (size_t)value;
}

Options parse_options(int argc, char **argv, const char *default_csv) {
    Options o = {.csv_path=default_csv, .trials=7, .warmups=2,
                 .sizes={19,4099,262147,1048579}, .size_count=4, .calls=1};
    int custom_sizes=0, custom_offset=0;
    for (int i = 1; i < argc; ++i) {
        const char *arg = argv[i];
        if (!strcmp(arg, "--help")) { o.help = 1; continue; }
        if (i + 1 == argc) fail("Missing option value");
        const char *value = argv[++i];
        if (!strcmp(arg, "--csv")) o.csv_path = value;
        else if (!strcmp(arg, "--trials")) o.trials = integer_option(value, 1, 10000);
        else if (!strcmp(arg, "--warmups")) o.warmups = integer_option(value, 0, 10000);
        else if (!strcmp(arg, "--study")) {
            if (strcmp(value, "alignment")) fail("Study must be alignment");
            o.alignment=1;
        }
        else if (!strcmp(arg, "--offset")) { o.offset = integer_option(value, 0, 1); custom_offset=1; }
        else if (!strcmp(arg, "--sizes")) {
            custom_sizes=1;
            o.size_count = 0;
            do {
                size_t length = strcspn(value, ",");
                char number[32];
                if (length >= sizeof number || o.size_count == 64) fail("Invalid size list");
                memcpy(number, value, length);
                number[length] = '\0';
                o.sizes[o.size_count++] = integer_option(number, 1, 33554432);
                value += length;
                if (!*value) break;
                ++value;
            } while (1);
        } else fail("Unknown option");
    }
    if (o.alignment) {
        if (custom_sizes || custom_offset) fail("Alignment study controls sizes and offsets");
        o.size_count=16;
        for (size_t i=0;i<8;++i) { o.sizes[i]=32+i; o.sizes[i+8]=4096+i; }
    }
    return o;
}

void print_usage(const char *program) {
    printf("Usage: %s [--csv PATH] [--sizes N,N,...] [--trials N]\n"
           "       [--warmups N] [--offset 0|1] [--study alignment]\n"
           "Defaults: sizes 19,4099,262147,1048579; 7 trials; 2 warmups; offset 0.\n", program);
}

void *allocate(size_t count, size_t element_size) {
    if (!element_size || count > SIZE_MAX / element_size) fail("Allocation size overflow");
    void *p;
    if (posix_memalign(&p, 64, (count ? count : 1) * element_size)) fail("Allocation failed");
    return p;
}

uint64_t now_ns(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) fail("Clock read failed");
    return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}

double random_value(uint32_t *state) {
    /* Fixed xorshift32 sequence, independent of the platform's rand(). */
    *state ^= *state << 13;
    *state ^= *state >> 17;
    *state ^= *state << 5;
    return ((int)(*state % 2049) - 1024) / 1000.0;
}

/* Binary fractions keep repeated AXPY updates exact in the alignment study. */
double input_value(uint32_t *state, const Options *o) {
    double value=random_value(state);
    return o->alignment ? (double)(*state % 17)/16.0 : value;
}

void check_close(long double actual, long double expected, long double tolerance) {
    if (!isfinite(actual) || !isfinite(expected) || fabsl(actual - expected) > tolerance)
        fail("Numerical mismatch");
}

FILE *open_csv(const char *path) {
    if (!*path) fail("Empty CSV path");
    /* Create parent directories for both default and custom output paths. */
    char *parent = allocate(strlen(path) + 1, 1);
    strcpy(parent, path);
    for (char *p = parent + 1; *p; ++p) {
        if (*p != '/') continue;
        *p = '\0';
        if (mkdir(parent, 0777) && errno != EEXIST) fail("Cannot create CSV directory");
        *p = '/';
    }
    free(parent);
    FILE *csv = fopen(path, "w");
    if (!csv) fail("Cannot open CSV");
    fputs("kernel,implementation,datatype,n,stride,offset_elements,x_mod32,y_mod32,output_mod32,"
          "coefficient,trial,warmups,calls,elapsed_ns,checksum,correct,seed,build_mode,compiler,study,ns_per_call\n", csv);
    return csv;
}

static void csv_quote(FILE *csv, const char *text) {
    fputc('"', csv);
    for (; *text; ++text) {
        if (*text == '"') fputc('"', csv);
        fputc(*text, csv);
    }
    fputc('"', csv);
}

void write_row(FILE *csv, const Options *o, const char *kernel,
               const char *type, int simd, size_t n, size_t trial,
               const void *x, const void *y, const void *output,
               double elapsed, long double checksum) {
    if (!isfinite(elapsed) || elapsed <= 0 || !isfinite(checksum)) fail("Invalid timing/checksum");
#ifdef BENCH_AUTO
    const char *implementation = simd ? "auto" : "scalar";
#else
    const char *implementation = simd ? "simd" : "scalar";
#endif
    fprintf(csv, "%s,%s,%s,%zu,1,%zu,%zu,%zu,", kernel, implementation,
            type, n, o->offset, (size_t)((uintptr_t)x % 32), (size_t)((uintptr_t)y % 32));
    if (output) fprintf(csv, "%zu", (size_t)((uintptr_t)output % 32));
    fprintf(csv, ",%s,%zu,%zu,%zu,%.17g,%.21Lg,pass,4320,",
            !strcmp(kernel, "axpy") ? "1.25" : "", trial, o->warmups, o->calls, elapsed, checksum);
    csv_quote(csv, SIMD_BUILD_MODE);
    fputc(',', csv);
    csv_quote(csv, __VERSION__);
    fprintf(csv, ",%s,%.17g\n", o->alignment ? "alignment" : "working_set", elapsed/o->calls);
    if (ferror(csv)) fail("CSV write failed");
}

void close_csv(FILE *csv, const Options *o) {
    if (fclose(csv)) fail("CSV close failed");
    printf("Wrote %zu rows to %s\n", o->size_count * o->trials * 4 * (o->alignment ? 2 : 1), o->csv_path);
}
