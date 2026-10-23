// Bounded single-thread AVX2 workload; counters cover each timed interval only.
#include "kernels.hpp"
#include <linux/perf_event.h>
#include <sys/syscall.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <sched.h>
#include <time.h>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <string>
static double now(clockid_t c) { timespec t{}; clock_gettime(c,&t);return t.tv_sec+t.tv_nsec*1e-9; }
int main(int argc,char**argv) {try {
 if(argc!=3) throw std::runtime_error("usage: worker compute|dot cpu_core_perf_type");
 cpu_set_t set; CPU_ZERO(&set);CPU_SET(0,&set);if(sched_setaffinity(0,sizeof(set),&set)) throw std::runtime_error("affinity");
 perf_event_attr a{};a.size=sizeof(a);a.type=std::stoi(argv[2]);a.config=0x3c /* CPU_CLK_UNHALTED.THREAD, explicit P-core PMU */;a.disabled=1;a.exclude_kernel=1;a.exclude_hv=1;a.read_format=PERF_FORMAT_TOTAL_TIME_ENABLED|PERF_FORMAT_TOTAL_TIME_RUNNING;
 int fd=syscall(__NR_perf_event_open,&a,0,-1,-1,0);if(fd<0) throw std::runtime_error(std::string("perf cycles: ")+strerror(errno));
 alignas(64) float x[2048],y[2048];for(int i=0;i<2048;i++){x[i]=float(i%17)/17;y[i]=float(i%13)/13;}
 const bool compute=std::string(argv[1])=="compute";if(!compute && std::string(argv[1])!="dot")throw std::runtime_error("invalid workload");
 long double dot_reference=0;for(int i=0;i<2048;i++)dot_reference+=(long double)x[i]*y[i];
 volatile float sink=0;
 for(int interval=0;interval<4;interval++) {
  ioctl(fd,PERF_EVENT_IOC_RESET,0);ioctl(fd,PERF_EVENT_IOC_ENABLE,0);
  double w=now(CLOCK_MONOTONIC),c=now(CLOCK_THREAD_CPUTIME_ID);uint64_t calls=0;
  do {for(int b=0;b<16;b++){sink=compute?evidence::compute_f32(8192):evidence::dot_simd_f32(x,y,2048,1);++calls;}}while(now(CLOCK_MONOTONIC)-w<0.75);
  double cpu=now(CLOCK_THREAD_CPUTIME_ID)-c,wall=now(CLOCK_MONOTONIC)-w;ioctl(fd,PERF_EVENT_IOC_DISABLE,0);
  struct {uint64_t cycles,enabled,running;} r{};if(read(fd,&r,sizeof(r))!=sizeof(r)||!r.cycles||!r.running||r.running!=r.enabled||!std::isfinite(sink))throw std::runtime_error("invalid counter or result");
  // Independent deterministic numerical check; register recurrence converges near 1..8.
  if((compute && !(sink>7 && sink<40))||(!compute && std::abs(float(sink)-dot_reference)>0.01))throw std::runtime_error("correctness");
  uint64_t units=calls*(compute?8192ULL*128:2048ULL*2);
  printf("{\"interval\":%d,\"warmup\":%s,\"calls\":%llu,\"operations\":%llu,\"wall_s\":%.9f,\"cpu_s\":%.9f,\"cycles\":%llu,\"enabled\":%llu,\"running\":%llu,\"checksum\":%.9g}\n",interval,interval==0?"true":"false",(unsigned long long)calls,(unsigned long long)units,wall,cpu,(unsigned long long)r.cycles,(unsigned long long)r.enabled,(unsigned long long)r.running,float(sink));fflush(stdout);
 }
 close(fd);return 0;
 }catch(const std::exception&e){fprintf(stderr,"%s\n",e.what());return 1;}}
