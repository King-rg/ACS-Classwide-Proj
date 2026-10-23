#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <linux/perf_event.h>
#include <math.h>
#include <pthread.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

static void check(int yes,const char *why){if(!yes){perror(why);exit(2);}}
static uint64_t clock_ns(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC_RAW,&t);return (uint64_t)t.tv_sec*1000000000ULL+t.tv_nsec;}
static uint64_t rng(uint64_t *s){*s^=*s<<13;*s^=*s>>7;*s^=*s<<17;return *s;}
static void shuffle(size_t *a,size_t n,uint64_t *seed){for(size_t i=n-1;i>0;--i){size_t j=rng(seed)%(i+1),v=a[i];a[i]=a[j];a[j]=v;}}
static uint64_t *mapping(size_t bytes,int huge){
 const size_t alignment=2*1024*1024;size_t total=bytes+alignment;
 void *raw=mmap(NULL,total,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);check(raw!=MAP_FAILED,"mmap");
 uintptr_t aligned=((uintptr_t)raw+alignment-1)&~(alignment-1);size_t prefix=aligned-(uintptr_t)raw;
 if(prefix)check(munmap(raw,prefix)==0,"unmap prefix");
 size_t suffix=total-prefix-bytes;if(suffix)check(munmap((void*)(aligned+bytes),suffix)==0,"unmap suffix");
 check(madvise((void*)aligned,bytes,huge?MADV_HUGEPAGE:MADV_NOHUGEPAGE)==0,"madvise");return (uint64_t*)aligned;
}
static size_t huge_bytes(void *ptr){
 FILE *f=fopen("/proc/self/smaps","r");check(f!=NULL,"smaps");char line[512];unsigned long start,end;int active=0;size_t kb=0;
 while(fgets(line,sizeof line,f)){
  if(sscanf(line,"%lx-%lx",&start,&end)==2)active=(uintptr_t)ptr>=start&&(uintptr_t)ptr<end;
  else if(active&&sscanf(line,"AnonHugePages: %zu kB",&kb)==1){fclose(f);return kb*1024;}
 }fclose(f);return 0;
}
struct Counters{int fd[4];int ok;uint64_t v[4],enabled,running;};
static void counters_open(struct Counters *c){
 memset(c,0,sizeof *c);for(int i=0;i<4;++i)c->fd[i]=-1;
 const uint64_t config[]={PERF_COUNT_HW_CPU_CYCLES,PERF_COUNT_HW_INSTRUCTIONS,
 PERF_COUNT_HW_CACHE_LL|(PERF_COUNT_HW_CACHE_OP_READ<<8)|(PERF_COUNT_HW_CACHE_RESULT_MISS<<16),
 PERF_COUNT_HW_CACHE_DTLB|(PERF_COUNT_HW_CACHE_OP_READ<<8)|(PERF_COUNT_HW_CACHE_RESULT_MISS<<16)};
 for(int i=0;i<4;++i){struct perf_event_attr a={0};a.size=sizeof a;a.type=i<2?PERF_TYPE_HARDWARE:PERF_TYPE_HW_CACHE;a.config=config[i];a.disabled=i==0;a.exclude_kernel=1;a.exclude_hv=1;a.read_format=PERF_FORMAT_GROUP|PERF_FORMAT_TOTAL_TIME_ENABLED|PERF_FORMAT_TOTAL_TIME_RUNNING;
  c->fd[i]=syscall(SYS_perf_event_open,&a,0,-1,i?c->fd[0]:-1,0);
  if(c->fd[i]<0){for(int j=0;j<i;++j)close(c->fd[j]);for(int j=0;j<4;++j)c->fd[j]=-1;return;}
 }c->ok=1;
}
static void counters_start(struct Counters *c){if(c->ok){check(ioctl(c->fd[0],PERF_EVENT_IOC_RESET,PERF_IOC_FLAG_GROUP)==0,"perf reset");check(ioctl(c->fd[0],PERF_EVENT_IOC_ENABLE,PERF_IOC_FLAG_GROUP)==0,"perf enable");}}
static void counters_stop(struct Counters *c){if(c->ok){check(ioctl(c->fd[0],PERF_EVENT_IOC_DISABLE,PERF_IOC_FLAG_GROUP)==0,"perf disable");struct{uint64_t n,e,r,v[4];}d;check(read(c->fd[0],&d,sizeof d)==sizeof d,"perf read");if(d.n!=4||d.e!=d.r||d.r==0)c->ok=0;else{memcpy(c->v,d.v,sizeof c->v);c->enabled=d.e;c->running=d.r;}}for(int i=0;i<4;++i)if(c->fd[i]>=0)close(c->fd[i]);}
struct Job{size_t bytes,spacing,block,streams;int cpu,huge,random,read_pct,bandwidth;uint64_t duration,seed;pthread_barrier_t *barrier;double elapsed;uint64_t operations,payload,checksum;size_t backed;struct Counters counters;};
static uint64_t bandwidth_pass(uint64_t *a,const size_t *order,size_t count,size_t block,int reads,uint64_t value){
 uint64_t sum=0;size_t words=block/8;
 for(size_t k=0;k<count;++k){uint64_t *p=a+order[k];if((int)(k%10)<reads/10){for(size_t j=0;j<words;++j)sum+=p[j];}else{for(size_t j=0;j<words;++j)p[j]=value;}}
 return sum;
}
static void *worker(void *arg){
 struct Job *j=arg;cpu_set_t set;CPU_ZERO(&set);CPU_SET(j->cpu,&set);check(pthread_setaffinity_np(pthread_self(),sizeof set,&set)==0,"affinity");
 uint64_t *a=mapping(j->bytes,j->huge);for(size_t i=0;i<j->bytes/8;++i)a[i]=1;
 size_t count=j->bytes/j->spacing;check(count>=j->streams&&j->streams<=16,"chain count");size_t *order=malloc(count*sizeof *order);check(order!=NULL,"order allocation");
 for(size_t i=0;i<count;++i)order[i]=i*j->spacing/8;
 uint64_t seed=j->seed;if(j->random)shuffle(order,count,&seed);
 size_t idx[16]={0};size_t per=count/j->streams;count=per*j->streams;
 if(!j->bandwidth){
  for(size_t s=0;s<j->streams;++s){size_t lo=s*per;idx[s]=order[lo];for(size_t k=0;k<per;++k)a[order[lo+k]]=order[lo+(k+1)%per];}
  unsigned char *seen=calloc(j->bytes/j->spacing,1);check(seen!=NULL,"seen allocation");
  for(size_t s=0;s<j->streams;++s){size_t x=idx[s];for(size_t k=0;k<per;++k){check(x<j->bytes/8&&x%(j->spacing/8)==0,"ring bound");size_t slot=x/(j->spacing/8);check(!seen[slot],"duplicate ring entry");seen[slot]=1;x=a[x];}check(x==idx[s],"ring closure");}free(seen);
 }else{
  // Reads remain one; write blocks always contain a known constant.
  bandwidth_pass(a,order,count,j->block,j->read_pct,2);
 }
 j->backed=huge_bytes(a);counters_open(&j->counters);
 pthread_barrier_wait(j->barrier);uint64_t start=clock_ns();counters_start(&j->counters);uint64_t now=start,ops=0,sum=0,passes=0;
 if(j->bandwidth){do{sum=bandwidth_pass(a,order,count,j->block,j->read_pct,2);++passes;now=clock_ns();}while(now-start<j->duration);ops=passes*count;}
 else{do{for(int b=0;b<1024;++b)for(size_t s=0;s<j->streams;++s)idx[s]=a[idx[s]];ops+=1024*j->streams;now=clock_ns();}while(now-start<j->duration);for(size_t s=0;s<j->streams;++s)sum+=idx[s];}
 counters_stop(&j->counters);j->elapsed=now-start;j->operations=ops;j->payload=j->bandwidth?passes*count*j->block:ops*64;j->checksum=sum;
 if(j->bandwidth){uint64_t expected=0;for(size_t k=0;k<count;++k){int readblock=(int)(k%10)<j->read_pct/10;for(size_t w=0;w<j->block/8;++w)check(a[order[k]+w]==(uint64_t)(readblock?1:2),"bandwidth output");if(readblock)expected+=j->block/8;}check(sum==expected,"read checksum");}
 else for(size_t s=0;s<j->streams;++s)check(idx[s]<j->bytes/8,"final pointer");
 check(sched_getcpu()==j->cpu,"migration");free(order);check(munmap(a,j->bytes)==0,"unmap");return NULL;
}
int main(int argc,char **argv){
 check(argc==11,"usage: mode bytes spacing block read_pct random huge streams ms cpu_list");
 struct Job base={0};base.bandwidth=!strcmp(argv[1],"bandwidth");check(base.bandwidth||!strcmp(argv[1],"latency"),"mode");
 base.bytes=strtoull(argv[2],0,10);base.spacing=strtoull(argv[3],0,10);base.block=strtoull(argv[4],0,10);base.read_pct=atoi(argv[5]);base.random=atoi(argv[6]);base.huge=atoi(argv[7]);base.streams=strtoull(argv[8],0,10);base.duration=strtoull(argv[9],0,10)*1000000ULL;base.seed=4320;
 check(base.bytes>=4096&&base.bytes<=512ULL*1024*1024&&base.bytes%4096==0,"bytes bound");check(base.spacing>=8&&base.spacing%8==0&&base.block>=8&&base.block<=base.spacing&&base.block%8==0,"block/spacing");check(base.duration>=1000000&&base.duration<=1000000000,"duration");check(base.streams>=1&&base.streams<=16&&base.read_pct>=0&&base.read_pct<=100&&base.read_pct%10==0,"options");
 struct Job jobs[8];pthread_t threads[8];pthread_barrier_t barrier;int n=0;char *list=strdup(argv[10]),*save=NULL;
 for(char *s=strtok_r(list,",",&save);s;s=strtok_r(NULL,",",&save)){check(n<8,"thread limit");jobs[n]=base;jobs[n].cpu=atoi(s);jobs[n].barrier=&barrier;++n;}check(n>0,"CPU list");pthread_barrier_init(&barrier,NULL,n);
 for(int i=0;i<n;++i)check(pthread_create(&threads[i],NULL,worker,&jobs[i])==0,"pthread_create");
 double max_elapsed=0,total_elapsed=0;uint64_t ops=0,payload=0,hp=0,vals[4]={0};int perf=1;
 for(int i=0;i<n;++i){pthread_join(threads[i],NULL);if(jobs[i].elapsed>max_elapsed)max_elapsed=jobs[i].elapsed;total_elapsed+=jobs[i].elapsed;ops+=jobs[i].operations;payload+=jobs[i].payload;hp+=jobs[i].backed;perf&=jobs[i].counters.ok;for(int k=0;k<4;++k)vals[k]+=jobs[i].counters.v[k];}
 printf("{\"elapsed_ns\":%.0f,\"operations\":%" PRIu64 ",\"payload_bytes\":%" PRIu64 ",\"ns_per_access\":%.9g,\"chain_latency_ns\":%.9g,\"million_accesses_s\":%.9g,\"gib_s\":%.9g,\"threads\":%d,\"streams\":%zu,\"huge_bytes\":%" PRIu64 ",\"counters_available\":%s,\"cycles\":%" PRIu64 ",\"instructions\":%" PRIu64 ",\"llc_read_misses\":%" PRIu64 ",\"dtlb_read_misses\":%" PRIu64 ",\"check\":\"pass\"}\n",max_elapsed,ops,payload,total_elapsed/ops,total_elapsed/ops*base.streams,ops/max_elapsed*1000,payload/max_elapsed*1e9/1073741824,n,base.streams,hp,perf?"true":"false",vals[0],vals[1],vals[2],vals[3]);
 pthread_barrier_destroy(&barrier);free(list);return 0;
}
