#include "kernels.h"
#include <immintrin.h>


void saxpy_simd(float a, const float* x, float* y, size_t n) {
    enum { width = 8 };
    size_t i = 0;
    const __m256 coefficient = _mm256_set1_ps(a);
    // n - i avoids overflow in a prospective i + width bound.
    for (; n - i >= width; i += width) {
        const __m256 vx = _mm256_loadu_ps(x + i);
        const __m256 vy = _mm256_loadu_ps(y + i);
        _mm256_storeu_ps(y + i, _mm256_add_ps(_mm256_mul_ps(coefficient, vx), vy));
    }
    for (; i < n; ++i) {
        y[i] = a * x[i] + y[i];
    }
}

void daxpy_simd(double a, const double* x, double* y, size_t n) {
    enum { width = 4 };
    size_t i = 0;
    const __m256d coefficient = _mm256_set1_pd(a);
    // n - i avoids overflow in a prospective i + width bound.
    for (; n - i >= width; i += width) {
        const __m256d vx = _mm256_loadu_pd(x + i);
        const __m256d vy = _mm256_loadu_pd(y + i);
        _mm256_storeu_pd(y + i, _mm256_add_pd(_mm256_mul_pd(coefficient, vx), vy));
    }
    for (; i < n; ++i) {
        y[i] = a * x[i] + y[i];
    }
}
