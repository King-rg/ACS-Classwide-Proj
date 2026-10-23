/* Opt-in, single-register dependent-load kernel for source-resolved sampling. */
extern const unsigned char hierarchy_load_pc[];
__attribute__((noinline,noclone)) static uintptr_t hierarchy_chase(uintptr_t p, size_t n) {
    __asm__ volatile(".global hierarchy_load_pc\n"
                     "hierarchy_load_pc:\n\t"
                     "mov (%[p]), %[p]\n\t"
                     "dec %[n]\n\t"
                     "jnz hierarchy_load_pc\n\t"
                     : [p] "+r"(p), [n] "+r"(n) : : "cc", "memory");
    return p;
}

static uint64_t hierarchy_clock(clockid_t id) {
    struct timespec t; check(clock_gettime(id,&t)==0,"hierarchy clock");
    return (uint64_t)t.tv_sec*1000000000ULL+t.tv_nsec;
}

static double hierarchy_tsc_hz(void) {
    unsigned a,b,c,d;
    if (__get_cpuid_count(0x15,0,&a,&b,&c,&d) && a && b && c)
        return (double)c*b/a;
    unsigned aux; uint64_t start=clock_ns(), t0=__rdtscp(&aux), end;
    do {end=clock_ns();} while(end-start<20000000);
    uint64_t t1=__rdtscp(&aux);
    return (double)(t1-t0)*1e9/(end-start);
}

static int hierarchy_main(int argc,char **argv) {
    check(argc==5,"usage: hierarchy bytes ms cpu");
    size_t bytes=strtoull(argv[2],NULL,10); unsigned ms=strtoul(argv[3],NULL,10);
    int cpu=atoi(argv[4]);
    check(bytes>=4096 && bytes<=192ULL*1024*1024 && bytes%4096==0 && ms>=1 && ms<=1000,"hierarchy bounds");
    check(cpu>=0 && cpu<CPU_SETSIZE,"hierarchy CPU");
    cpu_set_t set; CPU_ZERO(&set);CPU_SET(cpu,&set);
    check(sched_setaffinity(0,sizeof set,&set)==0,"hierarchy pinning");
    int pmu=prepared_pmu_type();double tsc_hz=hierarchy_tsc_hz();
    size_t n=bytes/64; uint64_t *data=allocate_mapping(bytes,0);
    size_t *order=malloc(n*sizeof *order);check(order!=NULL,"hierarchy order");
    for(size_t i=0;i<n;i++)order[i]=i*8;
    uint64_t seed=4320;shuffle_indices(order,n,&seed);
    for(size_t i=0;i<n;i++)data[order[i]]=(uintptr_t)&data[order[(i+1)%n]];
    uintptr_t p=(uintptr_t)&data[order[0]],first=p;
    check(hierarchy_chase(p,n)==first,"hierarchy ring closure");
    free(order);
    /* Fixed cycles/ref-cycles plus four programmable source counters. */
    int fd[6],available=1,saved_errno=0;
    int event_count=getenv("PROJECT2_HIERARCHY_SAMPLED")?2:6;
    const uint64_t configs[]={PERF_COUNT_HW_CPU_CYCLES,PERF_COUNT_HW_REF_CPU_CYCLES,
                             0x01d1,0x02d1,0x04d1,0x01d3};
    for(int i=0;i<6;i++)fd[i]=-1;
    for(int i=0;i<event_count;i++) {
        struct perf_event_attr a={0};a.size=sizeof a;
        a.type=i<2?PERF_TYPE_HARDWARE:(unsigned)pmu;a.config=configs[i];
        a.disabled=i==0;a.exclude_kernel=1;a.exclude_hv=1;
        a.read_format=PERF_FORMAT_GROUP|PERF_FORMAT_TOTAL_TIME_ENABLED|PERF_FORMAT_TOTAL_TIME_RUNNING;
        fd[i]=syscall(SYS_perf_event_open,&a,0,-1,i?fd[0]:-1,0);
        if(fd[i]<0){available=0;saved_errno=errno;break;}
    }
    if(available){check(ioctl(fd[0],PERF_EVENT_IOC_RESET,PERF_IOC_FLAG_GROUP)==0,"hierarchy reset");
        check(ioctl(fd[0],PERF_EVENT_IOC_ENABLE,PERF_IOC_FLAG_GROUP)==0,"hierarchy enable");}
    uint64_t start=hierarchy_clock(CLOCK_MONOTONIC),now=start,ops=0;
    uint64_t cpu_start=hierarchy_clock(CLOCK_THREAD_CPUTIME_ID);
    do {p=hierarchy_chase(p,65536);ops+=65536;now=hierarchy_clock(CLOCK_MONOTONIC);}
    while(now-start<(uint64_t)ms*1000000);
    uint64_t cpu_end=hierarchy_clock(CLOCK_THREAD_CPUTIME_ID);
    struct {uint64_t count,enabled,running,v[6];} counts={0};
    if(available){check(ioctl(fd[0],PERF_EVENT_IOC_DISABLE,PERF_IOC_FLAG_GROUP)==0,"hierarchy disable");
        ssize_t nr=read(fd[0],&counts,sizeof counts);
        available=nr==(ssize_t)((3+event_count)*sizeof(uint64_t)) && counts.count==(uint64_t)event_count && counts.running>0 && counts.enabled==counts.running;}
    check(p>=(uintptr_t)data && p<(uintptr_t)data+bytes && (p-(uintptr_t)data)%64==0,"hierarchy final pointer");
    check(sched_getcpu()==cpu,"hierarchy migration");
    printf("{\"check\":\"pass\",\"bytes\":%zu,\"cpu\":%d,\"pid\":%d,\"load_ip\":%"PRIuPTR","
           "\"data_start\":%"PRIuPTR",\"data_end\":%"PRIuPTR",\"start_ns\":%"PRIu64",\"end_ns\":%"PRIu64","
           "\"elapsed_ns\":%"PRIu64",\"thread_cpu_ns\":%"PRIu64",\"operations\":%"PRIu64",\"ns_per_access\":%.12g,"
           "\"counters_available\":%s,\"counter_errno\":%d,\"time_enabled\":%"PRIu64",\"time_running\":%"PRIu64","
           "\"cycles\":%"PRIu64",\"ref_cycles\":%"PRIu64",\"l1_hits\":%"PRIu64",\"l2_hits\":%"PRIu64","
           "\"l3_hits\":%"PRIu64",\"dram_reads\":%"PRIu64",\"tsc_hz\":%.12g,\"checksum\":%"PRIuPTR"}\n",
           bytes,cpu,getpid(),(uintptr_t)hierarchy_load_pc,(uintptr_t)data,(uintptr_t)data+bytes,start,now,
           now-start,cpu_end-cpu_start,ops,(double)(now-start)/ops,available?"true":"false",saved_errno,
           counts.enabled,counts.running,counts.v[0],counts.v[1],counts.v[2],counts.v[3],counts.v[4],counts.v[5],tsc_hz,p);
    for(int i=0;i<6;i++)if(fd[i]>=0)close(fd[i]);
    munmap(data,bytes);return 0;
}
