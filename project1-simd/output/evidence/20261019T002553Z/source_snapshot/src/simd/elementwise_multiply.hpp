#pragma once

#include <cstddef>

namespace simd_project {

// Multiply: read n initialized elements from x and y; write n outputs to z.
// z has space for n live elements; its old values need not be initialized.
// z's used range must not overlap either input; read-only inputs may overlap.
// Modify neither input. Implement n == 0 as a no-op; support arbitrary lengths.
// No special vector alignment is required.
void multiply_float_scalar(const float* x, const float* y, float* z, std::size_t n);
void multiply_float_simd(const float* x, const float* y, float* z, std::size_t n);
void multiply_double_scalar(const double* x, const double* y, double* z, std::size_t n);
void multiply_double_simd(const double* x, const double* y, double* z, std::size_t n);

} // namespace simd_project
