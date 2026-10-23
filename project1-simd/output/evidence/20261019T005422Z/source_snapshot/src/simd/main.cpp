#include "saxpy.hpp"
#include "dot_product.hpp"
#include "elementwise_multiply.hpp"
#include "timing.hpp"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

template<class T>
constexpr T guard_value = T(-12345);

template<class T>
using Axpy = void (*)(T, const T*, T*, std::size_t);
template<class T>
using Dot = T (*)(const T*, const T*, std::size_t);
template<class T>
using Multiply = void (*)(const T*, const T*, T*, std::size_t);

template<class T>
struct Inputs {
    std::size_t n;
    std::size_t offset;
    std::vector<T> x;
    std::vector<T> y;
};

void require(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

template<class T>
Inputs<T> make_inputs(std::size_t n, std::size_t offset, std::mt19937& random, bool known_fixture = true) {
    Inputs<T> inputs{n, offset, std::vector<T>(n + offset + 1, guard_value<T>),
                              std::vector<T>(n + offset + 1, guard_value<T>)};
    // Map seeded generator output directly to moderate decimal fractions.
    // Consume x then y in the same order for each element.
    for (std::size_t i = 0; i < n; ++i) {
        inputs.x[offset + i] = T(static_cast<int>(random() % 2049u) - 1024) / T(1000);
        inputs.y[offset + i] = T(static_cast<int>(random() % 2049u) - 1024) / T(1000);
    }
    // Keep consuming the same random sequence even for this known fixture.
    if (known_fixture && n == 3) {
        inputs.x[offset] = 1; inputs.x[offset + 1] = -2; inputs.x[offset + 2] = 3;
        inputs.y[offset] = 4; inputs.y[offset + 1] = 5; inputs.y[offset + 2] = -6;
    }
    return inputs;
}

template<class T>
void check_close(T got, long double expected, long double tolerance, const std::string& context) {
    require(std::isfinite(got) && std::abs(static_cast<long double>(got) - expected) <= tolerance,
            "Numerical mismatch: " + context);
}

template<class T>
void validate_elements(const std::vector<T>& actual, const std::vector<long double>& expected,
                       std::size_t offset, const std::string& context) {
    const long double eps = std::numeric_limits<T>::epsilon();
    for (std::size_t i = 0; i < expected.size(); ++i) {
        const long double tolerance = 8 * eps * std::max(1.0L, std::abs(expected[i]));
        check_close(actual[offset + i], expected[i], tolerance,
                    context + " i=" + std::to_string(i));
    }
}

template<class T>
long double checksum(const std::vector<T>& values, std::size_t offset, std::size_t n) {
    long double sum = 0;
    for (std::size_t i = 0; i < n; ++i) {
        sum += values[offset + i];
    }
    return sum;
}

std::string case_description(const char* kernel, const char* type,
                             std::size_t n, std::size_t offset) {
    return std::string(kernel) + " " + type + " n=" + std::to_string(n)
           + " offset=" + std::to_string(offset);
}

template<class T>
void check_inputs_unchanged(const Inputs<T>& inputs, const Inputs<T>& original,
                            const std::string& context) {
    require(inputs.x == original.x && inputs.y == original.y, "Input modified: " + context);
}

template<class T>
void check_output_guards(const std::vector<T>& output, std::size_t offset,
                         const std::string& context) {
    require(output.back() == guard_value<T> && (offset == 0 || output.front() == guard_value<T>),
            "Output guard modified: " + context);
}

template<class T>
std::vector<T> exact_input(const std::vector<T>& values, std::size_t offset, std::size_t n) {
    // No trailing guard: ASan can detect a SIMD read beyond the logical end.
    return std::vector<T>(values.begin() + offset, values.begin() + offset + n);
}

template<class T>
std::vector<long double> expected_axpy(const Inputs<T>& inputs, T a) {
    std::vector<long double> expected;
    for (std::size_t i = 0; i < inputs.n; ++i) {
        expected.push_back(static_cast<long double>(a) * inputs.x[inputs.offset + i]
                           + inputs.y[inputs.offset + i]);
    }
    return expected;
}

template<class T>
std::vector<long double> expected_products(const Inputs<T>& inputs) {
    std::vector<long double> expected;
    for (std::size_t i = 0; i < inputs.n; ++i) {
        expected.push_back(static_cast<long double>(inputs.x[inputs.offset + i])
                           * inputs.y[inputs.offset + i]);
    }
    return expected;
}

template<class T>
void check_known_axpy(const std::vector<T>& output, std::size_t offset, T a,
                      const std::string& context) {
    // Independently hand-computed fixture for the coefficient selected in main.
    if (a == T(1.25)) {
        require(output[offset] == T(5.25) && output[offset+1] == T(2.5)
                && output[offset+2] == T(-2.25), "Known AXPY failed: " + context);
    }
}

template<class T>
void check_known_multiply(const std::vector<T>& output, std::size_t offset,
                          const std::string& context) {
    require(output[offset] == T(4) && output[offset+1] == T(-10)
            && output[offset+2] == T(-18), "Known multiply failed: " + context);
}

template<class T>
void check_exact_axpy(const Inputs<T>& inputs, T a, Axpy<T> simd,
                      const std::vector<T>& result, const std::string& context) {
    if (inputs.n == 0) return;
    auto x = exact_input(inputs.x, inputs.offset, inputs.n);
    auto y = exact_input(inputs.y, inputs.offset, inputs.n);
    simd(a, x.data(), y.data(), inputs.n);
    for (std::size_t i = 0; i < inputs.n; ++i) {
        require(y[i] == result[inputs.offset+i], "Exact-size AXPY failed: " + context);
    }
}

template<class T>
void test_axpy_case(const char* type, T a, Axpy<T> scalar, Axpy<T> simd,
                    std::size_t n, std::size_t offset, std::mt19937& random) {
    auto inputs = make_inputs<T>(n, offset, random);
    const auto original = inputs;
    const auto expected = expected_axpy(inputs, a);
    const auto context = case_description("AXPY", type, n, offset);
    auto scalar_output = inputs.y;
    auto simd_output = inputs.y; // Same pristine old y for both calls.
    scalar(a, inputs.x.data() + offset, scalar_output.data() + offset, n);
    simd(a, inputs.x.data() + offset, simd_output.data() + offset, n);
    validate_elements(scalar_output, expected, offset, context + " scalar");
    validate_elements(simd_output, expected, offset, context + " SIMD");
    check_inputs_unchanged(inputs, original, context);
    check_output_guards(scalar_output, offset, context);
    check_output_guards(simd_output, offset, context);
    if (n == 3) {
        check_known_axpy(scalar_output, offset, a, context);
        check_known_axpy(simd_output, offset, a, context);
    }
    check_exact_axpy(inputs, a, simd, simd_output, context);
    if (n == 4099 && offset == 1) {
        std::cout << "AXPY " << type << " scalar/SIMD checksum: "
                  << checksum(scalar_output, offset, n) << " / "
                  << checksum(simd_output, offset, n) << '\n';
    }
}

struct DotReference {
    long double sum;
    long double tolerance;
};

template<class T>
DotReference expected_dot(const Inputs<T>& inputs) {
    long double sum = 0;
    long double sum_abs_products = 0;
    for (std::size_t i = 0; i < inputs.n; ++i) {
        const long double product = static_cast<long double>(inputs.x[inputs.offset+i])
                                    * inputs.y[inputs.offset+i];
        sum += product;
        sum_abs_products += std::abs(product);
    }
    // Forward-error scale includes rounded products/sums and cancellation.
    const long double eps = std::numeric_limits<T>::epsilon();
    const long double neps = (static_cast<long double>(inputs.n) + 1) * eps;
    return {sum, 2 * neps / (1 - neps) * sum_abs_products + eps};
}

template<class T>
void check_exact_dot(const Inputs<T>& inputs, Dot<T> simd, DotReference expected,
                     const std::string& context) {
    if (inputs.n == 0) return;
    auto x = exact_input(inputs.x, inputs.offset, inputs.n);
    auto y = exact_input(inputs.y, inputs.offset, inputs.n);
    check_close(simd(x.data(), y.data(), inputs.n), expected.sum, expected.tolerance,
                context + " exact-size SIMD");
}

template<class T>
void test_dot_case(const char* type, Dot<T> scalar, Dot<T> simd,
                   std::size_t n, std::size_t offset, std::mt19937& random) {
    auto inputs = make_inputs<T>(n, offset, random);
    const auto original = inputs;
    const auto expected = expected_dot(inputs);
    const auto context = case_description("dot product", type, n, offset);
    const T scalar_result = scalar(inputs.x.data()+offset, inputs.y.data()+offset, n);
    const T simd_result = simd(inputs.x.data()+offset, inputs.y.data()+offset, n);
    check_close(scalar_result, expected.sum, expected.tolerance, context + " scalar");
    check_close(simd_result, expected.sum, expected.tolerance, context + " SIMD");
    check_inputs_unchanged(inputs, original, context);
    if (n == 3) {
        require(scalar_result == T(-24) && simd_result == T(-24),
                "Known dot product failed: " + context);
    }
    check_exact_dot(inputs, simd, expected, context);
    if (n == 4099 && offset == 1) {
        std::cout << "dot product " << type << " scalar/SIMD: "
                  << scalar_result << " / " << simd_result << '\n';
    }
}

template<class T>
void check_exact_multiply(const Inputs<T>& inputs, Multiply<T> simd,
                          const std::vector<T>& result, const std::string& context) {
    if (inputs.n == 0) return;
    auto x = exact_input(inputs.x, inputs.offset, inputs.n);
    auto y = exact_input(inputs.y, inputs.offset, inputs.n);
    std::vector<T> z(inputs.n);
    simd(x.data(), y.data(), z.data(), inputs.n);
    for (std::size_t i = 0; i < inputs.n; ++i) {
        require(z[i] == result[inputs.offset+i], "Exact-size multiply failed: " + context);
    }
}

template<class T>
void test_multiply_case(const char* type, Multiply<T> scalar, Multiply<T> simd,
                        std::size_t n, std::size_t offset, std::mt19937& random) {
    auto inputs = make_inputs<T>(n, offset, random);
    const auto original = inputs;
    const auto expected = expected_products(inputs);
    const auto context = case_description("multiply", type, n, offset);
    std::vector<T> scalar_output(inputs.y.size(), guard_value<T>);
    std::vector<T> simd_output(inputs.y.size(), guard_value<T>);
    scalar(inputs.x.data()+offset, inputs.y.data()+offset, scalar_output.data()+offset, n);
    simd(inputs.x.data()+offset, inputs.y.data()+offset, simd_output.data()+offset, n);
    validate_elements(scalar_output, expected, offset, context + " scalar");
    validate_elements(simd_output, expected, offset, context + " SIMD");
    check_inputs_unchanged(inputs, original, context);
    check_output_guards(scalar_output, offset, context);
    check_output_guards(simd_output, offset, context);
    if (n == 3) {
        check_known_multiply(scalar_output, offset, context);
        check_known_multiply(simd_output, offset, context);
    }
    check_exact_multiply(inputs, simd, simd_output, context);
    if (n == 4099 && offset == 1) {
        std::cout << "multiply " << type << " scalar/SIMD checksum: "
                  << checksum(scalar_output, offset, n) << " / "
                  << checksum(simd_output, offset, n) << '\n';
    }
}

// Timing is separate from correctness fixtures. Each measured call is validated
// before its CSV row is written; checks and CSV output are outside the timer.
template<class T>
void time_axpy(const char* type, T a, Axpy<T> scalar, Axpy<T> simd,
               const Inputs<T>& inputs, const TimingOptions& options, TimingCsv& csv) {
    const auto expected = expected_axpy(inputs, a);
    const auto original = inputs;
    auto output = inputs.y;
    const auto n = inputs.n;
    const auto offset = inputs.offset;
    const T* x = inputs.x.data() + offset;
    T* y = output.data() + offset;
    // Alternate which implementation goes first in each trial.
    for (std::size_t trial = 0; trial < options.trials; ++trial) {
        for (int position = 0; position < 2; ++position) {
            const bool vector = (trial + position) % 2 != 0;
            const auto function = vector ? simd : scalar;
            for (std::size_t warmup = 0; warmup < options.warmups; ++warmup) {
                std::copy(inputs.y.begin(), inputs.y.end(), output.begin());
                function(a, x, y, n);
                validate_elements(output, expected, offset, "AXPY warmup");
            }
            // Reset outside timing; every call starts from exactly the same y.
            std::copy(inputs.y.begin(), inputs.y.end(), output.begin());
            const double ns = elapsed_nanoseconds([&] { function(a, x, y, n); });
            validate_elements(output, expected, offset, "AXPY timing");
            check_output_guards(output, offset, "AXPY timing");
            check_inputs_unchanged(inputs, original, "AXPY timing");
            csv.write({"axpy", vector ? "simd" : "scalar", type, n, x,
                       y, y, std::to_string(a), trial, ns,
                       checksum(output, offset, n)});
        }
    }
}

template<class T>
void time_dot(const char* type, Dot<T> scalar, Dot<T> simd, const Inputs<T>& inputs,
              const TimingOptions& options, TimingCsv& csv) {
    const auto expected = expected_dot(inputs);
    const auto original = inputs;
    const auto n = inputs.n;
    const auto offset = inputs.offset;
    const T* x = inputs.x.data() + offset;
    const T* y = inputs.y.data() + offset;
    for (std::size_t trial = 0; trial < options.trials; ++trial) {
        for (int position = 0; position < 2; ++position) {
            const bool vector = (trial + position) % 2 != 0;
            const auto function = vector ? simd : scalar;
            for (std::size_t warmup = 0; warmup < options.warmups; ++warmup) {
                check_close(function(x, y, n), expected.sum, expected.tolerance, "dot warmup");
            }
            T result = 0;
            const double ns = elapsed_nanoseconds([&] { result = function(x, y, n); });
            check_close(result, expected.sum, expected.tolerance, "dot timing");
            check_inputs_unchanged(inputs, original, "dot timing");
            csv.write({"dot", vector ? "simd" : "scalar", type, n, x, y, nullptr,
                       "", trial, ns, static_cast<long double>(result)});
        }
    }
}

template<class T>
void time_multiply(const char* type, Multiply<T> scalar, Multiply<T> simd,
                   const Inputs<T>& inputs, const TimingOptions& options, TimingCsv& csv) {
    const auto expected = expected_products(inputs);
    const auto original = inputs;
    std::vector<T> output(inputs.y.size(), guard_value<T>);
    const auto n = inputs.n;
    const auto offset = inputs.offset;
    const T* x = inputs.x.data() + offset;
    const T* y = inputs.y.data() + offset;
    T* z = output.data() + offset;
    for (std::size_t trial = 0; trial < options.trials; ++trial) {
        for (int position = 0; position < 2; ++position) {
            const bool vector = (trial + position) % 2 != 0;
            const auto function = vector ? simd : scalar;
            for (std::size_t warmup = 0; warmup < options.warmups; ++warmup) {
                function(x, y, z, n);
                validate_elements(output, expected, offset, "multiply warmup");
            }
            const double ns = elapsed_nanoseconds([&] { function(x, y, z, n); });
            validate_elements(output, expected, offset, "multiply timing");
            check_output_guards(output, offset, "multiply timing");
            check_inputs_unchanged(inputs, original, "multiply timing");
            csv.write({"multiply", vector ? "simd" : "scalar", type, n, x, y, z,
                       "", trial, ns, checksum(output, offset, n)});
        }
    }
}

} // namespace

