"""Acquire the Project 2 experiment matrix without changing machine policy."""

from pathlib import Path
import argparse
import datetime
import json
import csv
import subprocess
import os
import random
import hashlib
import shutil

ROOT = Path(__file__).resolve().parents[1]


def parse_cpu_set(text):
    output = set()
    for part in text.strip().split(","):
        if "-" in part:
            first, last = map(int, part.split("-"))
            output.update(range(first, last + 1))
        elif part:
            output.add(int(part))
    return output


def select_cpus():
    """Choose one allowed CPU per physical core, preferring P-cores when exposed."""
    allowed = sorted(os.sched_getaffinity(0))
    cpus = []
    cores = set()
    pmu = Path("/sys/bus/event_source/devices/cpu_core/cpus")
    preferred = parse_cpu_set(pmu.read_text()) if pmu.exists() else set(allowed)
    for cpu in allowed:
        if cpu not in preferred:
            continue
        topology = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
        key = (
            (topology / "physical_package_id").read_text(),
            (topology / "core_id").read_text(),
        )
        if key not in cores:
            cores.add(key)
            cpus.append(cpu)
    assert cpus
    return cpus


def build_cases(profile, cpu_count):
    """Construct the same ordered cases for quick and full acquisition profiles."""
    cases = []

    def add_case(
        study,
        mode,
        span,
        spacing=64,
        block=8,
        reads=100,
        random_access=1,
        huge=0,
        streams=1,
        threads=1,
    ):
        cases.append(
            dict(
                study=study,
                mode=mode,
                bytes=span,
                spacing=spacing,
                block=block,
                read_pct=reads,
                random=random_access,
                huge=huge,
                streams=streams,
                threads=threads,
            )
        )

    KiB = 1024
    MiB = 1024**2
    sizes = [
        4 * KiB,
        16 * KiB,
        32 * KiB,
        48 * KiB,
        64 * KiB,
        256 * KiB,
        512 * KiB,
        1 * MiB,
        2 * MiB,
        8 * MiB,
        24 * MiB,
        48 * MiB,
        96 * MiB,
        192 * MiB,
    ]
    if profile == "full":
        sizes = sorted(
            set(
                sizes
                + [
                    8 * KiB,
                    96 * KiB,
                    128 * KiB,
                    768 * KiB,
                    1280 * KiB,
                    4 * MiB,
                    16 * MiB,
                    32 * MiB,
                    64 * MiB,
                    128 * MiB,
                ]
            )
        )
    for span_bytes in sizes:
        for order in [0, 1]:
            add_case("working_set", "latency", span_bytes, random_access=order)
    for spacing in [64, 256, 1024]:
        for order in [0, 1]:
            add_case(
                "pattern_latency",
                "latency",
                96 * MiB,
                spacing=spacing,
                random_access=order,
            )
    for block in [8, 64, 256, 1024]:
        for gap in [1, 4]:
            for order in [0, 1]:
                add_case(
                    "pattern_bandwidth",
                    "bandwidth",
                    96 * MiB,
                    spacing=block * gap,
                    block=block,
                    random_access=order,
                )
    for reads in [100, 70, 50, 0]:
        for order in [0, 1]:
            add_case(
                "mix",
                "bandwidth",
                96 * MiB,
                spacing=1024,
                block=1024,
                reads=reads,
                random_access=order,
            )
    for threads in sorted(
        set([1, min(2, cpu_count), min(4, cpu_count), min(6, cpu_count)])
    ):
        add_case("intensity_threads", "latency", 96 * MiB, threads=threads)
    for streams in [1, 2, 4, 8, 16] if profile == "quick" else [1, 2, 4, 8, 16, 32, 64]:
        add_case("intensity_streams", "latency", 96 * MiB, streams=streams)
    for span_bytes in [4 * MiB, 16 * MiB, 64 * MiB, 192 * MiB]:
        for order in [0, 1]:
            for huge in [0, 1]:
                add_case(
                    "tlb",
                    "latency",
                    span_bytes,
                    spacing=4096,
                    random_access=order,
                    huge=huge,
                )
    for span_bytes in [32 * KiB, 192 * MiB]:
        add_case(
            "pitfall",
            "bandwidth",
            span_bytes,
            spacing=1024,
            block=1024,
            random_access=0,
        )
    return cases


def read_caches(primary):
    """Record nominal data/unified cache capacities for the primary CPU."""
    caches = []
    for cache_dir in sorted(
        Path(f"/sys/devices/system/cpu/cpu{primary}/cache").glob("index*")
    ):
        if (cache_dir / "type").read_text().strip() == "Instruction":
            continue
        text = (cache_dir / "size").read_text().strip()
        size = int(text[:-1]) * (1024 if text.endswith("K") else 1024**2)
        caches.append(
            dict(
                level=int((cache_dir / "level").read_text()),
                bytes=size,
                shared=(cache_dir / "shared_cpu_list").read_text().strip(),
            )
        )
    return caches


