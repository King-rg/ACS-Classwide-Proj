#include "dot_product.hpp"

namespace simd_project {

float dot_float_scalar(const float* x, const float* y, std::size_t n) {
    float sum = 0;
    for (std::size_t i = 0; i < n; ++i) {
        sum += x[i] * y[i];
    }
    return sum;
}

double dot_double_scalar(const double* x, const double* y, std::size_t n) {
    double sum = 0;
    for (std::size_t i = 0; i < n; ++i) {
        sum += x[i] * y[i];
    }
    return sum;
}

} // namespace simd_project
