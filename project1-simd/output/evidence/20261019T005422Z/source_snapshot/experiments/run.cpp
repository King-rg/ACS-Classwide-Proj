#include "kernels.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>
#include <sched.h>
#include <x86intrin.h>
#include <cpuid.h>
#include <thread>
#include <linux/perf_event.h>
#include <sys/ioctl.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <cerrno>
#include <cstring>

using Clock=std::chrono::steady_clock;
struct Case { std::string kernel,type,study; std::size_t n,stride,offset; };
constexpr std::size_t seed=4320;
constexpr int trials=5, warmups=2;
constexpr double coefficient=1.25;

void require(bool ok,const std::string& message) { if(!ok) throw std::runtime_error(message); }

// 64-byte aligned allocation; sentinels cover gaps, shifted prefixes and tails.
template<class T> struct Array {
    T* p=nullptr; std::size_t length;
    explicit Array(std::size_t size):length(size) {
        require(posix_memalign(reinterpret_cast<void**>(&p),64,size*sizeof(T))==0,"allocation failed");
        std::fill(p,p+size,T(-12345));
    }
    ~Array(){std::free(p);}
    Array(const Array&)=delete;
    Array& operator=(const Array&)=delete;
};

// Reproducible index-based pseudo-random finite data; no extra reference array.
// Different independent salts distinguish x and initial y. Reset is outside timing.
template<class T> T value(std::size_t i,std::uint64_t salt) {
    std::uint64_t z=i+salt+0x9e3779b97f4a7c15ULL;
    z=(z^(z>>30))*0xbf58476d1ce4e5b9ULL;
    z=(z^(z>>27))*0x94d049bb133111ebULL; z^=z>>31;
    return T(static_cast<int>(z%2049)-1024)/T(1000);
}
template<class T> void initialize(Array<T>& x,Array<T>& y,const Case& c) {
    for(std::size_t i=0;i<c.n;++i){x.p[c.offset+i*c.stride]=value<T>(i,seed);y.p[c.offset+i*c.stride]=value<T>(i,seed+1);}
}
template<class T> void reset_y(Array<T>& y,const Case& c) {
    for(std::size_t i=0;i<c.n;++i) y.p[c.offset+i*c.stride]=value<T>(i,seed+1);
}
long read_frequency() {
    long khz=0; std::ifstream f("/sys/devices/system/cpu/cpu"+std::to_string(sched_getcpu())+"/cpufreq/scaling_cur_freq"); f>>khz; return khz;
}
// Explicit P-core PMU avoids mixing E-core and P-core hybrid counters.
struct CounterValues { std::uint64_t cycles=0,instructions=0,cache_misses=0,enabled=0,running=0; };
class CounterGroup {
    int fd=-1, instructions=-1, misses=-1;
    int open_event(std::uint64_t event,int group) {
        perf_event_attr attr{};attr.size=sizeof(attr);attr.type=4; // cpu_core/type, checked by launcher.
        attr.config=event;attr.disabled=group==-1;attr.exclude_kernel=1;attr.exclude_hv=1;
        attr.read_format=PERF_FORMAT_GROUP|PERF_FORMAT_TOTAL_TIME_ENABLED|PERF_FORMAT_TOTAL_TIME_RUNNING;
        const int result=static_cast<int>(syscall(__NR_perf_event_open,&attr,0,-1,group,0));
        require(result>=0,std::string("perf_event_open: ")+std::strerror(errno));return result;
    }
public:
    CounterGroup(){fd=open_event(0x3c,-1);instructions=open_event(0xc0,fd);misses=open_event(0x412e,fd);}
    ~CounterGroup(){if(misses>=0)close(misses);if(instructions>=0)close(instructions);if(fd>=0)close(fd);}
    void start(){require(ioctl(fd,PERF_EVENT_IOC_RESET,PERF_IOC_FLAG_GROUP)==0,"counter reset");require(ioctl(fd,PERF_EVENT_IOC_ENABLE,PERF_IOC_FLAG_GROUP)==0,"counter enable");}
    CounterValues stop(){
        require(ioctl(fd,PERF_EVENT_IOC_DISABLE,PERF_IOC_FLAG_GROUP)==0,"counter disable");
        struct {std::uint64_t nr,enabled,running,values[3];} data{};
        require(::read(fd,&data,sizeof(data))==sizeof(data)&&data.nr==3,"counter read");
        require(data.running>0 && static_cast<double>(data.running)/data.enabled>.95,"counter multiplexing/inactive group");
        return {data.values[0],data.values[1],data.values[2],data.enabled,data.running};
    }
};
struct Measurement { double ns; std::uint64_t tsc; unsigned aux_start,aux_end; int cpu_start,cpu_end; long khz_start,khz_end; CounterValues counters; };
template<class Call> Measurement measure(Call call,std::size_t calls) {
    static CounterGroup counters;
    Measurement m{}; m.khz_start=read_frequency();m.cpu_start=sched_getcpu();
    counters.start();
    unsigned tag; _mm_lfence(); const auto start_tsc=__rdtscp(&tag);m.aux_start=tag;_mm_lfence();
    const auto start=Clock::now();
    for(std::size_t i=0;i<calls;++i) call();
    const auto end=Clock::now();_mm_lfence();const auto end_tsc=__rdtscp(&tag);m.aux_end=tag;_mm_lfence();
    m.counters=counters.stop();
    m.ns=std::chrono::duration<double,std::nano>(end-start).count();m.tsc=end_tsc-start_tsc;
    m.cpu_end=sched_getcpu();m.khz_end=read_frequency();
    require(m.ns>0 && m.tsc>0,"invalid clock sample");
    require(m.cpu_start==m.cpu_end && m.aux_start==m.aux_end,"migration detected");return m;
}
template<class Call> std::size_t batch_count(Call call) {
    const auto pilot=measure(call,1);
    return std::clamp<std::size_t>(static_cast<std::size_t>(std::ceil(2000000.0/pilot.ns)),1,65536);
}

