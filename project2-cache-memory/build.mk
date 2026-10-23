CC ?= gcc
PYTHON ?= ../.venv-analysis/bin/python
CFLAGS ?= -O3 -march=native -std=c11 -Wall -Wextra -Wpedantic
LDLIBS = -pthread -lm
.PHONY: all check
all: build/memory_bench
build/memory_bench: src/memory_bench.c src/prepared_access.h src/hierarchy_access.h
	mkdir -p build
	$(CC) $(CFLAGS) $< -o $@ $(LDLIBS)
check: all
	$(PYTHON) scripts/check.py
