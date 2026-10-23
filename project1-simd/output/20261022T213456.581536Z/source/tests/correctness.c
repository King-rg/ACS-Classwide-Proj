#include "benchmark.h"

static void test_float(size_t n, size_t offset, int guarded) {
    const size_t count = n + offset + guarded;
    float *xb = allocate(count, sizeof *xb), *yb = allocate(count, sizeof *yb);
    float *zb = allocate(count, sizeof *zb);
    float *original_x = allocate(count, sizeof *original_x);
    float *original_y = allocate(count, sizeof *original_y);
    float *x = xb + offset, *y = yb + offset, *z = zb + offset;
    uint32_t seed = 4320;
    for (size_t i = 0; i < count; ++i) xb[i] = yb[i] = zb[i] = GUARD;
    for (size_t i = 0; i < n; ++i) {
        x[i] = (float)random_value(&seed);
        y[i] = (float)random_value(&seed);
    }
    if (n == 3) {
        x[0] = 1; x[1] = -2; x[2] = 3;
        y[0] = 4; y[1] = 5; y[2] = -6;
    }
    memcpy(original_x, xb, count * sizeof *xb);
    memcpy(original_y, yb, count * sizeof *yb);
    long double dot = 0, sum_abs = 0;
    for (size_t i = 0; i < n; ++i) {
        const long double product = (long double)x[i] * y[i];
        dot += product;
        sum_abs += fabsl(product);
    }
    const long double neps = (n + 1.0L) * FLT_EPSILON;
    const long double tolerance = 2 * neps / (1 - neps) * sum_abs + FLT_EPSILON;
    for (int simd = 0; simd < 2; ++simd) {
        memcpy(z, y, n * sizeof *z);
        if (simd) saxpy_simd(1.25, x, z, n); else saxpy_scalar(1.25, x, z, n);
        for (size_t i = 0; i < n; ++i) {
            const long double expected = 1.25L * x[i] + y[i];
            check_close(z[i], expected, 8 * FLT_EPSILON * fmaxl(1, fabsl(expected)));
        }
        if (n == 3 && (z[0] != 5.25 || z[1] != 2.5 || z[2] != -2.25)) fail("Known AXPY failed");
        if ((guarded && z[n] != GUARD) || (offset && zb[0] != GUARD)) fail("AXPY guard modified");
        if (memcmp(xb, original_x, count * sizeof *xb) || memcmp(yb, original_y, count * sizeof *yb))
            fail("AXPY input modified");

        const float result = simd ? dot_float_simd(x, y, n) : dot_float_scalar(x, y, n);
        check_close(result, dot, tolerance);
        if (n == 3 && result != -24) fail("Known dot failed");
        if (memcmp(xb, original_x, count * sizeof *xb) || memcmp(yb, original_y, count * sizeof *yb))
            fail("Dot input modified");

        if (simd) multiply_float_simd(x, y, z, n); else multiply_float_scalar(x, y, z, n);
        for (size_t i = 0; i < n; ++i) {
            const long double expected = (long double)x[i] * y[i];
            check_close(z[i], expected, 8 * FLT_EPSILON * fmaxl(1, fabsl(expected)));
        }
        if (n == 3 && (z[0] != 4 || z[1] != -10 || z[2] != -18)) fail("Known multiply failed");
        if ((guarded && z[n] != GUARD) || (offset && zb[0] != GUARD)) fail("Multiply guard modified");
        if (memcmp(xb, original_x, count * sizeof *xb) || memcmp(yb, original_y, count * sizeof *yb))
            fail("Multiply input modified");
    }
    free(xb); free(yb); free(zb); free(original_x); free(original_y);
}

static void test_double(size_t n, size_t offset, int guarded) {
    const size_t count = n + offset + guarded;
    double *xb = allocate(count, sizeof *xb), *yb = allocate(count, sizeof *yb);
    double *zb = allocate(count, sizeof *zb);
    double *original_x = allocate(count, sizeof *original_x);
    double *original_y = allocate(count, sizeof *original_y);
    double *x = xb + offset, *y = yb + offset, *z = zb + offset;
    uint32_t seed = 4320;
    for (size_t i = 0; i < count; ++i) xb[i] = yb[i] = zb[i] = GUARD;
    for (size_t i = 0; i < n; ++i) {
        x[i] = (double)random_value(&seed);
        y[i] = (double)random_value(&seed);
    }
    if (n == 3) {
        x[0] = 1; x[1] = -2; x[2] = 3;
        y[0] = 4; y[1] = 5; y[2] = -6;
    }
    memcpy(original_x, xb, count * sizeof *xb);
    memcpy(original_y, yb, count * sizeof *yb);
    long double dot = 0, sum_abs = 0;
    for (size_t i = 0; i < n; ++i) {
        const long double product = (long double)x[i] * y[i];
        dot += product;
        sum_abs += fabsl(product);
    }
    const long double neps = (n + 1.0L) * DBL_EPSILON;
    const long double tolerance = 2 * neps / (1 - neps) * sum_abs + DBL_EPSILON;
    for (int simd = 0; simd < 2; ++simd) {
        memcpy(z, y, n * sizeof *z);
        if (simd) daxpy_simd(1.25, x, z, n); else daxpy_scalar(1.25, x, z, n);
        for (size_t i = 0; i < n; ++i) {
            const long double expected = 1.25L * x[i] + y[i];
            check_close(z[i], expected, 8 * DBL_EPSILON * fmaxl(1, fabsl(expected)));
        }
        if (n == 3 && (z[0] != 5.25 || z[1] != 2.5 || z[2] != -2.25)) fail("Known AXPY failed");
        if ((guarded && z[n] != GUARD) || (offset && zb[0] != GUARD)) fail("AXPY guard modified");
        if (memcmp(xb, original_x, count * sizeof *xb) || memcmp(yb, original_y, count * sizeof *yb))
            fail("AXPY input modified");

        const double result = simd ? dot_double_simd(x, y, n) : dot_double_scalar(x, y, n);
        check_close(result, dot, tolerance);
        if (n == 3 && result != -24) fail("Known dot failed");
        if (memcmp(xb, original_x, count * sizeof *xb) || memcmp(yb, original_y, count * sizeof *yb))
            fail("Dot input modified");

        if (simd) multiply_double_simd(x, y, z, n); else multiply_double_scalar(x, y, z, n);
        for (size_t i = 0; i < n; ++i) {
            const long double expected = (long double)x[i] * y[i];
            check_close(z[i], expected, 8 * DBL_EPSILON * fmaxl(1, fabsl(expected)));
        }
        if (n == 3 && (z[0] != 4 || z[1] != -10 || z[2] != -18)) fail("Known multiply failed");
        if ((guarded && z[n] != GUARD) || (offset && zb[0] != GUARD)) fail("Multiply guard modified");
        if (memcmp(xb, original_x, count * sizeof *xb) || memcmp(yb, original_y, count * sizeof *yb))
            fail("Multiply input modified");
    }
    free(xb); free(yb); free(zb); free(original_x); free(original_y);
}

int main(void) {
    const size_t lengths[] = {0, 1, 2, 3, 4, 7, 8, 9, 15, 16, 17, 19, 4099};
    for (size_t i = 0; i < sizeof lengths / sizeof lengths[0]; ++i) {
        for (size_t offset = 0; offset <= 1; ++offset) {
            for (int guarded = 0; guarded <= 1; ++guarded) {
                test_float(lengths[i], offset, guarded);
                test_double(lengths[i], offset, guarded);
            }
        }
    }
    puts("PASS: all 12 kernels; 13 lengths, two offsets, guarded and exact-size buffers");
    return 0;
}
