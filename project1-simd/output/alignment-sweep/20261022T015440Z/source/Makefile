CC = gcc
MODE ?= avx
AUTO ?= 0
BUILD_DIR ?= build/$(notdir $(CC))/$(MODE)$(if $(filter 1,$(AUTO)),-auto,)
KERNELS = axpy dot multiply
PROGRAMS = $(addprefix $(BUILD_DIR)/,$(KERNELS))
SCALAR_OBJECTS = $(addprefix $(BUILD_DIR)/,$(addsuffix _scalar.o,$(KERNELS)))
SIMD_OBJECTS = $(addprefix $(BUILD_DIR)/,$(addsuffix _simd.o,$(KERNELS)))
BUILD_METADATA = -DSIMD_BUILD_MODE=\"$(MODE)\"
COMMON_FLAGS = -std=c11 -D_POSIX_C_SOURCE=200809L -Wall -Wextra -Wpedantic -O3 -ffp-contract=off
IS_CLANG := $(shell $(CC) --version 2>/dev/null | head -n 1 | grep -i clang)

ifeq ($(MODE),avx)
  ISA_FLAGS = -mavx
else ifeq ($(MODE),native)
  ISA_FLAGS = -march=native
else
  $(error MODE must be avx or native; scalar/SIMD are now separate functions in each executable)
endif

ifneq ($(IS_CLANG),)
  SCALAR_FLAGS = -fno-vectorize -fno-slp-vectorize
else
  SCALAR_FLAGS = -fno-tree-vectorize -fno-tree-slp-vectorize
endif

.PHONY: all run check clean
all: $(PROGRAMS)

# Same optimization level and ISA for scalar and SIMD; only scalar disables
# auto-vectorization. Keep files separate and do not enable LTO for this setup.
$(SCALAR_OBJECTS): EXTRA_FLAGS = $(SCALAR_FLAGS)
$(BUILD_DIR)/%.o: src/%.c src/benchmark.h src/kernels.h Makefile
	mkdir -p $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(BUILD_METADATA) $(COMMON_FLAGS) $(CFLAGS) $(ISA_FLAGS) $(EXTRA_FLAGS) -c $< -o $@

# Auto mode compiles the same ordinary loops under the second symbol names.
ifeq ($(AUTO),1)
BUILD_METADATA += -DBENCH_AUTO=1
$(SCALAR_OBJECTS): EXTRA_FLAGS += -ffast-math
$(BUILD_DIR)/%_auto.c: src/%_scalar.c src/kernels.h Makefile
	mkdir -p $(BUILD_DIR)
	sed 's/_scalar/_simd/g' $< > $@
$(SIMD_OBJECTS): $(BUILD_DIR)/%_simd.o: $(BUILD_DIR)/%_auto.c src/kernels.h Makefile
	$(CC) $(CPPFLAGS) $(COMMON_FLAGS) $(CFLAGS) $(ISA_FLAGS) -ffast-math -Isrc -c $< -o $@
endif

define kernel_program
$(BUILD_DIR)/$(1): $(BUILD_DIR)/$(1)_main.o $(BUILD_DIR)/$(1)_scalar.o $(BUILD_DIR)/$(1)_simd.o $(BUILD_DIR)/benchmark.o
	$(CC) $$^ $(LDFLAGS) $(LDLIBS) -lm -o $$@
endef
$(foreach kernel,$(KERNELS),$(eval $(call kernel_program,$(kernel))))

run: $(PROGRAMS)
	@set -e; for program in $(PROGRAMS); do $$program; done

$(BUILD_DIR)/correctness.o: tests/correctness.c src/benchmark.h src/kernels.h Makefile
	mkdir -p $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(BUILD_METADATA) $(COMMON_FLAGS) $(CFLAGS) $(ISA_FLAGS) -Isrc -c $< -o $@

$(BUILD_DIR)/correctness: $(BUILD_DIR)/correctness.o $(SCALAR_OBJECTS) $(SIMD_OBJECTS) $(BUILD_DIR)/benchmark.o
	$(CC) $^ $(LDFLAGS) $(LDLIBS) -lm -o $@

check: $(BUILD_DIR)/correctness
	$(BUILD_DIR)/correctness

clean:
	rm -rf build

# Pin using the current allowed CPU set; generate separate CSVs for each kernel.
.PHONY: alignment
alignment: $(PROGRAMS)
	@set -e; cpu=$$(python3 -c 'import os; print(min(os.sched_getaffinity(0)))'); for k in $(KERNELS); do taskset -c $$cpu $(BUILD_DIR)/$$k --study alignment --trials 15 --warmups 5 --csv output/alignment/$(MODE)$(if $(filter 1,$(AUTO)),-auto,)/$$k.csv; done