// A bound for moderate finite test values, not a guarantee for arbitrary inputs.
long double bound(std::size_t operations,long double absolute_sum,long double eps) {
    const long double e=operations*eps;
    if(e>=0.9L) return 2*std::expm1(e)*absolute_sum+16*eps;
    return 2*e/(1-e)*absolute_sum+16*eps;
}
template<class T> long double check_result(T got,long double expected,long double tolerance) {
    const long double error=std::abs(static_cast<long double>(got)-expected);
    require(std::isfinite(got)&&error<=tolerance,"independent reference mismatch");return error;
}
template<class T> void check_inputs(const Array<T>& x,const Array<T>& y,const Case& c,bool y_changes) {
    for(std::size_t j=0;j<x.length;++j) {
        const bool used=j>=c.offset && (j-c.offset)%c.stride==0 && (j-c.offset)/c.stride<c.n;
        if(used){
            const auto i=(j-c.offset)/c.stride;
            require(x.p[j]==value<T>(i,seed),"x modified");
            if(!y_changes) require(y.p[j]==value<T>(i,seed+1),"y modified");
        } else require(x.p[j]==T(-12345)&&y.p[j]==T(-12345),"input/padding modified");
    }
}
template<class T> void check_output_padding(const Array<T>& z,const Case& c) {
    for(std::size_t j=0;j<z.length;++j) {
        const bool used=j>=c.offset && (j-c.offset)%c.stride==0 && (j-c.offset)/c.stride<c.n;
        if(!used) require(z.p[j]==T(-12345),"output/padding modified");
    }
}

void csv_row(std::ofstream& out,const Case& c,const std::string& runid,int repeat,int trial,
             const char* implementation,std::size_t calls,const Measurement& m,const void* x,const void* y,
             const void* z,std::size_t footprint,long double checksum,long double error) {
    auto residue=[](const void* p){return reinterpret_cast<std::uintptr_t>(p)%64;};
    out<<runid<<','<<repeat<<','<<c.study<<','<<c.kernel<<','<<c.type<<','<<implementation<<','
       <<c.n<<','<<c.stride<<','<<c.offset<<','<<residue(x)<<','<<residue(y)<<',';
    if(z)out<<residue(z);
    out<<','<<footprint<<','<<(c.kernel=="axpy"?"1.25":"")<<','<<trial<<','<<warmups<<','<<calls<<','
       <<m.ns<<','<<m.tsc<<','<<m.cpu_start<<','<<m.cpu_end<<','<<m.aux_start<<','<<m.aux_end<<','
       <<m.khz_start<<','<<m.khz_end<<','<<m.counters.cycles<<','<<m.counters.instructions<<','<<m.counters.cache_misses<<','<<m.counters.enabled<<','<<m.counters.running<<','<<checksum<<','<<error<<",pass,4320\n";
}

