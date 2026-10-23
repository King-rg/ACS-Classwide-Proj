#include "timing.hpp"

#include <cmath>
#include <cstdint>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <locale>
#include <stdexcept>

#ifndef SIMD_BUILD_MODE
#define SIMD_BUILD_MODE "unknown"
#endif

namespace {
std::size_t integer_option(const std::string& value, std::size_t minimum,
                           std::size_t maximum) {
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos) {
        throw std::runtime_error("Expected an unsigned integer: " + value);
    }
    const auto number = std::stoull(value);
    if (number < minimum || number > maximum) {
        throw std::runtime_error("Option out of range: " + value);
    }
    return static_cast<std::size_t>(number);
}

std::string csv_quote(const std::string& text) {
    std::string result = "\"";
    for (char c : text) {
        result += c;
        if (c == '"') result += '"';
    }
    return result + '"';
}

std::size_t alignment_mod32(const void* pointer) {
    return reinterpret_cast<std::uintptr_t>(pointer) % 32;
}
} // namespace

TimingOptions parse_options(int argc, char** argv) {
    TimingOptions options;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--help") { options.help = true; continue; }
        if (arg == "--check-only") { options.check_only = true; continue; }
        if (arg != "--csv" && arg != "--trials" && arg != "--warmups"
            && arg != "--sizes" && arg != "--offset") {
            throw std::runtime_error("Unknown option: " + arg);
        }
        if (++i == argc) throw std::runtime_error("Missing value for " + arg);
        const std::string value = argv[i];
        if (arg == "--csv") options.csv_path = value;
        if (arg == "--trials") options.trials = integer_option(value, 1, 10000);
        if (arg == "--warmups") options.warmups = integer_option(value, 0, 10000);
        if (arg == "--offset") options.offset = integer_option(value, 0, 1);
        if (arg == "--sizes") {
            options.sizes.clear();
            std::size_t start = 0;
            do {
                const auto end = value.find(',', start);
                options.sizes.push_back(integer_option(value.substr(start, end - start), 1, 4194304));
                if (end == std::string::npos) break;
                start = end + 1;
            } while (true);
            if (options.sizes.size() > 64) throw std::runtime_error("At most 64 timing sizes allowed");
        }
    }
    return options;
}

void print_usage() {
    std::cout << "Usage: simd_starter [--check-only] [--csv PATH] [--trials N]\n"
              << "       [--warmups N] [--sizes N,N,...] [--offset 0|1]\n"
              << "Defaults: output/timings.csv, 7 trials, 2 warmups, offset 0,\n"
              << "          sizes 19,4099,262147,1048579.\n";
}

TimingCsv::TimingCsv(const TimingOptions& options) : options_(options) {
    const std::filesystem::path path(options.csv_path);
    if (path.has_parent_path()) std::filesystem::create_directories(path.parent_path());
    file_.exceptions(std::ios::failbit | std::ios::badbit);
    file_.open(path); // Explicitly replace the requested output file.
    file_.imbue(std::locale::classic());
    file_ << std::setprecision(21)
          << "kernel,implementation,datatype,n,stride,offset_elements,x_mod32,y_mod32,output_mod32,"
             "coefficient,trial,warmups,calls,elapsed_ns,checksum,correct,seed,build_mode,compiler\n";
}

void TimingCsv::write(const TimingRow& row) {
    if (!std::isfinite(row.elapsed_ns) || row.elapsed_ns <= 0 || !std::isfinite(row.checksum)) {
        throw std::runtime_error("Invalid timing/checksum; try a larger size (no row written)");
    }
    file_ << row.kernel << ',' << row.implementation << ',' << row.datatype << ',' << row.n
          << ",1," << options_.offset << ',' << alignment_mod32(row.x) << ','
          << alignment_mod32(row.y) << ',';
    if (row.output) file_ << alignment_mod32(row.output);
    file_ << ',' << row.coefficient << ',' << row.trial << ',' << options_.warmups
          << ",1," << row.elapsed_ns << ',' << row.checksum << ",pass,4320,"
          << csv_quote(SIMD_BUILD_MODE) << ',' << csv_quote(__VERSION__) << '\n';
    ++rows_;
}

void TimingCsv::finish() {
    file_.flush();
    file_.close();
}
