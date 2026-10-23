#pragma once
#include <cstddef>
namespace evidence {
#define DECLARE_VARIANT(V, T, SUFFIX) \
void axpy_##V##_##SUFFIX(T a, const T* x, T* y, std::size_t n, std::size_t stride); \
T dot_##V##_##SUFFIX(const T* x, const T* y, std::size_t n, std::size_t stride); \
void multiply_##V##_##SUFFIX(const T* x, const T* y, T* z, std::size_t n, std::size_t stride);
#define DECLARE_TYPE(T, SUFFIX) \
DECLARE_VARIANT(scalar,T,SUFFIX) DECLARE_VARIANT(auto,T,SUFFIX) DECLARE_VARIANT(simd,T,SUFFIX)
DECLARE_TYPE(float, f32)
DECLARE_TYPE(double, f64)
#undef DECLARE_TYPE
#undef DECLARE_VARIANT
void stream_triad(const double* x, const double* y, double* z, std::size_t n);
void cached_copy(const double* x, double* z, std::size_t n);
float compute_f32(std::size_t iterations);
double compute_f64(std::size_t iterations);
}
