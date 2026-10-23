#include "elementwise_multiply.hpp"
#include <immintrin.h>

namespace simd_project {

void multiply_float_simd(const float* x, const float* y, float* z, std::size_t n) {
    constexpr std::size_t width = 8;
    std::size_t i = 0;
    // n - i avoids overflow in a prospective i + width bound.
    for (; n - i >= width; i += width) {
        const __m256 vx = _mm256_loadu_ps(x + i);
        const __m256 vy = _mm256_loadu_ps(y + i);
        _mm256_storeu_ps(z + i, _mm256_mul_ps(vx, vy));
    }
    for (; i < n; ++i) {
        z[i] = x[i] * y[i];
    }
}

void multiply_double_simd(const double* x, const double* y, double* z, std::size_t n) {
    constexpr std::size_t width = 4;
    std::size_t i = 0;
    // n - i avoids overflow in a prospective i + width bound.
    for (; n - i >= width; i += width) {
        const __m256d vx = _mm256_loadu_pd(x + i);
        const __m256d vy = _mm256_loadu_pd(y + i);
        _mm256_storeu_pd(z + i, _mm256_mul_pd(vx, vy));
    }
    for (; i < n; ++i) {
        z[i] = x[i] * y[i];
    }
}

} // namespace simd_project
