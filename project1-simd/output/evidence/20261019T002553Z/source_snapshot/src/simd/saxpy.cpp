#include "saxpy.hpp"

namespace simd_project {

void saxpy_scalar(float a, const float* x, float* y, std::size_t n) {
    for (std::size_t i = 0; i < n; ++i) {
        y[i] = a * x[i] + y[i];
    }
}

void daxpy_scalar(double a, const double* x, double* y, std::size_t n) {
    for (std::size_t i = 0; i < n; ++i) {
        y[i] = a * x[i] + y[i];
    }
}

} // namespace simd_project
