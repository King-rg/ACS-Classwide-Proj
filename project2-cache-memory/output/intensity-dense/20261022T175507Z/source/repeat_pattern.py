"""Repeat the pattern/granularity sweep with paired access orders and longer trials."""

from pathlib import Path
import argparse
import csv
import datetime
import hashlib
import json
import os
import random
import subprocess

import run as acquisition


def dense_cases():
    """Add measured intermediate sizes while keeping the mapped span fixed."""
    spacings = [64, 96, 128, 160, 192, 224, 256, 320, 384, 512, 640, 768, 1024]
    blocks = [
        8,
        16,
        24,
        32,
        48,
        64,
        96,
        128,
        160,
        192,
        224,
        256,
        320,
        384,
        512,
        768,
        1024,
    ]
    common = dict(bytes=96 * 1024**2, read_pct=100, huge=0, streams=1, threads=1)
    cases = []
    for spacing in spacings:
        for order in [0, 1]:
            cases.append(
                dict(
                    study="pattern_latency",
                    mode="latency",
                    spacing=spacing,
                    block=8,
                    random=order,
                    **common,
                )
            )
    for block in blocks:
        for gap in [1, 4]:
            for order in [0, 1]:
                cases.append(
                    dict(
                        study="pattern_bandwidth",
                        mode="bandwidth",
                        spacing=block * gap,
                        block=block,
                        random=order,
                        **common,
                    )
                )
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dense",
        action="store_true",
        help="Measure intermediate spacings and transfer sizes",
    )
    parser.add_argument("--mix", action="store_true", help="Measure all read percentages in steps of ten")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument(
        "--trials", type=int, default=15, help="Trials per condition per round"
    )
    parser.add_argument("--target-ms", type=int, default=250)
    args = parser.parse_args()
    assert args.rounds > 0 and args.trials > 0 and 1 <= args.target_ms <= 1000
    root = acquisition.ROOT
    compiler = os.environ.get("CC", "cc")
    flags = os.environ.get(
        "CFLAGS", "-O3 -march=native -std=c11 -Wall -Wextra -Wpedantic"
    )
    subprocess.run(
        ["make", "-B", "-C", str(root), "CC=" + compiler, "CFLAGS=" + flags, "check"],
        check=True,
    )
    cpus = acquisition.select_cpus()
    cases = [
        case
        for case in acquisition.build_cases("quick", len(cpus))
        if case["study"] in {"pattern_latency", "pattern_bandwidth"}
    ]
    if args.dense:
        cases = dense_cases()
    if args.mix:
        assert not args.dense, "Choose either mix or pattern sweep"
        cases = [dict(study="mix", mode="bandwidth", bytes=96*1024**2,
                      spacing=1024, block=1024, read_pct=read_pct, random=order,
                      huge=0, streams=1, threads=1)
                 for read_pct in range(0, 101, 10) for order in [0, 1]]
    sequential_cases = [case for case in cases if case["random"] == 0]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    study_folder = "pattern-dense" if args.dense else "pattern-repeat"
    if args.mix:
        study_folder = "mix-dense"
    output = root / "output" / study_folder / stamp
    output.mkdir(parents=True)
    metadata = acquisition.collect_metadata(
        study_folder,
        args.rounds * args.trials,
        args.target_ms,
        cpus,
        compiler,
        flags,
        cases,
    )
    metadata.update(
        dense=args.dense,
        pointer_spacings=sorted(
            {case["spacing"] for case in cases if case["study"] == "pattern_latency"}
        ),
        transfer_sizes=sorted(
            {case["block"] for case in cases if case["study"] == "pattern_bandwidth"}
        ),
        rounds=args.rounds,
        trials_per_round=args.trials,
        order_seed=4320,
        benchmark_sha256=hashlib.sha256(
            (root / "build/memory_bench").read_bytes()
        ).hexdigest(),
        protocol="Fixed 96 MiB mapped span; dense mode adds intermediate measured sizes and remeasures the original sizes. Each trial uses a fresh process and mapping. Sequential/random cases are adjacent pairs; pair order alternates. Pair groups are shuffled each trial. Three separate acquisition rounds by default. Initialization, one warm traversal/pass, and validation remain outside timing. No machine-policy changes. All samples retained.",
    )
    if args.mix:
        metadata["protocol"] = "Fixed 96 MiB span, 1 KiB dense blocks; read percentages 0 through 100 in steps of ten. Three rounds of fifteen 250 ms trials per condition. Fresh process/mapping per trial; adjacent sequential/random pairs alternate order; ratio groups shuffled with seed 4320. Initialization, warmup, validation outside timing. All samples retained."
    acquisition.snapshot_sources(output)
    (output / "PLAN.md").write_text(
        "Test whether the pilot random-over-sequential advantage at 4x spacing persists with longer repeated trials. Keep mapped span, kernel, warmup, and CPU selection fixed. Dense mode measures intermediate spacing and granularity points, including cache-line and non-cache-line multiples, and remeasures all anchor sizes in the same campaign. Do not claim a cache or prefetch mechanism without counter evidence. Compare paired ratios and per-round medians; retain all measurements.\n"
    )
    if args.mix:
        (output / "PLAN.md").write_text(metadata["protocol"] + "\nAssess whether the pilot 50/50 dip persists; do not infer causal mechanisms without counters.\n")
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2))
    print("OUTPUT " + str(output), flush=True)
    rng = random.Random(4320)
    with (output / "raw.csv").open("w") as target:
        writer = None
        for round_index in range(args.rounds):
            for local_trial in range(args.trials):
                trial = round_index * args.trials + local_trial
                groups = sequential_cases.copy()
                rng.shuffle(groups)
                for group_index, case in enumerate(groups):
                    orders = [0, 1] if (trial + group_index) % 2 == 0 else [1, 0]
                    for order in orders:
                        condition = dict(case, random=order)
                        command = [
                            str(root / "build/memory_bench"),
                            condition["mode"],
                            *[
                                str(condition[key])
                                for key in [
                                    "bytes",
                                    "spacing",
                                    "block",
                                    "read_pct",
                                    "random",
                                    "huge",
                                    "streams",
                                ]
                            ],
                            str(args.target_ms),
                            str(cpus[0]),
                        ]
                        result = json.loads(subprocess.check_output(command, text=True))
                        assert result["check"] == "pass" and result["elapsed_ns"] > 0
                        row = {
                            **condition,
                            "trial": trial,
                            "round": round_index + 1,
                            "trial_in_round": local_trial,
                            "pair_order": orders.index(order),
                            **result,
                        }
                        if writer is None:
                            writer = csv.DictWriter(target, fieldnames=row)
                            writer.writeheader()
                        writer.writerow(row)
                        target.flush()
                        metadata["commands"].append(command)
                print(
                    f"Round {round_index+1}/{args.rounds}, trial {local_trial+1}/{args.trials} complete",
                    flush=True,
                )
            (output / "metadata.json").write_text(json.dumps(metadata, indent=2))
    metadata["finished"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    metadata["raw_sha256"] = hashlib.sha256(
        (output / "raw.csv").read_bytes()
    ).hexdigest()
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2))
    (output.parent / "LATEST").write_text(output.name + "\n")
    if args.mix:
        import plot as figures
        with (output / "raw.csv").open() as source:
            rows = list(csv.DictReader(source))
        assert len(rows) == len(cases) * args.rounds * args.trials
        summary = figures.summarize_rows(rows, metadata)
        with (output / "summary.csv").open("w") as target:
            writer = csv.DictWriter(target, fieldnames=summary[0])
            writer.writeheader()
            writer.writerows(summary)
        plots = output / "plots"
        plots.mkdir()
        figures.plot_read_write_mix(summary, metadata, plots)
    print("COMPLETE " + str(output), flush=True)


if __name__ == "__main__":
    main()
