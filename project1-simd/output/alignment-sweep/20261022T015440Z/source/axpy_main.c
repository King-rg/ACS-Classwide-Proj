#include "benchmark.h"

/* float: allocate once, warm up, time each kernel, validate, then release. */
static void benchmark_float(size_t n, const Options *o, FILE *csv) {
    const size_t count = n + o->offset + 1;
    float *xb = allocate(count, sizeof *xb), *yb = allocate(count, sizeof *yb);
    float *zb = allocate(count, sizeof *zb);
    float *x = xb + o->offset, *y = yb + o->offset, *z = zb + o->offset;
    uint32_t seed = 4320;
    for (size_t i = 0; i < count; ++i) xb[i] = yb[i] = zb[i] = GUARD;
    for (size_t i = 0; i < n; ++i) {
        x[i] = (float)input_value(&seed, o);
        y[i] = (float)input_value(&seed, o);
    }
    long double *expected = allocate(n, sizeof *expected);
    for (size_t i = 0; i < n; ++i) expected[i] = o->calls * 1.25L * x[i] + y[i];
    for (size_t trial = 0; trial < o->trials; ++trial) {
        for (int position = 0; position < 2; ++position) {
            const int simd = (trial + position) % 2;
            for (size_t warmup = 0; warmup < o->warmups; ++warmup) {
                memcpy(z, y, n * sizeof *z);
                if (simd) saxpy_simd(1.25, x, z, n); else saxpy_scalar(1.25, x, z, n);
            }
            memcpy(z, y, n * sizeof *z); /* Reset outside the timer. */
            const uint64_t start = now_ns();
            for (size_t call=0; call<o->calls; ++call) {
                if (simd) saxpy_simd(1.25, x, z, n); else saxpy_scalar(1.25, x, z, n);
            }
            const double elapsed = (double)(now_ns() - start);
            long double checksum = 0;
            for (size_t i = 0; i < n; ++i) {
                check_close(z[i], expected[i], 8 * FLT_EPSILON * fmaxl(1, fabsl(expected[i])));
                checksum += z[i];
            }
            /* Recreate the input sequence to check that read-only arrays stayed intact. */
            seed = 4320;
            for (size_t i = 0; i < n; ++i) {
                if (x[i] != (float)input_value(&seed, o)) fail("x modified");
                if (y[i] != (float)input_value(&seed, o)) fail("y modified");
            }
            if (xb[count-1] != GUARD || yb[count-1] != GUARD || zb[count-1] != GUARD ||
                (o->offset && (xb[0] != GUARD || yb[0] != GUARD || zb[0] != GUARD)))
                fail("Guard modified");
            write_row(csv, o, "axpy", "float", simd, n, trial,
                      x, z, z, elapsed, checksum);
        }
    }
    free(expected);
    free(xb); free(yb); free(zb);
}

/* double: allocate once, warm up, time each kernel, validate, then release. */
static void benchmark_double(size_t n, const Options *o, FILE *csv) {
    const size_t count = n + o->offset + 1;
    double *xb = allocate(count, sizeof *xb), *yb = allocate(count, sizeof *yb);
    double *zb = allocate(count, sizeof *zb);
    double *x = xb + o->offset, *y = yb + o->offset, *z = zb + o->offset;
    uint32_t seed = 4320;
    for (size_t i = 0; i < count; ++i) xb[i] = yb[i] = zb[i] = GUARD;
    for (size_t i = 0; i < n; ++i) {
        x[i] = (double)input_value(&seed, o);
        y[i] = (double)input_value(&seed, o);
    }
    long double *expected = allocate(n, sizeof *expected);
    for (size_t i = 0; i < n; ++i) expected[i] = o->calls * 1.25L * x[i] + y[i];
    for (size_t trial = 0; trial < o->trials; ++trial) {
        for (int position = 0; position < 2; ++position) {
            const int simd = (trial + position) % 2;
            for (size_t warmup = 0; warmup < o->warmups; ++warmup) {
                memcpy(z, y, n * sizeof *z);
                if (simd) daxpy_simd(1.25, x, z, n); else daxpy_scalar(1.25, x, z, n);
            }
            memcpy(z, y, n * sizeof *z); /* Reset outside the timer. */
            const uint64_t start = now_ns();
            for (size_t call=0; call<o->calls; ++call) {
                if (simd) daxpy_simd(1.25, x, z, n); else daxpy_scalar(1.25, x, z, n);
            }
            const double elapsed = (double)(now_ns() - start);
            long double checksum = 0;
            for (size_t i = 0; i < n; ++i) {
                check_close(z[i], expected[i], 8 * DBL_EPSILON * fmaxl(1, fabsl(expected[i])));
                checksum += z[i];
            }
            /* Recreate the input sequence to check that read-only arrays stayed intact. */
            seed = 4320;
            for (size_t i = 0; i < n; ++i) {
                if (x[i] != (double)input_value(&seed, o)) fail("x modified");
                if (y[i] != (double)input_value(&seed, o)) fail("y modified");
            }
            if (xb[count-1] != GUARD || yb[count-1] != GUARD || zb[count-1] != GUARD ||
                (o->offset && (xb[0] != GUARD || yb[0] != GUARD || zb[0] != GUARD)))
                fail("Guard modified");
            write_row(csv, o, "axpy", "double", simd, n, trial,
                      x, z, z, elapsed, checksum);
        }
    }
    free(expected);
    free(xb); free(yb); free(zb);
}

int main(int argc, char **argv) {
    Options options = parse_options(argc, argv, "output/axpy_timings.csv");
    if (options.help) { print_usage(argv[0]); return 0; }
    FILE *csv = open_csv(options.csv_path);
    for (size_t i = 0; i < options.size_count; ++i) {
        options.calls = options.alignment ? (options.sizes[i] < 40 ? 4096 : 256) : 1;
        for (size_t position=0; position<(options.alignment ? 2u : 1u); ++position) {
            if (options.alignment) options.offset=(i+position)%2;
            benchmark_float(options.sizes[i], &options, csv);
            benchmark_double(options.sizes[i], &options, csv);
        }
    }
    close_csv(csv, &options);
    return 0;
}
