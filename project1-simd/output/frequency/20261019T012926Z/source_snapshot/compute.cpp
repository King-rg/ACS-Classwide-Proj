#include "kernels.hpp"
#include <immintrin.h>
namespace evidence {
float compute_f32(std::size_t iterations) {
    __m256 a0=_mm256_set1_ps(1.0);
    __m256 a1=_mm256_set1_ps(2.0);
    __m256 a2=_mm256_set1_ps(3.0);
    __m256 a3=_mm256_set1_ps(4.0);
    __m256 a4=_mm256_set1_ps(5.0);
    __m256 a5=_mm256_set1_ps(6.0);
    __m256 a6=_mm256_set1_ps(7.0);
    __m256 a7=_mm256_set1_ps(8.0);
    const auto factor=_mm256_set1_ps(0.99999), bias=_mm256_set1_ps(0.00001);
    for (std::size_t i=0;i<iterations;++i) {
        a0=_mm256_fmadd_ps(a0,factor,bias);
        a1=_mm256_fmadd_ps(a1,factor,bias);
        a2=_mm256_fmadd_ps(a2,factor,bias);
        a3=_mm256_fmadd_ps(a3,factor,bias);
        a4=_mm256_fmadd_ps(a4,factor,bias);
        a5=_mm256_fmadd_ps(a5,factor,bias);
        a6=_mm256_fmadd_ps(a6,factor,bias);
        a7=_mm256_fmadd_ps(a7,factor,bias);
    }
    a0=_mm256_add_ps(a0,a1);
    a0=_mm256_add_ps(a0,a2);
    a0=_mm256_add_ps(a0,a3);
    a0=_mm256_add_ps(a0,a4);
    a0=_mm256_add_ps(a0,a5);
    a0=_mm256_add_ps(a0,a6);
    a0=_mm256_add_ps(a0,a7);
    alignas(32) float lanes[8]; _mm256_store_ps(lanes,a0);
    return lanes[0];
}
double compute_f64(std::size_t iterations) {
    __m256d a0=_mm256_set1_pd(1.0);
    __m256d a1=_mm256_set1_pd(2.0);
    __m256d a2=_mm256_set1_pd(3.0);
    __m256d a3=_mm256_set1_pd(4.0);
    __m256d a4=_mm256_set1_pd(5.0);
    __m256d a5=_mm256_set1_pd(6.0);
    __m256d a6=_mm256_set1_pd(7.0);
    __m256d a7=_mm256_set1_pd(8.0);
    const auto factor=_mm256_set1_pd(0.99999), bias=_mm256_set1_pd(0.00001);
    for (std::size_t i=0;i<iterations;++i) {
        a0=_mm256_fmadd_pd(a0,factor,bias);
        a1=_mm256_fmadd_pd(a1,factor,bias);
        a2=_mm256_fmadd_pd(a2,factor,bias);
        a3=_mm256_fmadd_pd(a3,factor,bias);
        a4=_mm256_fmadd_pd(a4,factor,bias);
        a5=_mm256_fmadd_pd(a5,factor,bias);
        a6=_mm256_fmadd_pd(a6,factor,bias);
        a7=_mm256_fmadd_pd(a7,factor,bias);
    }
    a0=_mm256_add_pd(a0,a1);
    a0=_mm256_add_pd(a0,a2);
    a0=_mm256_add_pd(a0,a3);
    a0=_mm256_add_pd(a0,a4);
    a0=_mm256_add_pd(a0,a5);
    a0=_mm256_add_pd(a0,a6);
    a0=_mm256_add_pd(a0,a7);
    alignas(32) double lanes[4]; _mm256_store_pd(lanes,a0);
    return lanes[0];
}
}
