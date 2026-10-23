#pragma once

#include <cstddef>

namespace simd_project {

// AXPY: x is read-only; y is initialized input/output; each has n elements.
// Used x/y ranges must not overlap. Only the first n elements of y may change.
// SAXPY uses float; DAXPY uses double. No special vector alignment is required.
// Implement n == 0 as a no-op and support arbitrary remainder lengths.
void saxpy_scalar(float a, const float* x, float* y, std::size_t n);
void saxpy_simd(float a, const float* x, float* y, std::size_t n);
void daxpy_scalar(double a, const double* x, double* y, std::size_t n);
void daxpy_simd(double a, const double* x, double* y, std::size_t n);

} // namespace simd_project
