#ifndef BENCHMARK_H
#define BENCHMARK_H

#include "kernels.h"
#include <float.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define GUARD (-12345)

typedef struct {
    const char *csv_path;
    size_t trials, warmups, offset, sizes[64], size_count;
    int help, alignment;
    size_t calls;
} Options;

Options parse_options(int argc, char **argv, const char *default_csv);
void print_usage(const char *program);
void fail(const char *message);
void *allocate(size_t count, size_t element_size);
uint64_t now_ns(void);
double random_value(uint32_t *state);
double input_value(uint32_t *state, const Options *options);
void check_close(long double actual, long double expected, long double tolerance);
FILE *open_csv(const char *path);
void write_row(FILE *csv, const Options *options, const char *kernel,
               const char *type, int simd, size_t n, size_t trial,
               const void *x, const void *y, const void *output,
               double elapsed, long double checksum);
void close_csv(FILE *csv, const Options *options);

#endif
