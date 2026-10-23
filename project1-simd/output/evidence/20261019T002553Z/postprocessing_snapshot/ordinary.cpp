#include "kernels.hpp"
// The same readable loops are compiled once with vectorization disabled and once
// with the compiler's vectorizer enabled. Relaxed FP flags permit dot reassociation.
#define JOIN_(A,B,C) A##B##C
#define JOIN(A,B,C) JOIN_(A,B,C)
#define DEFINE(T,S) \
void JOIN(axpy_,VARIANT,_##S)(T a, const T* __restrict x, T* __restrict y, std::size_t n, std::size_t stride) { \
    for (std::size_t i=0; i<n; ++i) { const auto j=i*stride; y[j]=a*x[j]+y[j]; } \
} \
T JOIN(dot_,VARIANT,_##S)(const T* __restrict x, const T* __restrict y, std::size_t n, std::size_t stride) { \
    T sum=0; for (std::size_t i=0; i<n; ++i) { const auto j=i*stride; sum+=x[j]*y[j]; } return sum; \
} \
void JOIN(multiply_,VARIANT,_##S)(const T* __restrict x, const T* __restrict y, T* __restrict z, std::size_t n, std::size_t stride) { \
    for (std::size_t i=0; i<n; ++i) { const auto j=i*stride; z[j]=x[j]*y[j]; } \
}
namespace evidence { DEFINE(float,f32) DEFINE(double,f64) }
