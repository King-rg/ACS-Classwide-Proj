#include "kernels.hpp"
#include <immintrin.h>
namespace evidence {
static __m256 load_f32(const float* p, std::size_t stride) {
    if (stride==1) return _mm256_loadu_ps(p);
    return _mm256_i32gather_ps(p, _mm256_setr_epi32(0, stride, 2*stride, 3*stride, 4*stride, 5*stride, 6*stride, 7*stride), sizeof(float));
}
static void store_f32(float* p, __m256 v, std::size_t stride) {
    if (stride==1) { _mm256_storeu_ps(p,v); return; }
    alignas(32) float lanes[8]; _mm256_store_ps(lanes,v);
    for (std::size_t lane=0; lane<8; ++lane) p[lane*stride]=lanes[lane];
}
void axpy_simd_f32(float a, const float* x, float* y, std::size_t n, std::size_t stride) {
    auto va=_mm256_set1_ps(a); std::size_t i=0;
    for (; n-i>=8; i+=8) {
        auto vx=load_f32(x+i*stride,stride), vy=load_f32(y+i*stride,stride);
        store_f32(y+i*stride,_mm256_add_ps(_mm256_mul_ps(va,vx),vy),stride);
    }
    for (;i<n;++i) { auto j=i*stride; y[j]=a*x[j]+y[j]; }
}
float dot_simd_f32(const float* x, const float* y, std::size_t n, std::size_t stride) {
    auto partial=_mm256_setzero_ps(); std::size_t i=0;
    for (; n-i>=8; i+=8) {
        auto vx=load_f32(x+i*stride,stride), vy=load_f32(y+i*stride,stride);
        partial=_mm256_add_ps(partial,_mm256_mul_ps(vx,vy));
    }
    alignas(32) float lanes[8]; _mm256_store_ps(lanes,partial);
    float sum=0; for (auto lane:lanes) sum+=lane;
    for (;i<n;++i) sum+=x[i*stride]*y[i*stride];
    return sum;
}
void multiply_simd_f32(const float* x, const float* y, float* z, std::size_t n, std::size_t stride) {
    std::size_t i=0;
    for (;n-i>=8;i+=8) {
        auto vx=load_f32(x+i*stride,stride), vy=load_f32(y+i*stride,stride);
        store_f32(z+i*stride,_mm256_mul_ps(vx,vy),stride);
    }
    for (;i<n;++i) z[i*stride]=x[i*stride]*y[i*stride];
}
static __m256d load_f64(const double* p, std::size_t stride) {
    if (stride==1) return _mm256_loadu_pd(p);
    return _mm256_i64gather_pd(p, _mm256_setr_epi64x(0, stride, 2*stride, 3*stride), sizeof(double));
}
static void store_f64(double* p, __m256d v, std::size_t stride) {
    if (stride==1) { _mm256_storeu_pd(p,v); return; }
    alignas(32) double lanes[4]; _mm256_store_pd(lanes,v);
    for (std::size_t lane=0; lane<4; ++lane) p[lane*stride]=lanes[lane];
}
void axpy_simd_f64(double a, const double* x, double* y, std::size_t n, std::size_t stride) {
    auto va=_mm256_set1_pd(a); std::size_t i=0;
    for (; n-i>=4; i+=4) {
        auto vx=load_f64(x+i*stride,stride), vy=load_f64(y+i*stride,stride);
        store_f64(y+i*stride,_mm256_add_pd(_mm256_mul_pd(va,vx),vy),stride);
    }
    for (;i<n;++i) { auto j=i*stride; y[j]=a*x[j]+y[j]; }
}
double dot_simd_f64(const double* x, const double* y, std::size_t n, std::size_t stride) {
    auto partial=_mm256_setzero_pd(); std::size_t i=0;
    for (; n-i>=4; i+=4) {
        auto vx=load_f64(x+i*stride,stride), vy=load_f64(y+i*stride,stride);
        partial=_mm256_add_pd(partial,_mm256_mul_pd(vx,vy));
    }
    alignas(32) double lanes[4]; _mm256_store_pd(lanes,partial);
    double sum=0; for (auto lane:lanes) sum+=lane;
    for (;i<n;++i) sum+=x[i*stride]*y[i*stride];
    return sum;
}
void multiply_simd_f64(const double* x, const double* y, double* z, std::size_t n, std::size_t stride) {
    std::size_t i=0;
    for (;n-i>=4;i+=4) {
        auto vx=load_f64(x+i*stride,stride), vy=load_f64(y+i*stride,stride);
        store_f64(z+i*stride,_mm256_mul_pd(vx,vy),stride);
    }
    for (;i<n;++i) z[i*stride]=x[i*stride]*y[i*stride];
}
// Independent streaming references, not assignment-kernel aliases.
void stream_triad(const double* x, const double* y, double* z, std::size_t n) {
    for (std::size_t i=0;i<n;i+=4) {
        _mm256_stream_pd(z+i,_mm256_add_pd(_mm256_load_pd(x+i),_mm256_load_pd(y+i)));
    }
    _mm_sfence(); // Include completion of non-temporal stores in the call.
}
void cached_copy(const double* x, double* z, std::size_t n) {
    for (std::size_t i=0;i<n;i+=4) _mm256_store_pd(z+i,_mm256_load_pd(x+i));
    _mm_sfence();
}
} // namespace evidence
