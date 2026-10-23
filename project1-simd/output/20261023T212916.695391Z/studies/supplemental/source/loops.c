#include <stddef.h>
#ifndef NAME
#define NAME axpy_stride_auto_f
#endif
#ifndef TYPE
#define TYPE float
#endif
void NAME(TYPE a, const TYPE *restrict x, TYPE *restrict y, size_t n, size_t stride) {
    for (size_t i=0; i<n; ++i) y[i*stride] = a*x[i*stride] + y[i*stride];
}
