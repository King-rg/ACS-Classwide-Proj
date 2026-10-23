#ifndef KERNELS_H
#define KERNELS_H

#include <stddef.h>


// AXPY: x is read-only; y is initialized input/output; each has n elements.
// Used x/y ranges must not overlap. Only the first n elements of y may change.
// SAXPY uses float; DAXPY uses double. No special vector alignment is required.
// Implement n == 0 as a no-op and support arbitrary remainder lengths.
void saxpy_scalar(float a, const float* x, float* y, size_t n);
void saxpy_simd(float a, const float* x, float* y, size_t n);
void daxpy_scalar(double a, const double* x, double* y, size_t n);
void daxpy_simd(double a, const double* x, double* y, size_t n);

// Dot product: read n initialized elements from each input; modify neither.
// Read-only input ranges may overlap. Return the sum of matching products.
// Return zero for n == 0 without element access; support arbitrary lengths.
// Accumulate and return in the input type. SIMD uses lane-wise partial sums,
// then combines lanes; rounding can differ from scalar left-to-right addition.
// No special vector alignment is required.
float dot_float_scalar(const float* x, const float* y, size_t n);
float dot_float_simd(const float* x, const float* y, size_t n);
double dot_double_scalar(const double* x, const double* y, size_t n);
double dot_double_simd(const double* x, const double* y, size_t n);

// Multiply: read n initialized elements from x and y; write n outputs to z.
// z has space for n live elements; its old values need not be initialized.
// z's used range must not overlap either input; read-only inputs may overlap.
// Modify neither input. Implement n == 0 as a no-op; support arbitrary lengths.
// No special vector alignment is required.
void multiply_float_scalar(const float* x, const float* y, float* z, size_t n);
void multiply_float_simd(const float* x, const float* y, float* z, size_t n);
void multiply_double_scalar(const double* x, const double* y, double* z, size_t n);
void multiply_double_simd(const double* x, const double* y, double* z, size_t n);


#endif
