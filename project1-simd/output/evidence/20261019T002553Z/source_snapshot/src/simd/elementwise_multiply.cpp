#include "elementwise_multiply.hpp"

namespace simd_project {

void multiply_float_scalar(const float* x, const float* y, float* z, std::size_t n) {
    for (std::size_t i = 0; i < n; ++i) {
        z[i] = x[i] * y[i];
    }
}

void multiply_double_scalar(const double* x, const double* y, double* z, std::size_t n) {
    for (std::size_t i = 0; i < n; ++i) {
        z[i] = x[i] * y[i];
    }
}

} // namespace simd_project
