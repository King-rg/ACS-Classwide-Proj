#!/usr/bin/env bash
set -eu
root=$1
# Default/strict FP auto comparison: no fast-math; same target for all three variants.
for pair in 'g++ gcc' 'clang++ clang'; do
 read -r compiler label <<< "$pair"
 folder="$root/strict-$label"
 mkdir -p "$folder"
 flags=(-std=c++17 -O3 -mavx2 -ffp-contract=off -fno-fast-math)
 if [ "$label" = gcc ]; then scalar=(-fno-tree-vectorize -fno-tree-slp-vectorize); else scalar=(-fno-vectorize -fno-slp-vectorize); fi
 {
 set -x
 "$compiler" "${flags[@]}" "${scalar[@]}" -DVARIANT=scalar -c experiments/ordinary.cpp -o "$folder/scalar.o"
 cp "$root/build-$label/auto_strict.o" "$folder/auto.o"
 "$compiler" "${flags[@]}" -c experiments/intrinsics.cpp -o "$folder/simd.o"
 cp "$root/build-$label/compute.o" "$folder/compute.o"
 cp "$root/build-$label/run.o" "$folder/run.o"
 "$compiler" "$folder/run.o" "$folder/scalar.o" "$folder/auto.o" "$folder/simd.o" "$folder/compute.o" -o "$folder/runner"
 } > "$folder/build.log" 2>&1
 printf '%s\n' 'axpy float strict 4096 1 0' 'axpy double strict 4096 1 0' 'dot float strict 4096 1 0' 'dot double strict 4096 1 0' 'multiply float strict 4096 1 0' 'multiply double strict 4096 1 0' > "$folder/cases.txt"
 "$folder/runner" "$folder/cases.txt" "$folder" "strict-$label" 0 0 > "$folder/run.log" 2>&1
 objdump -d -C "$folder/auto.o" > "$folder/disassembly-auto.txt"
done
# Sanitizer version of all three numerical variants; original runner stays strict FP.
folder="$root/sanitize"
mkdir -p "$folder"
flags=(-std=c++17 -O1 -g -mavx2 -ffast-math -ffp-contract=off -fsanitize=address,undefined -fno-omit-frame-pointer)
{
set -x
clang++ "${flags[@]}" -fno-vectorize -fno-slp-vectorize -DVARIANT=scalar -c experiments/ordinary.cpp -o "$folder/scalar.o"
clang++ "${flags[@]}" -DVARIANT=auto -c experiments/ordinary.cpp -o "$folder/auto.o"
clang++ "${flags[@]}" -c experiments/intrinsics.cpp -o "$folder/simd.o"
clang++ "${flags[@]}" -mfma -c experiments/compute.cpp -o "$folder/compute.o"
clang++ "${flags[@]}" -fno-fast-math -c experiments/run.cpp -o "$folder/run.o"
clang++ -fsanitize=address,undefined "$folder/run.o" "$folder/scalar.o" "$folder/auto.o" "$folder/simd.o" "$folder/compute.o" -o "$folder/runner"
} > "$folder/build.log" 2>&1
printf '%s\n' 'axpy float sanitize 19 8 1' 'axpy double sanitize 19 4 1' 'dot float sanitize 19 2 1' 'dot double sanitize 19 8 1' 'multiply float sanitize 19 4 1' 'multiply double sanitize 19 8 1' > "$folder/cases.txt"
"$folder/runner" "$folder/cases.txt" "$folder" sanitizer 0 0 > "$folder/run.log" 2>&1
