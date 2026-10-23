#define _GNU_SOURCE
#include "/home/dandisk/ACS-Classwide-Proj/experiments/cycles/counter.h"
#include <time.h>
int main(void){struct timespec t;for(int i=0;i<25;i++){cycle_start();clock_gettime(CLOCK_MONOTONIC,&t);clock_gettime(CLOCK_MONOTONIC,&t);cycle_stop();printf("%llu\n",(unsigned long long)cycle_value);}return 0;}
