#ifndef CYCLE_COUNTER_H
#define CYCLE_COUNTER_H
#include <linux/perf_event.h>
#include <sys/syscall.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
static int cycle_fd=-1;
static uint64_t cycle_value;
static void cycle_start(void){
 if(cycle_fd<0){struct perf_event_attr a={0};a.type=PERF_TYPE_HARDWARE;a.size=sizeof a;a.config=PERF_COUNT_HW_CPU_CYCLES;a.disabled=1;a.exclude_kernel=1;a.exclude_hv=1;a.pinned=1;a.read_format=PERF_FORMAT_TOTAL_TIME_ENABLED|PERF_FORMAT_TOTAL_TIME_RUNNING;
 cycle_fd=syscall(__NR_perf_event_open,&a,0,-1,-1,0);if(cycle_fd<0){perror("perf_event_open");exit(2);}}
 if(ioctl(cycle_fd,PERF_EVENT_IOC_RESET,0)||ioctl(cycle_fd,PERF_EVENT_IOC_ENABLE,0)){perror("enable counter");exit(2);}
}
static void cycle_stop(void){
 struct {uint64_t value,enabled,running;} r;
 if(ioctl(cycle_fd,PERF_EVENT_IOC_DISABLE,0)||read(cycle_fd,&r,sizeof r)!=sizeof r){perror("read counter");exit(2);}
 if(!r.running||r.running!=r.enabled){fprintf(stderr,"Counter not continuously scheduled\n");exit(2);}cycle_value=r.value;
}
#endif
