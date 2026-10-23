CXX = g++
MODE ?= avx
BUILD_DIR ?= build/$(notdir $(CXX))/$(MODE)
TARGET = $(BUILD_DIR)/simd_starter
SCALAR_SOURCES = src/simd/saxpy.cpp src/simd/dot_product.cpp src/simd/elementwise_multiply.cpp src/simd/reference.cpp
SIMD_SOURCES = src/simd/saxpy_simd.cpp src/simd/dot_product_simd.cpp src/simd/elementwise_multiply_simd.cpp
SOURCES = $(SCALAR_SOURCES) $(SIMD_SOURCES) src/simd/main.cpp src/simd/timing.cpp
HEADERS = $(wildcard src/simd/*.hpp)
BUILD_METADATA = -DSIMD_BUILD_MODE=\"$(MODE)\"
OBJECTS = $(patsubst src/simd/%.cpp,$(BUILD_DIR)/%.o,$(SOURCES))
SCALAR_OBJECTS = $(patsubst src/simd/%.cpp,$(BUILD_DIR)/%.o,$(SCALAR_SOURCES))
COMMON_FLAGS = -std=c++17 -Wall -Wextra -Wpedantic -O3 -ffp-contract=off
IS_CLANG := $(shell $(CXX) --version 2>/dev/null | head -n 1 | grep -i clang)

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

.PHONY: all run clean
all: $(TARGET)

# Same optimization level and ISA for scalar and SIMD; only scalar disables
# auto-vectorization. Keep files separate and do not enable LTO for this setup.
$(SCALAR_OBJECTS): EXTRA_FLAGS = $(SCALAR_FLAGS)
$(BUILD_DIR)/%.o: src/simd/%.cpp $(HEADERS) Makefile
	mkdir -p $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(BUILD_METADATA) $(COMMON_FLAGS) $(CXXFLAGS) $(ISA_FLAGS) $(EXTRA_FLAGS) -c $< -o $@

$(TARGET): $(OBJECTS)
	$(CXX) $(OBJECTS) $(LDFLAGS) $(LDLIBS) -o $@

run: $(TARGET)
	$(TARGET)

clean:
	rm -rf build
