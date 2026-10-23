# Primary references for the controlled evidence

- Intel i7-13800H specifications (Raptor Lake, 6 P cores + 8 E cores, 5.2 GHz
  advertised P-core maximum turbo, AVX2, 24 MB Smart Cache):
  https://www.intel.com/content/www/us/en/products/sku/232164/intel-core-i713800h-processor-24m-cache-up-to-5-20-ghz/specifications.html
- Intel Optimization Reference Manual 248966-050US, Table 2-4, printed page 2-14:
  Golden Cove-class vector multiply/FMA execution units: 2 x 256-bit.
  https://cdrdv2-public.intel.com/821612/248966-Optimization-Reference-Manual-V1-050.pdf
- LLVM vectorizers, reductions / floating point reassociation and diagnostics:
  https://llvm.org/docs/Vectorizers.html
- GCC optimization flags and floating-point semantics:
  https://gcc.gnu.org/onlinedocs/gcc-13.4.0/gcc/Optimize-Options.html
- Linux perf_event_open API (user-space counting and read-format semantics):
  https://man7.org/linux/man-pages/man2/perf_event_open.2.html

The theoretical AVX2 FMA reference is 2 units * 8 float lanes * 2 FLOP * 5.2 GHz
= 166.4 GFLOP/s per P-core (83.2 for double). This is an architectural/turbo upper
estimate, NOT the sustained measured clock, a socket-wide peak, or the peak of our
non-FMA main kernels. An independent measured register-FMA loop supplies a more
conservative empirical compute reference. Source mapping and DVFS uncertainty remain
explicit, and the empirical reference is not claimed to be the silicon maximum.
