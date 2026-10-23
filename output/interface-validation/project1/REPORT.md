# Report figures

Each image is a standalone panel. CSV tables contain its plotted values.

## 02_throughput_axpy_float

axpy, float: scalar and auto-vectorized loops; nominal cache capacities, not measured residency boundaries.

![02_throughput_axpy_float](plots/02_throughput_axpy_float.png)

[Plotted data](tables/02_throughput_axpy_float.csv)

## 02_throughput_axpy_double

axpy, double: scalar and auto-vectorized loops; nominal cache capacities, not measured residency boundaries.

![02_throughput_axpy_double](plots/02_throughput_axpy_double.png)

[Plotted data](tables/02_throughput_axpy_double.csv)

## 01_speedup_axpy

axpy: matched trial ratios, float32 and float64. SIMD gains may compress beyond nominal cache capacities.

![01_speedup_axpy](plots/01_speedup_axpy.png)

[Plotted data](tables/01_speedup_axpy.csv)

## 02_throughput_dot_float

dot, float: scalar and auto-vectorized loops; nominal cache capacities, not measured residency boundaries.

![02_throughput_dot_float](plots/02_throughput_dot_float.png)

[Plotted data](tables/02_throughput_dot_float.csv)

## 02_throughput_dot_double

dot, double: scalar and auto-vectorized loops; nominal cache capacities, not measured residency boundaries.

![02_throughput_dot_double](plots/02_throughput_dot_double.png)

[Plotted data](tables/02_throughput_dot_double.csv)

## 01_speedup_dot

dot: matched trial ratios, float32 and float64. SIMD gains may compress beyond nominal cache capacities.

![01_speedup_dot](plots/01_speedup_dot.png)

[Plotted data](tables/01_speedup_dot.csv)

## 02_throughput_multiply_float

multiply, float: scalar and auto-vectorized loops; nominal cache capacities, not measured residency boundaries.

![02_throughput_multiply_float](plots/02_throughput_multiply_float.png)

[Plotted data](tables/02_throughput_multiply_float.csv)

## 02_throughput_multiply_double

multiply, double: scalar and auto-vectorized loops; nominal cache capacities, not measured residency boundaries.

![02_throughput_multiply_double](plots/02_throughput_multiply_double.png)

[Plotted data](tables/02_throughput_multiply_double.csv)

## 01_speedup_multiply

multiply: matched trial ratios, float32 and float64. SIMD gains may compress beyond nominal cache capacities.

![01_speedup_multiply](plots/01_speedup_multiply.png)

[Plotted data](tables/01_speedup_multiply.csv)

## 03_alignment_float

float: equal-kernel geometric mean of per-kernel ratios of median runtimes. No aggregate uncertainty interval is asserted.

![03_alignment_float](plots/03_alignment_float.png)

[Plotted data](tables/03_alignment_float.csv)

## 04_alignment_representative_float

float, base N=32,768; equal-kernel geometric mean; tails add seven elements, shifts add one element. No uncertainty interval is asserted.

![04_alignment_representative_float](plots/04_alignment_representative_float.png)

[Plotted data](tables/04_alignment_representative_float.csv)

## 03_alignment_double

double: equal-kernel geometric mean of per-kernel ratios of median runtimes. No aggregate uncertainty interval is asserted.

![03_alignment_double](plots/03_alignment_double.png)

[Plotted data](tables/03_alignment_double.csv)

## 04_alignment_representative_double

double, base N=32,768; equal-kernel geometric mean; tails add seven elements, shifts add one element. No uncertainty interval is asserted.

![04_alignment_representative_double](plots/04_alignment_representative_double.png)

[Plotted data](tables/04_alignment_representative_double.csv)

## 05_stride_bandwidth_262144_float

AXPY float, 262144 byte footprint. Useful payload excludes unused cache-line bytes.

![05_stride_bandwidth_262144_float](plots/05_stride_bandwidth_262144_float.png)

[Plotted data](tables/05_stride_bandwidth_262144_float.csv)

## 05_stride_bandwidth_262144_double

AXPY double, 262144 byte footprint. Useful payload excludes unused cache-line bytes.

![05_stride_bandwidth_262144_double](plots/05_stride_bandwidth_262144_double.png)

[Plotted data](tables/05_stride_bandwidth_262144_double.csv)

## 05_stride_speedup_262144

AXPY, 262144 byte footprint; matched scalar/auto trials.

