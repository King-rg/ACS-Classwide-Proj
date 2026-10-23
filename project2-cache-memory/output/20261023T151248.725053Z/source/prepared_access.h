/* Controlled preparation modes for the existing dependent-chain benchmark. */
#if defined(__x86_64__) || defined(__i386__)
#include <cpuid.h>
#include <immintrin.h>
#endif

__attribute__((noinline)) static size_t dependent_pass(const uint64_t *data,
                                                       size_t position, size_t count) {
    for (size_t k = 0; k < count; ++k) position = data[position];
    __asm__ volatile("" : "+r"(position) : : "memory");
    return position;
}

static int prepared_pmu_type(void) {
#if defined(__x86_64__) || defined(__i386__)
    unsigned a,b,c,d;
    check(__get_cpuid(0,&a,&b,&c,&d) && b==0x756e6547 && d==0x49656e69 && c==0x6c65746e,
          "prepared counters require GenuineIntel");
    check(__get_cpuid(1,&a,&b,&c,&d), "CPUID unavailable");
    unsigned model=((a>>4)&15)|((a>>12)&240), family=(a>>8)&15;
    check(family==6 && model==186, "prepared counters require verified Intel model 186");
    check(d & (1u<<19), "CLFLUSH unsupported");
    check(((b>>8)&255)*8==64, "prepared tests require 64-byte cache lines");
    check(__get_cpuid(0x1a,&a,&b,&c,&d) && (a>>24)==0x40,
          "prepared counters require a pinned performance core");
    FILE *f=fopen("/sys/bus/event_source/devices/cpu_core/type","r");
    int type;
    check(f && fscanf(f,"%d",&type)==1,"cpu_core PMU unavailable");
    fclose(f);
    return type;
#else
    check(0,"prepared access requires verified x86 hardware");
    return -1;
#endif
}

static void flush_chain(uint64_t *data, size_t bytes) {
#if defined(__x86_64__) || defined(__i386__)
    for(size_t offset=0;offset<bytes;offset+=64) _mm_clflush((char *)data+offset);
    _mm_mfence();
#else
    (void)data;(void)bytes;check(0,"CLFLUSH unsupported");
#endif
}

static void prepared_counter_open(struct Counters *c, int type) {
    memset(c,0,sizeof *c);
    for(int i=0;i<4;i++) c->fd[i]=-1;
    /* Verified local perf catalog for cpu_core/model 186: cycles, retired
       L3 hits, retired L3 misses, retired L2 misses. No generic-event aliases. */
    const uint64_t configs[]={0x003c,0x04d1,0x20d1,0x10d1};
    for(int i=0;i<4;i++) {
        struct perf_event_attr attr={0};
        attr.size=sizeof attr;attr.type=type;attr.config=configs[i];
        attr.disabled=i==0;attr.exclude_kernel=1;attr.exclude_hv=1;
        attr.read_format=PERF_FORMAT_GROUP|PERF_FORMAT_TOTAL_TIME_ENABLED|PERF_FORMAT_TOTAL_TIME_RUNNING;
        c->fd[i]=syscall(SYS_perf_event_open,&attr,0,-1,i?c->fd[0]:-1,0);
        if(c->fd[i]<0) {
            int saved=errno;
            for(int j=0;j<i;j++)close(c->fd[j]);
            fprintf(stderr,"Prepared counter open failed (event 0x%lx): %s. No permissions were changed.\n",(unsigned long)configs[i],strerror(saved));
            printf("{\"check\":\"fail\",\"reason\":\"counter_open\",\"errno\":%d,\"event\":%lu}\n",saved,(unsigned long)configs[i]);
            exit(3);
        }
    }
    c->available=1;
}

/* Disable/read per pass, but retain descriptors. Reset once per measured pass. */
static int prepared_counter_read(struct Counters *c, uint64_t totals[4]) {
    check(ioctl(c->fd[0],PERF_EVENT_IOC_DISABLE,PERF_IOC_FLAG_GROUP)==0,"counter disable");
    struct {uint64_t count,enabled,running,values[4];} v;
    check(read(c->fd[0],&v,sizeof v)==sizeof v,"prepared counter read");
    if(v.count!=4 || v.enabled!=v.running || !v.running)return 0;
    for(int i=0;i<4;i++)totals[i]+=v.values[i];
    return 1;
}

