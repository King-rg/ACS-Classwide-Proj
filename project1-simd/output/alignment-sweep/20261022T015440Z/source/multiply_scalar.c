#include "kernels.h"


void multiply_float_scalar(const float* x, const float* y, float* z, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        z[i] = x[i] * y[i];
    }
}

void multiply_double_scalar(const double* x, const double* y, double* z, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        z[i] = x[i] * y[i];
    }
}
