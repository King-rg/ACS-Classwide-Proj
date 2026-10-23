#include <stddef.h>
void stream_f(const float *restrict x,const float *restrict y,float *restrict z,size_t n) {
    for(size_t i=0;i<n;++i) z[i]=x[i]+1.25f*y[i];
}