static int prepared_benchmark(struct BenchmarkJob *job) {
    cpu_set_t set;CPU_ZERO(&set);CPU_SET(job->cpu,&set);
    check(sched_setaffinity(0,sizeof set,&set)==0,"prepared pinning");
    int type=prepared_pmu_type();
    struct Counters counters;prepared_counter_open(&counters,type);
    size_t count=job->span_bytes/64;
    uint64_t *data=allocate_mapping(job->span_bytes,0);
    size_t *order=malloc(count*sizeof *order),position[1];
    check(order!=NULL,"order allocation");
    for(size_t k=0;k<count;k++)order[k]=k*8;
    uint64_t seed=job->seed;shuffle_indices(order,count,&seed);
    prepare_pointer_chains(job,data,order,position,count);
    uint64_t *evict=NULL;size_t evict_count=job->eviction_bytes/64;
    if(job->preparation==1) {
        evict=allocate_mapping(job->eviction_bytes,0);
        size_t *eo=malloc(evict_count*sizeof *eo);check(eo!=NULL,"eviction order");
        for(size_t k=0;k<evict_count;k++)eo[k]=k*8;
        shuffle_indices(eo,evict_count,&seed);
        for(size_t k=0;k<evict_count;k++)evict[eo[k]]=eo[(k+1)%evict_count];
        /* Ring includes offset zero, giving a stable starting address. */
        free(eo);
    }
    uint64_t overhead_ns=0,overhead_counts[4]={0};int available=1;
    for(int k=0;k<1000;k++) {
        uint64_t t=clock_ns();counters_start(&counters);
        __asm__ volatile("" ::: "memory");
        uint64_t end=clock_ns();
        available &= prepared_counter_read(&counters,overhead_counts);
        overhead_ns+=end-t;
    }
    uint64_t elapsed=0,preparation_ns=0,passes=0,totals[4]={0};
    uint64_t invalid_passes=0;double max_overhead_fraction=0;
    const size_t initial=position[0];
    while(elapsed<job->duration_ns) {
        uint64_t prep=clock_ns();
        if(job->preparation==1) {
            check(dependent_pass(data,initial,count)==initial,"warm ring closure");
            check(dependent_pass(evict,0,evict_count)==0,"eviction ring closure");
        } else flush_chain(data,job->span_bytes);
        preparation_ns+=clock_ns()-prep;
        uint64_t pass_counts[4]={0};
        uint64_t t=clock_ns();counters_start(&counters);
        size_t final=dependent_pass(data,initial,count);
        uint64_t end=clock_ns();
        available &= prepared_counter_read(&counters,pass_counts);
        check(final==initial,"timed ring closure");
        double hit=(double)pass_counts[1]/count,miss=(double)pass_counts[2]/count;
        double l2=(double)pass_counts[3]/count,total=hit+miss;
        int residency=job->preparation==1 ? hit>=.95 && miss<=.05 : miss>=.95;
        if(!residency || total<.95 || total>1.05 || l2<.95 || l2>1.05)invalid_passes++;
        double fraction=(overhead_ns/1000.0)/(end-t);
        if(fraction>max_overhead_fraction)max_overhead_fraction=fraction;
        for(int k=0;k<4;k++)totals[k]+=pass_counts[k];
        elapsed+=end-t;passes++;
    }
    uint64_t ops=passes*count;
    int ok=available && invalid_passes==0 && max_overhead_fraction<.01;
    check(sched_getcpu()==job->cpu,"prepared migration");
    printf("{\"check\":\"%s\",\"preparation\":\"%s\",\"cpu\":%d,\"pmu_type\":%d,"
           "\"eviction_bytes\":%zu,\"elapsed_ns\":%"PRIu64",\"preparation_ns\":%"PRIu64","
           "\"passes\":%"PRIu64",\"operations\":%"PRIu64",\"ns_per_access\":%.12g,"
           "\"cycles\":%"PRIu64",\"l3_hits\":%"PRIu64",\"l3_misses\":%"PRIu64",\"l2_misses\":%"PRIu64","
           "\"counters_available\":%s,\"invalid_residency_passes\":%"PRIu64","
           "\"envelope_ns\":%.6f,\"max_overhead_fraction\":%.9g,\"checksum\":%zu}\n",
           ok?"pass":"fail",job->preparation==1?"l3-resident":"cache-flushed",job->cpu,type,
           job->eviction_bytes,elapsed,preparation_ns,passes,ops,(double)elapsed/ops,
           totals[0],totals[1],totals[2],totals[3],available?"true":"false",invalid_passes,
           overhead_ns/1000.0,max_overhead_fraction,initial);
    for(int k=0;k<4;k++)close(counters.fd[k]);
    free(order);munmap(data,job->span_bytes);
    if(evict)munmap(evict,job->eviction_bytes);
    return ok?0:4;
}