def read_optional_text(path):
    """Read a Linux metadata file when the host exposes it."""
    path = Path(path)
    return path.read_text().strip() if path.exists() else None


def collect_metadata(profile, trials, target_ms, cpus, compiler, flags, cases):
    """Capture machine settings and acquisition parameters without modifying them."""
    primary = cpus[0]
    metadata = dict(
        profile=profile,
        trials=trials,
        target_ms=target_ms,
        cpus=cpus,
        caches=read_caches(primary),
        started=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        compiler=subprocess.check_output([compiler, "--version"], text=True),
        build_flags=flags,
        kernel=subprocess.check_output(["uname", "-a"], text=True),
        lscpu=subprocess.check_output(["lscpu"], text=True),
        meminfo=read_optional_text("/proc/meminfo"),
        governor=read_optional_text(
            f"/sys/devices/system/cpu/cpu{primary}/cpufreq/scaling_governor"
        ),
        smt=read_optional_text("/sys/devices/system/cpu/smt/active"),
        perf_event_paranoid=read_optional_text("/proc/sys/kernel/perf_event_paranoid"),
        transparent_hugepage=read_optional_text(
            "/sys/kernel/mm/transparent_hugepage/enabled"
        ),
        numa_maps_policy="Anonymous mappings first-touched by each pinned worker; default NUMA policy; placement not independently measured.",
        cases=cases,
        commands=[],
    )
    return metadata


def snapshot_sources(run_dir):
    """Keep the acquisition source and instructions with the measured data."""
    (run_dir / "source").mkdir()
    for source in (ROOT / "src").glob("*.[ch]"):
        shutil.copy2(source, run_dir / "source" / source.name)
    shutil.copy2(ROOT / "Makefile", run_dir / "source/Makefile")
    shutil.copy2(ROOT / "PLAN.md", run_dir / "source/PLAN.md")
    for f in Path(__file__).parent.glob("*.py"):
        shutil.copy2(f, run_dir / "source" / f.name)


def measure_cases(run_dir, cases, trials, target_ms, cpus, metadata):
    """Shuffle cases reproducibly and flush each validated trial to the raw CSV."""
    random.Random(4320).shuffle(cases)
    with (run_dir / "raw.csv").open("w") as output:
        writer = None
        for i, benchmark_case in enumerate(cases):
            for trial in range(trials):
                command = [
                    str(ROOT / "build/memory_bench"),
                    benchmark_case["mode"],
                    str(benchmark_case["bytes"]),
                    str(benchmark_case["spacing"]),
                    str(benchmark_case["block"]),
                    str(benchmark_case["read_pct"]),
                    str(benchmark_case["random"]),
                    str(benchmark_case["huge"]),
                    str(benchmark_case["streams"]),
                    str(target_ms),
                    ",".join(map(str, cpus[: benchmark_case["threads"]])),
                ]
                result = subprocess.run(
                    command, check=True, capture_output=True, text=True
                )
                result_row = json.loads(result.stdout)
                assert result_row["check"] == "pass"
                row = {**benchmark_case, "trial": trial, **result_row}
                metadata["commands"].append(command)
                if writer is None:
                    writer = csv.DictWriter(output, fieldnames=row.keys())
                    writer.writeheader()
                writer.writerow(row)
                output.flush()
            print(
                f"{i + 1}/{len(cases)} {benchmark_case['study']} {benchmark_case['bytes'] // 1024} KiB",
                flush=True,
            )


def main():
    """Build, acquire the selected profile, then mark the completed run as latest."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["quick", "full"], default="quick")
    args = parser.parse_args()
    trials, target_ms = (3, 15) if args.profile == "quick" else (7, 100)
    run_dir = (
        ROOT
        / "output"
        / datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    run_dir.mkdir(parents=True)
    compiler = os.environ.get("CC", "cc")
    flags = os.environ.get(
        "CFLAGS", "-O3 -march=native -std=c11 -Wall -Wextra -Wpedantic"
    )
    subprocess.run(
        ["make", "-f", "build.mk", "-C", str(ROOT), "CC=" + compiler, "CFLAGS=" + flags], check=True
    )
    cpus = select_cpus()
    cases = build_cases(args.profile, len(cpus))
    metadata = collect_metadata(
        args.profile, trials, target_ms, cpus, compiler, flags, cases
    )
    snapshot_sources(run_dir)
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    print(run_dir, flush=True)
    measure_cases(run_dir, cases, trials, target_ms, cpus, metadata)
    metadata["finished"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    metadata["raw_sha256"] = hashlib.sha256(
        (run_dir / "raw.csv").read_bytes()
    ).hexdigest()
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    (ROOT / "output/LATEST").write_text(run_dir.name + "\n")
    print("COMPLETE " + str(run_dir), flush=True)


if __name__ == "__main__":
    main()