// Typed selectors keep each kernel's distinct interface visible.
template<class T> using Axpy=void(*)(T,const T*,T*,std::size_t,std::size_t);
template<class T> using Dot=T(*)(const T*,const T*,std::size_t,std::size_t);
template<class T> using Multiply=void(*)(const T*,const T*,T*,std::size_t,std::size_t);
template<class T> Axpy<T> axpy_function(int variant);
template<class T> Dot<T> dot_function(int variant);
template<class T> Multiply<T> multiply_function(int variant);
#define SELECT(T,S) \
template<> Axpy<T> axpy_function<T>(int v){return v==0?evidence::axpy_scalar_##S:v==1?evidence::axpy_auto_##S:evidence::axpy_simd_##S;} \
template<> Dot<T> dot_function<T>(int v){return v==0?evidence::dot_scalar_##S:v==1?evidence::dot_auto_##S:evidence::dot_simd_##S;} \
template<> Multiply<T> multiply_function<T>(int v){return v==0?evidence::multiply_scalar_##S:v==1?evidence::multiply_auto_##S:evidence::multiply_simd_##S;}
SELECT(float,f32) SELECT(double,f64)
#undef SELECT
const char* names[]={"scalar","auto","simd"};

template<class T> void run_axpy(const Case& c,std::ofstream& out,const std::string& runid,int repeat,T a) {
    Array<T>x(c.n*c.stride+c.offset+8),y(x.length);initialize(x,y,c);
    const auto calls=batch_count([&]{axpy_function<T>(0)(a,x.p+c.offset,y.p+c.offset,c.n,c.stride);});
    for(int trial=0;trial<trials;++trial) for(int position=0;position<3;++position) {
        const int variant=(trial+position+repeat)%3; const auto fn=axpy_function<T>(variant);
        for(int w=0;w<warmups;++w){reset_y(y,c);for(std::size_t k=0;k<calls;++k)fn(a,x.p+c.offset,y.p+c.offset,c.n,c.stride);}
        reset_y(y,c);
        auto m=measure([&]{fn(a,x.p+c.offset,y.p+c.offset,c.n,c.stride);},calls);
        long double sum=0,error=0;
        for(std::size_t i=0;i<c.n;++i){const auto j=c.offset+i*c.stride;
            const long double product=static_cast<long double>(a)*x.p[j], initial=value<T>(i,seed+1);
            const long double expected=initial+calls*product;
            const auto tolerance=bound(calls+1,std::abs(initial)+calls*std::abs(product),std::numeric_limits<T>::epsilon());
            error=std::max(error,check_result(y.p[j],expected,tolerance));sum+=y.p[j];}
        check_inputs(x,y,c,true);
        csv_row(out,c,runid,repeat,trial,names[variant],calls,m,x.p+c.offset,y.p+c.offset,y.p+c.offset,
                2*c.n*c.stride*sizeof(T),sum,error);
    }
}
template<class T> void run_dot(const Case& c,std::ofstream& out,const std::string& runid,int repeat) {
    Array<T>x(c.n*c.stride+c.offset+8),y(x.length);initialize(x,y,c);
    long double expected=0,absolute=0;
    for(std::size_t i=0;i<c.n;++i){const auto j=c.offset+i*c.stride;const auto product=static_cast<long double>(x.p[j])*y.p[j];expected+=product;absolute+=std::abs(product);}
    // In addition to a conservative rounding bound, impose a tighter finite-data
    // acceptance limit against the independent long-double oracle.
    auto tolerance=std::min(bound(c.n+1,absolute,std::numeric_limits<T>::epsilon()),
        0.0001L*std::max(1.0L,std::abs(expected))+0.1L);T result=0;
    const auto calls=batch_count([&]{result=dot_function<T>(0)(x.p+c.offset,y.p+c.offset,c.n,c.stride);});
    for(int trial=0;trial<trials;++trial) for(int position=0;position<3;++position) {
        const int variant=(trial+position+repeat)%3;const auto fn=dot_function<T>(variant);
        for(int w=0;w<warmups;++w)for(std::size_t k=0;k<calls;++k)result=fn(x.p+c.offset,y.p+c.offset,c.n,c.stride);
        auto m=measure([&]{result=fn(x.p+c.offset,y.p+c.offset,c.n,c.stride);},calls);
        const auto error=check_result(result,expected,tolerance);check_inputs(x,y,c,false);
        csv_row(out,c,runid,repeat,trial,names[variant],calls,m,x.p+c.offset,y.p+c.offset,nullptr,
                2*c.n*c.stride*sizeof(T),result,error);
    }
}
template<class T> void run_multiply(const Case& c,std::ofstream& out,const std::string& runid,int repeat) {
    Array<T>x(c.n*c.stride+c.offset+8),y(x.length),z(x.length);initialize(x,y,c);
    const auto calls=batch_count([&]{multiply_function<T>(0)(x.p+c.offset,y.p+c.offset,z.p+c.offset,c.n,c.stride);});
    for(int trial=0;trial<trials;++trial) for(int position=0;position<3;++position) {
        const int variant=(trial+position+repeat)%3;const auto fn=multiply_function<T>(variant);
        for(int w=0;w<warmups;++w)for(std::size_t k=0;k<calls;++k)fn(x.p+c.offset,y.p+c.offset,z.p+c.offset,c.n,c.stride);
        auto m=measure([&]{fn(x.p+c.offset,y.p+c.offset,z.p+c.offset,c.n,c.stride);},calls);
        long double sum=0,error=0;
        for(std::size_t i=0;i<c.n;++i){const auto j=c.offset+i*c.stride;const auto expected=static_cast<long double>(x.p[j])*y.p[j];
            error=std::max(error,check_result(z.p[j],expected,8*std::numeric_limits<T>::epsilon()*std::max(1.0L,std::abs(expected))));sum+=z.p[j];}
        check_inputs(x,y,c,false);check_output_padding(z,c);
        csv_row(out,c,runid,repeat,trial,names[variant],calls,m,x.p+c.offset,y.p+c.offset,z.p+c.offset,
                3*c.n*c.stride*sizeof(T),sum,error);
    }
}

template<class T> void check_functions() {
    for(auto n:{0u,1u,2u,3u,4u,7u,8u,9u,16u,19u})
    for(auto stride:{1u,2u,4u,8u})for(auto offset:{0u,1u})for(int v=0;v<3;++v) {
        Case c{"check","check","correctness",n,stride,offset};
        Array<T>x(n*stride+offset+8),y(x.length),z(x.length);initialize(x,y,c);
        long double expected_dot=0,absolute=0;
        for(std::size_t i=0;i<n;++i){const auto j=offset+i*stride;const auto p=static_cast<long double>(x.p[j])*y.p[j];expected_dot+=p;absolute+=std::abs(p);}
        auto dot=dot_function<T>(v)(x.p+offset,y.p+offset,n,stride);
        check_result(dot,expected_dot,bound(n+1,absolute,std::numeric_limits<T>::epsilon()));
        multiply_function<T>(v)(x.p+offset,y.p+offset,z.p+offset,n,stride);
        for(std::size_t i=0;i<n;++i){const auto j=offset+i*stride;check_result(z.p[j],static_cast<long double>(x.p[j])*y.p[j],8*std::numeric_limits<T>::epsilon());}
        check_inputs(x,y,c,false);check_output_padding(z,c);
        axpy_function<T>(v)(T(1.25),x.p+offset,y.p+offset,n,stride);
        for(std::size_t i=0;i<n;++i){const auto j=offset+i*stride;check_result(y.p[j],1.25L*x.p[j]+value<T>(i,seed+1),8*std::numeric_limits<T>::epsilon());}
        check_inputs(x,y,c,true);
    }
    // Independently known arithmetic fixture, including a reduction.
    T x[]={1,-2,3},initial[]={4,5,-6},y[3],z[3];
    for(int v=0;v<3;++v){std::copy(initial,initial+3,y);
        axpy_function<T>(v)(T(1.25),x,y,3,1);require(y[0]==T(5.25)&&y[1]==T(2.5)&&y[2]==T(-2.25),"AXPY known fixture");
        require(dot_function<T>(v)(x,initial,3,1)==T(-24),"dot known fixture");
        multiply_function<T>(v)(x,initial,z,3,1);require(z[0]==4&&z[1]==-10&&z[2]==-18,"multiply known fixture");
    }
}

void calibrate(const std::string& directory) {
    std::ofstream out(directory+"/calibration.csv");out<<std::setprecision(18)<<"kind,trial,n,calls,elapsed_ns,tsc_ticks,work,work_unit,checksum\n";
    // 96 MiB active triad / 64 MiB active cached-copy footprint, beyond LLC.
    const std::size_t n=4*1024*1024;Array<double>x(n),y(n),z(n);
    for(std::size_t i=0;i<n;++i){x.p[i]=value<double>(i,seed);y.p[i]=value<double>(i,seed+1);}
    for(int kind=0;kind<2;++kind){
        auto call=[&]{if(kind==0)evidence::stream_triad(x.p,y.p,z.p,n);else evidence::cached_copy(x.p,z.p,n);};
        call();call();
        for(int t=0;t<7;++t){auto m=measure(call,4);long double sum=0;
            for(std::size_t i=0;i<n;++i){check_result(z.p[i],kind==0?x.p[i]+y.p[i]:x.p[i],0);sum+=z.p[i];}
            out<<(kind==0?"nt_triad":"cached_copy")<<','<<t<<','<<n<<",4,"<<m.ns<<','<<m.tsc<<','
               <<4*n*sizeof(double)*(kind==0?3:2)<<",logical_bytes,"<<sum<<'\n';}
    }
    const std::size_t iterations=2000000;
    for(int kind=0;kind<2;++kind){
        long double result=0;auto call=[&]{result=kind==0?evidence::compute_f32(iterations):evidence::compute_f64(iterations);};
        call();call();
        for(int t=0;t<7;++t){auto m=measure(call,1);require(std::isfinite(result),"compute calibration invalid");
            out<<(kind==0?"fma_f32":"fma_f64")<<','<<t<<','<<iterations<<",1,"<<m.ns<<','<<m.tsc<<','
               <<iterations*8*(kind==0?8:4)*2<<",flops,"<<result<<'\n';}
    }
    // Frequency from CPUID leaf 0x15 where supplied, with wall-clock cross-check.
    unsigned a,b,c,d; __cpuid_count(0x15,0,a,b,c,d);
    const double hz=a&&b&&c?static_cast<double>(c)*b/a:0;
    std::ofstream tsc(directory+"/tsc.json");tsc<<std::setprecision(18)<<"{\"cpuid_tsc_hz\":"<<hz<<",\"wall_calibration_hz\":[";
    for(int i=0;i<3;++i){auto m=measure([]{std::this_thread::sleep_for(std::chrono::milliseconds(100));},1);if(i)tsc<<',';tsc<<m.tsc/m.ns*1e9;}
    unsigned ca,cb,cc,cd;__cpuid_count(0x1a,0,ca,cb,cc,cd);
    tsc<<"],\"cpuid_core_type\":"<<(ca>>24)<<",\"unit\":\"invariant reference TSC ticks; NOT core cycles\"}\n";
}

int main(int argc,char**argv) {
    try {
        require(argc==6,"Usage: runner CASES OUTPUT_DIRECTORY RUN_ID REPEAT CPU");
        const int cpu=std::stoi(argv[5]);cpu_set_t mask;CPU_ZERO(&mask);CPU_SET(cpu,&mask);
        require(sched_setaffinity(0,sizeof(mask),&mask)==0,"pinning failed");require(sched_getcpu()==cpu,"wrong CPU");
        std::ifstream input(argv[1]);require(bool(input),"cases file missing");std::vector<Case> cases;Case c;
        while(input>>c.kernel>>c.type>>c.study>>c.n>>c.stride>>c.offset){
            require(c.n>0 && c.stride<=8 && c.stride>=1 && c.offset<=1,"invalid case");cases.push_back(c);}
        require(!cases.empty(),"no cases");
        std::ofstream out(std::string(argv[2])+"/raw.csv");out.exceptions(std::ios::badbit|std::ios::failbit);out<<std::setprecision(18);
        out<<"run_id,repeat,study,kernel,datatype,implementation,n,stride,offset_elements,x_mod64,y_mod64,output_mod64,footprint_bytes,coefficient,trial,warmups,calls,elapsed_ns,tsc_ticks,cpu_start,cpu_end,aux_start,aux_end,khz_start,khz_end,core_cycles,user_instructions,llc_misses,perf_enabled_ns,perf_running_ns,checksum,max_abs_error,correct,seed\n";
        const int repeat=std::stoi(argv[4]);
        check_functions<float>();check_functions<double>();
        std::cout<<"480 new-variant cases plus known fixtures: PASS\n";
        std::cout<<"AXPY configurations\n"<<std::flush;
        for(const auto& item:cases)if(item.kernel=="axpy"){
            if(item.type=="float")run_axpy<float>(item,out,argv[3],repeat,static_cast<float>(coefficient));
            else run_axpy<double>(item,out,argv[3],repeat,coefficient);}
        std::cout<<"Dot-product configurations\n"<<std::flush;
        for(const auto& item:cases)if(item.kernel=="dot"){
            if(item.type=="float")run_dot<float>(item,out,argv[3],repeat);
            else run_dot<double>(item,out,argv[3],repeat);}
        std::cout<<"Multiply configurations\n"<<std::flush;
        for(const auto& item:cases)if(item.kernel=="multiply"){
            if(item.type=="float")run_multiply<float>(item,out,argv[3],repeat);
            else run_multiply<double>(item,out,argv[3],repeat);}
        calibrate(argv[2]);out.close();std::cout<<"Completed "<<cases.size()<<" configurations; CPU "<<sched_getcpu()<<"\n";
    } catch(const std::exception& error){std::cerr<<"FAIL: "<<error.what()<<'\n';return 1;}
}