![05_stride_speedup_262144](plots/05_stride_speedup_262144.png)

[Plotted data](tables/05_stride_speedup_262144.csv)

## 05_stride_bandwidth_201326592_float

AXPY float, 201326592 byte footprint. Useful payload excludes unused cache-line bytes.

![05_stride_bandwidth_201326592_float](plots/05_stride_bandwidth_201326592_float.png)

[Plotted data](tables/05_stride_bandwidth_201326592_float.csv)

## 05_stride_bandwidth_201326592_double

AXPY double, 201326592 byte footprint. Useful payload excludes unused cache-line bytes.

![05_stride_bandwidth_201326592_double](plots/05_stride_bandwidth_201326592_double.png)

[Plotted data](tables/05_stride_bandwidth_201326592_double.csv)

## 05_stride_speedup_201326592

AXPY, 201326592 byte footprint; matched scalar/auto trials.

![05_stride_speedup_201326592](plots/05_stride_speedup_201326592.png)

[Plotted data](tables/05_stride_speedup_201326592.csv)

## 04_tail_cost_float_32

AXPY float, base N=32; batched calls, aligned versus shifted one element.

![04_tail_cost_float_32](plots/04_tail_cost_float_32.png)

[Plotted data](tables/04_tail_cost_float_32.csv)

## 04_tail_cost_float_4096

AXPY float, base N=4096; batched calls, aligned versus shifted one element.

![04_tail_cost_float_4096](plots/04_tail_cost_float_4096.png)

[Plotted data](tables/04_tail_cost_float_4096.csv)

## 06_strict_dot_float

float dot product: strict versus relaxed floating-point reassociation; compiler/disassembly evidence retained.

![06_strict_dot_float](plots/06_strict_dot_float.png)

[Plotted data](tables/06_strict_dot_float.csv)

## 04_tail_cost_double_32

AXPY double, base N=32; batched calls, aligned versus shifted one element.

![04_tail_cost_double_32](plots/04_tail_cost_double_32.png)

[Plotted data](tables/04_tail_cost_double_32.csv)

## 04_tail_cost_double_4096

AXPY double, base N=4096; batched calls, aligned versus shifted one element.

![04_tail_cost_double_4096](plots/04_tail_cost_double_4096.png)

[Plotted data](tables/04_tail_cost_double_4096.csv)

## 06_strict_dot_double

double dot product: strict versus relaxed floating-point reassociation; compiler/disassembly evidence retained.

![06_strict_dot_double](plots/06_strict_dot_double.png)

[Plotted data](tables/06_strict_dot_double.csv)

## 07_roofline

Measured bandwidth with a write-allocation model and an empirical register-FMA peak; AXPY float32. Calibration IQR bands are not confidence intervals.

![07_roofline](plots/07_roofline.png)

[Plotted data](tables/07_roofline.csv)

## 08_cycles_axpy_float

axpy, float: measured user-space cycles, continuously scheduled counter; timer/dispatch overhead included.

![08_cycles_axpy_float](plots/08_cycles_axpy_float.png)

[Plotted data](tables/08_cycles_axpy_float.csv)

## 08_cycles_axpy_double

axpy, double: measured user-space cycles, continuously scheduled counter; timer/dispatch overhead included.

![08_cycles_axpy_double](plots/08_cycles_axpy_double.png)

[Plotted data](tables/08_cycles_axpy_double.csv)

## 08_cycles_dot_float

dot, float: measured user-space cycles, continuously scheduled counter; timer/dispatch overhead included.

![08_cycles_dot_float](plots/08_cycles_dot_float.png)

[Plotted data](tables/08_cycles_dot_float.csv)

## 08_cycles_dot_double

dot, double: measured user-space cycles, continuously scheduled counter; timer/dispatch overhead included.

![08_cycles_dot_double](plots/08_cycles_dot_double.png)

[Plotted data](tables/08_cycles_dot_double.csv)

## 08_cycles_multiply_float

multiply, float: measured user-space cycles, continuously scheduled counter; timer/dispatch overhead included.

![08_cycles_multiply_float](plots/08_cycles_multiply_float.png)

[Plotted data](tables/08_cycles_multiply_float.csv)

## 08_cycles_multiply_double

multiply, double: measured user-space cycles, continuously scheduled counter; timer/dispatch overhead included.

![08_cycles_multiply_double](plots/08_cycles_multiply_double.png)

[Plotted data](tables/08_cycles_multiply_double.csv)
