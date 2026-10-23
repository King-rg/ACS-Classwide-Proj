CC ?= gcc
CFLAGS ?= -O3 -march=native -std=c11 -Wall -Wextra -Wpedantic
LDLIBS = -pthread -lm
.PHONY: all check quick full clean
all: build/memory_bench
build/memory_bench: src/memory_bench.c
	mkdir -p build
	$(CC) $(CFLAGS) $< -o $@ $(LDLIBS)
check: all
	python3 scripts/check.py
quick: all
	python3 scripts/run.py --profile quick
full: all
	python3 scripts/run.py --profile full
clean:
	rm -f build/memory_bench
