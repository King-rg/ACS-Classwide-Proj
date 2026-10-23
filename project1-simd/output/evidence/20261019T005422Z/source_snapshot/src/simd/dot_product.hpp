#pragma once

#include <cstddef>

namespace simd_project {

// Dot product: read n initialized elements from each input; modify neither.
// Read-only input ranges may overlap. Return the sum of matching products.
// Return zero for n == 0 without element access; support arbitrary lengths.
// Accumulate and return in the input type. SIMD uses lane-wise partial sums,
// then combines lanes; rounding can differ from scalar left-to-right addition.
// No special vector alignment is required.
float dot_float_scalar(const float* x, const float* y, std::size_t n);
float dot_float_simd(const float* x, const float* y, std::size_t n);
double dot_double_scalar(const double* x, const double* y, std::size_t n);
double dot_double_simd(const double* x, const double* y, std::size_t n);

} // namespace simd_project
