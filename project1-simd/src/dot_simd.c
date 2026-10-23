#include "kernels.h"
#include <immintrin.h>


float dot_float_simd(const float* x, const float* y, size_t n) {
    enum { width = 8 };
    size_t i = 0;
    __m256 partial = _mm256_setzero_ps();
    // n - i avoids overflow in a prospective i + width bound.
    for (; n - i >= width; i += width) {
        const __m256 vx = _mm256_loadu_ps(x + i);
        const __m256 vy = _mm256_loadu_ps(y + i);
        partial = _mm256_add_ps(partial, _mm256_mul_ps(vx, vy));
    }
    _Alignas(32) float lanes[width];
    _mm256_store_ps(lanes, partial);
    float sum = 0;
    for (size_t lane = 0; lane < width; ++lane) {
        sum += lanes[lane];
    }
    for (; i < n; ++i) {
        sum += x[i] * y[i];
    }
    return sum;
}

double dot_double_simd(const double* x, const double* y, size_t n) {
    enum { width = 4 };
    size_t i = 0;
    __m256d partial = _mm256_setzero_pd();
    // n - i avoids overflow in a prospective i + width bound.
    for (; n - i >= width; i += width) {
        const __m256d vx = _mm256_loadu_pd(x + i);
        const __m256d vy = _mm256_loadu_pd(y + i);
        partial = _mm256_add_pd(partial, _mm256_mul_pd(vx, vy));
    }
    _Alignas(32) double lanes[width];
    _mm256_store_pd(lanes, partial);
    double sum = 0;
    for (size_t lane = 0; lane < width; ++lane) {
        sum += lanes[lane];
    }
    for (; i < n; ++i) {
        sum += x[i] * y[i];
    }
    return sum;
}
