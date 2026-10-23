#include <immintrin.h>
#include <stddef.h>
float compute_f(size_t n) {
    __m256 a0=_mm256_set1_ps(1.0f);
    __m256 a1=_mm256_set1_ps(2.0f);
    __m256 a2=_mm256_set1_ps(3.0f);
    __m256 a3=_mm256_set1_ps(4.0f);
    __m256 a4=_mm256_set1_ps(5.0f);
    __m256 a5=_mm256_set1_ps(6.0f);
    __m256 a6=_mm256_set1_ps(7.0f);
    __m256 a7=_mm256_set1_ps(8.0f);
    const __m256 f=_mm256_set1_ps(0.99999f), b=_mm256_set1_ps(0.00001f);
    for(size_t j=0;j<n;++j) {
        a0=_mm256_fmadd_ps(a0,f,b);
        a1=_mm256_fmadd_ps(a1,f,b);
        a2=_mm256_fmadd_ps(a2,f,b);
        a3=_mm256_fmadd_ps(a3,f,b);
        a4=_mm256_fmadd_ps(a4,f,b);
        a5=_mm256_fmadd_ps(a5,f,b);
        a6=_mm256_fmadd_ps(a6,f,b);
        a7=_mm256_fmadd_ps(a7,f,b);
    }
    a0=_mm256_add_ps(a0,a1);
    a0=_mm256_add_ps(a0,a2);
    a0=_mm256_add_ps(a0,a3);
    a0=_mm256_add_ps(a0,a4);
    a0=_mm256_add_ps(a0,a5);
    a0=_mm256_add_ps(a0,a6);
    a0=_mm256_add_ps(a0,a7);
    float out[8]; _mm256_storeu_ps(out,a0); return out[0];
}
