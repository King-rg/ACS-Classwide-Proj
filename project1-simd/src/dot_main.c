#include "benchmark.h"

/* float: allocate once, warm up, time each kernel, validate, then release. */
static void benchmark_float(size_t n, const Options *o, FILE *csv) {
    const size_t count = n + o->offset + 1;
    float *xb = allocate(count, sizeof *xb), *yb = allocate(count, sizeof *yb);
    float *x = xb + o->offset, *y = yb + o->offset;
    uint32_t seed = 4320;
    for (size_t i = 0; i < count; ++i) xb[i] = yb[i] = GUARD;
    for (size_t i = 0; i < n; ++i) {
        x[i] = (float)input_value(&seed, o);
        y[i] = (float)input_value(&seed, o);
    }
    long double expected = 0, sum_abs = 0;
    for (size_t i = 0; i < n; ++i) {
        long double product = (long double)x[i] * y[i];
        expected += product;
        sum_abs += fabsl(product);
    }
    const long double neps = (n + 1.0L) * FLT_EPSILON;
    // The exponential bound remains defined when n*epsilon reaches one.
    const long double gamma = neps < 1 ? neps / (1 - neps) : expm1l(neps);
    const long double tolerance = 2 * gamma * sum_abs + FLT_EPSILON;
    float result = 0;
    for (size_t trial = 0; trial < o->trials; ++trial) {
        for (int position = 0; position < 2; ++position) {
            const int simd = (trial + position) % 2;
            for (size_t warmup = 0; warmup < o->warmups; ++warmup) {
                result = simd ? dot_float_simd(x, y, n) : dot_float_scalar(x, y, n);
                check_close(result, expected, tolerance);
            }
            const uint64_t start = now_ns();
            for (size_t call=0; call<o->calls; ++call) {
                result = simd ? dot_float_simd(x, y, n) : dot_float_scalar(x, y, n);
            }
            const double elapsed = (double)(now_ns() - start);
            check_close(result, expected, tolerance);
            const long double checksum = result;
            /* Recreate the input sequence to check that read-only arrays stayed intact. */
            seed = 4320;
            for (size_t i = 0; i < n; ++i) {
                if (x[i] != (float)input_value(&seed, o)) fail("x modified");
                if (y[i] != (float)input_value(&seed, o)) fail("y modified");
            }
            if (xb[count-1] != GUARD || yb[count-1] != GUARD ||
                (o->offset && (xb[0] != GUARD || yb[0] != GUARD)))
                fail("Guard modified");
            write_row(csv, o, "dot", "float", simd, n, trial,
                      x, y, NULL, elapsed, checksum);
        }
    }
    free(xb); free(yb);
}

/* double: allocate once, warm up, time each kernel, validate, then release. */
static void benchmark_double(size_t n, const Options *o, FILE *csv) {
    const size_t count = n + o->offset + 1;
    double *xb = allocate(count, sizeof *xb), *yb = allocate(count, sizeof *yb);
    double *x = xb + o->offset, *y = yb + o->offset;
    uint32_t seed = 4320;
    for (size_t i = 0; i < count; ++i) xb[i] = yb[i] = GUARD;
    for (size_t i = 0; i < n; ++i) {
        x[i] = (double)input_value(&seed, o);
        y[i] = (double)input_value(&seed, o);
    }
    long double expected = 0, sum_abs = 0;
    for (size_t i = 0; i < n; ++i) {
        long double product = (long double)x[i] * y[i];
        expected += product;
        sum_abs += fabsl(product);
    }
    const long double neps = (n + 1.0L) * DBL_EPSILON;
    const long double gamma = neps < 1 ? neps / (1 - neps) : expm1l(neps);
    const long double tolerance = 2 * gamma * sum_abs + DBL_EPSILON;
    double result = 0;
    for (size_t trial = 0; trial < o->trials; ++trial) {
        for (int position = 0; position < 2; ++position) {
            const int simd = (trial + position) % 2;
            for (size_t warmup = 0; warmup < o->warmups; ++warmup) {
                result = simd ? dot_double_simd(x, y, n) : dot_double_scalar(x, y, n);
                check_close(result, expected, tolerance);
            }
            const uint64_t start = now_ns();
            for (size_t call=0; call<o->calls; ++call) {
                result = simd ? dot_double_simd(x, y, n) : dot_double_scalar(x, y, n);
            }
            const double elapsed = (double)(now_ns() - start);
            check_close(result, expected, tolerance);
            const long double checksum = result;
            /* Recreate the input sequence to check that read-only arrays stayed intact. */
            seed = 4320;
            for (size_t i = 0; i < n; ++i) {
                if (x[i] != (double)input_value(&seed, o)) fail("x modified");
                if (y[i] != (double)input_value(&seed, o)) fail("y modified");
            }
            if (xb[count-1] != GUARD || yb[count-1] != GUARD ||
                (o->offset && (xb[0] != GUARD || yb[0] != GUARD)))
                fail("Guard modified");
            write_row(csv, o, "dot", "double", simd, n, trial,
                      x, y, NULL, elapsed, checksum);
        }
    }
    free(xb); free(yb);
}

int main(int argc, char **argv) {
    Options options = parse_options(argc, argv, "output/dot_timings.csv");
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
