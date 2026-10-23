#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <math.h>
#include <time.h>
#include <sched.h>
#include <float.h>
#include <string.h>
#ifdef DOUBLE
#define T double
#define LABEL "double"
#define SCALAR daxpy_scalar
#define AUTO daxpy_auto
#define STRIDE_SCALAR axpy_stride_scalar_d
#define STRIDE_AUTO axpy_stride_auto_d
#define DOT_SCALAR dot_double_scalar
#define DOT_AUTO dot_double_auto
#define DOT_STRICT dot_double_strict
#define EPS DBL_EPSILON
#else
#define T float
#define LABEL "float"
#define SCALAR saxpy_scalar
#define AUTO saxpy_auto
#define STRIDE_SCALAR axpy_stride_scalar_f
#define STRIDE_AUTO axpy_stride_auto_f
#define DOT_SCALAR dot_float_scalar
#define DOT_AUTO dot_float_auto
#define DOT_STRICT dot_float_strict
#define EPS FLT_EPSILON
#endif
void SCALAR(T,const T*,T*,size_t); void AUTO(T,const T*,T*,size_t);
void STRIDE_SCALAR(T,const T*,T*,size_t,size_t); void STRIDE_AUTO(T,const T*,T*,size_t,size_t);
T DOT_SCALAR(const T*,const T*,size_t); T DOT_AUTO(const T*,const T*,size_t); T DOT_STRICT(const T*,const T*,size_t);
void stream_f(const float*,const float*,float*,size_t); float compute_f(size_t);
static volatile double sink;
static void require(int yes,const char *msg){if(!yes){fprintf(stderr,"%s\n",msg);exit(2);}}
static uint64_t ns(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC_RAW,&t);return (uint64_t)t.tv_sec*1000000000ULL+t.tv_nsec;}
static T *alloc(size_t n){void *p;require(posix_memalign(&p,64,n*sizeof(T))==0,"allocation failed");return p;}
static T xv(size_t i){return (T)(i%17)/16;} static T yv(size_t i){return (T)(i%13)/16;}
int main(int argc,char **argv){
 require(argc==7,"study n stride offset trials calls");
 const char *study=argv[1];size_t n=strtoull(argv[2],0,10),st=strtoull(argv[3],0,10),off=strtoull(argv[4],0,10),trials=strtoull(argv[5],0,10),calls=strtoull(argv[6],0,10);
 require(n>0&&n<=33554432&&st>=1&&st<=8&&off<=1&&calls>0,"invalid case");
 int dot=!strcmp(study,"dot"),stream=!strcmp(study,"stream"),compute=!strcmp(study,"compute"),strided=!strcmp(study,"stride");
 size_t span=n*st,len=span+off+16;
 T *xb=alloc(len),*yb=alloc(len),*zb=stream?alloc(len):NULL,*x=xb+off,*y=yb+off,*z=zb?zb+off:NULL;
 for(size_t i=0;i<len;++i){xb[i]=-12345;yb[i]=-12345;if(zb)zb[i]=-12345;}
 long double dotref=0;
 for(size_t i=0;i<n;++i){x[i*st]=xv(i);y[i*st]=yv(i);dotref+=(long double)xv(i)*yv(i);}
 printf("study,type,n,stride,offset,trial,variant,calls,elapsed_ns,ns_per_call,cpu,check\n");
 const int variants=(stream||compute)?1:(dot?3:2);
 for(size_t trial=0;trial<trials;++trial)for(int order=0;order<variants;++order){
  int v=(order+trial)%variants; const char *name=(stream||compute)?"calibration":v==0?"scalar":v==1?"auto":"strict";
  void (*ax)(T,const T*,T*,size_t)=v==0?SCALAR:AUTO;
  void (*sx)(T,const T*,T*,size_t,size_t)=v==0?STRIDE_SCALAR:STRIDE_AUTO;
  T (*dx)(const T*,const T*,size_t)=v==0?DOT_SCALAR:v==1?DOT_AUTO:DOT_STRICT;
  T sum=0;
  for(int warm=0;warm<5;++warm){
   if(compute)sink=compute_f(n); else if(stream)stream_f((float*)x,(float*)y,(float*)z,n);
   else if(dot)sum=dx(x,y,n);else if(strided)sx(1.25,x,y,n,st);else ax(1.25,x,y,n);
  }
  if(!dot&&!stream&&!compute)for(size_t i=0;i<n;++i)y[i*st]=yv(i);
  int cpu=sched_getcpu();uint64_t start=ns();
  for(size_t c=0;c<calls;++c){
   if(compute)sink=compute_f(n);else if(stream)stream_f((float*)x,(float*)y,(float*)z,n);
   else if(dot)sum=dx(x,y,n);else if(strided)sx(1.25,x,y,n,st);else ax(1.25,x,y,n);
  }
  uint64_t elapsed=ns()-start;require(cpu==sched_getcpu(),"CPU migration");require(elapsed>0,"zero duration");sink+=sum;
  if(dot)require(isfinite(sum)&&fabsl((long double)sum-dotref)<=8*EPS*n*fabsl(dotref),"dot validation");
  if(compute)require(isfinite(sink),"compute validation");
  for(size_t j=0;j<len;++j){
   int active=j>=off&&(j-off)%st==0&&(j-off)/st<n;size_t i=active?(j-off)/st:0;
   require(xb[j]==(active?xv(i):-12345),"input/guard changed");
   long double expected=active?yv(i):-12345;
   if(active&&!dot&&!stream&&!compute)expected+=(long double)calls*1.25*xv(i);
   require(yb[j]==(T)expected,"output/gap/guard validation");
   if(stream)require(zb[j]==(active?(T)(xv(i)+1.25*yv(i)):-12345),"stream validation");
  }
  printf("%s,%s,%zu,%zu,%zu,%zu,%s,%zu,%llu,%.9g,%d,pass\n",study,LABEL,n,st,off,trial,name,calls,(unsigned long long)elapsed,(double)elapsed/calls,cpu);fflush(stdout);
 }
 free(xb);free(yb);free(zb);return 0;
}
