#!/usr/bin/env bash
set -eu
compiler=${1:-g++}
out=${2:-build/evidence/gcc}
mkdir -p "$out"
common=(-std=c++17 -Wall -Wextra -Wpedantic -O3 -mavx2 -ffast-math -ffp-contract=off)
if "$compiler" --version | head -1 | rg -qi clang; then
 scalar=(-fno-vectorize -fno-slp-vectorize)
 report=(-Rpass=loop-vectorize -Rpass-missed=loop-vectorize -Rpass-analysis=loop-vectorize)
else
 scalar=(-fno-tree-vectorize -fno-tree-slp-vectorize)
 report=(-fopt-info-vec-all)
fi
# Numerical kernels share finite-input relaxed semantics. Keep harness validation
# strict so isfinite/error checks cannot be optimized away by fast-math.
set -x
"$compiler" "${common[@]}" "${scalar[@]}" -DVARIANT=scalar -c experiments/ordinary.cpp -o "$out/scalar.o"
"$compiler" "${common[@]}" "${report[@]}" -DVARIANT=auto -c experiments/ordinary.cpp -o "$out/auto.o" 2> "$out/vectorization.txt"
"$compiler" "${common[@]}" -fno-fast-math "${report[@]}" -DVARIANT=auto -c experiments/ordinary.cpp -o "$out/auto_strict.o" 2> "$out/vectorization-strict.txt"
"$compiler" "${common[@]}" -c experiments/intrinsics.cpp -o "$out/simd.o"
"$compiler" "${common[@]}" -mfma -c experiments/compute.cpp -o "$out/compute.o"
"$compiler" -std=c++17 -Wall -Wextra -Wpedantic -O3 -mavx2 -ffp-contract=off -c experiments/run.cpp -o "$out/run.o"
"$compiler" "$out/run.o" "$out/scalar.o" "$out/auto.o" "$out/simd.o" "$out/compute.o" -o "$out/runner"
for object in scalar auto auto_strict simd compute; do
 objdump -d -C "$out/$object.o" > "$out/disassembly-$object.txt"
done