int main(int argc, char** argv) {
    using namespace simd_project;
    std::cout << std::setprecision(12);
    try {
        const auto options = parse_options(argc, argv);
        if (options.help) { print_usage(); return 0; }
        const std::size_t lengths[] = {0, 1, 2, 3, 4, 7, 8, 9, 15, 16, 17, 19, 4099};
        const std::size_t offsets[] = {0, 1};
        
        const float saxpy_coefficient = 1.25f;
        const double daxpy_coefficient = 1.25;

        // AXPY: coefficient + read-only x + initialized mutable y.
        std::cout << "AXPY tests\n";
        std::mt19937 axpy_float_random(4320), axpy_double_random(4320);
        std::size_t axpy_cases = 0;
        for (std::size_t n : lengths) {
            for (std::size_t offset : offsets) {
                test_axpy_case<float>("float", saxpy_coefficient, saxpy_scalar, saxpy_simd,
                                      n, offset, axpy_float_random);
                test_axpy_case<double>("double", daxpy_coefficient, daxpy_scalar, daxpy_simd,
                                       n, offset, axpy_double_random);
                ++axpy_cases;
            }
        }
        std::cout << "AXPY: PASS (" << axpy_cases << " cases per type, float/double scalar/SIMD)\n";

        // Dot product: two read-only arrays, one scalar result; no coefficient.
        std::cout << "Dot product tests\n";
        std::mt19937 dot_float_random(4320), dot_double_random(4320);
        std::size_t dot_cases = 0;
        for (std::size_t n : lengths) {
            for (std::size_t offset : offsets) {
                test_dot_case<float>("float", dot_float_scalar, dot_float_simd,
                                     n, offset, dot_float_random);
                test_dot_case<double>("double", dot_double_scalar, dot_double_simd,
                                      n, offset, dot_double_random);
                ++dot_cases;
            }
        }
        std::cout << "Dot product: PASS (" << dot_cases << " cases per type, float/double scalar/SIMD)\n";

        // Elementwise multiply: two read-only arrays, a separate output array.
        std::cout << "Elementwise multiply tests\n";
        std::mt19937 multiply_float_random(4320), multiply_double_random(4320);
        std::size_t multiply_cases = 0;
        for (std::size_t n : lengths) {
            for (std::size_t offset : offsets) {
                test_multiply_case<float>("float", multiply_float_scalar, multiply_float_simd,
                                          n, offset, multiply_float_random);
                test_multiply_case<double>("double", multiply_double_scalar, multiply_double_simd,
                                           n, offset, multiply_double_random);
                ++multiply_cases;
            }
        }
        std::cout << "Elementwise multiply: PASS (" << multiply_cases
                  << " cases per type, float/double scalar/SIMD)\n";
        std::cout << "All 12 functions validated.\n";
        if (!options.check_only) {
            TimingCsv csv(options);
            // Separate timing sections, with explicit float/double calls.
            for (std::size_t n : options.sizes) {
                std::mt19937 float_random(4320), double_random(4320);
                const auto floats = make_inputs<float>(n, options.offset, float_random, false);
                const auto doubles = make_inputs<double>(n, options.offset, double_random, false);
                time_axpy<float>("float", saxpy_coefficient, saxpy_scalar, saxpy_simd, floats, options, csv);
                time_axpy<double>("double", daxpy_coefficient, daxpy_scalar, daxpy_simd, doubles, options, csv);
            }
            for (std::size_t n : options.sizes) {
                std::mt19937 float_random(4320), double_random(4320);
                const auto floats = make_inputs<float>(n, options.offset, float_random, false);
                const auto doubles = make_inputs<double>(n, options.offset, double_random, false);
                time_dot<float>("float", dot_float_scalar, dot_float_simd, floats, options, csv);
                time_dot<double>("double", dot_double_scalar, dot_double_simd, doubles, options, csv);
            }
            for (std::size_t n : options.sizes) {
                std::mt19937 float_random(4320), double_random(4320);
                const auto floats = make_inputs<float>(n, options.offset, float_random, false);
                const auto doubles = make_inputs<double>(n, options.offset, double_random, false);
                time_multiply<float>("float", multiply_float_scalar, multiply_float_simd, floats, options, csv);
                time_multiply<double>("double", multiply_double_scalar, multiply_double_simd, doubles, options, csv);
            }
            csv.finish();
            std::cout << "Wrote " << csv.rows() << " raw timing rows to " << options.csv_path << '\n';
        }
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
