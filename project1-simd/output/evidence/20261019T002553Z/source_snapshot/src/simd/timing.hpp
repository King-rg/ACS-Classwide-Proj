#pragma once

#include <chrono>
#include <cstddef>
#include <fstream>
#include <string>
#include <vector>

struct TimingOptions {
    std::string csv_path = "output/timings.csv";
    std::size_t trials = 7;
    std::size_t warmups = 2;
    std::size_t offset = 0;
    std::vector<std::size_t> sizes = {19, 4099, 262147, 1048579};
    bool check_only = false;
    bool help = false;
};

TimingOptions parse_options(int argc, char** argv);
void print_usage();

struct TimingRow {
    const char* kernel;
    const char* implementation;
    const char* datatype;
    std::size_t n;
    const void* x;
    const void* y;
    const void* output; // nullptr for dot product's scalar return value.
    std::string coefficient; // Empty for kernels without a coefficient.
    std::size_t trial;
    double elapsed_ns;
    long double checksum;
};

class TimingCsv {
public:
    explicit TimingCsv(const TimingOptions& options);
    void write(const TimingRow& row);
    void finish();
    std::size_t rows() const { return rows_; }
private:
    const TimingOptions& options_;
    std::ofstream file_;
    std::size_t rows_ = 0;
};

// The callback contains only one kernel call. Setup and validation belong outside.
template<class Call>
double elapsed_nanoseconds(Call call) {
    const auto start = std::chrono::steady_clock::now();
    call();
    const auto end = std::chrono::steady_clock::now();
    return std::chrono::duration<double, std::nano>(end - start).count();
}
