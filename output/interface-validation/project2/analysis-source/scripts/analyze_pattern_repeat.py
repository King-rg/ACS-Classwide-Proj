"""Summarize the repeated sweep and compare paired random/sequential bandwidth."""

from pathlib import Path
import csv
import json
import sys

import numpy as np
import matplotlib.pyplot as plt
import analysis as figures


def write_csv(path, rows):
    with path.open("w") as output:
        writer = csv.DictWriter(output, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def main():
    runs = Path(__file__).resolve().parents[1] / "output/pattern-repeat"
    run = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else runs / (runs / "LATEST").read_text().strip()
    )
    metadata = json.loads((run / "metadata.json").read_text())
    with (run / "raw.csv").open() as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == len(metadata["cases"]) * metadata["trials"]
    identities = [
        (row["study"], row["spacing"], row["block"], row["random"], row["trial"])
        for row in rows
    ]
    assert len(set(identities)) == len(rows)
    summary = figures.summarize_rows(rows, metadata)
    write_csv(run / "summary.csv", summary)
    plots = run / "plots"
    plots.mkdir(exist_ok=True)
    figures.plot_pattern_granularity(summary, metadata, plots)
    # Report per-round medians separately instead of hiding between-round drift.
    round_summaries = []
    for round_number in range(1, metadata["rounds"] + 1):
        selected = [
            dict(row, trial=int(row["trial_in_round"]))
            for row in rows
            if int(row["round"]) == round_number
        ]
        round_meta = dict(metadata, trials=metadata["trials_per_round"])
        for result in figures.summarize_rows(selected, round_meta):
            round_summaries.append(dict(round=round_number, **result))
    write_csv(run / "round_summary.csv", round_summaries)
    comparisons = []
    block_sizes = sorted(
        {row["block"] for row in rows if row["study"] == "pattern_bandwidth"}
    )
    for block in block_sizes:
        selected = [
            row
            for row in rows
            if row["study"] == "pattern_bandwidth"
            and row["block"] == block
            and row["spacing"] == 4 * block
        ]
        pairs = {(row["trial"], row["random"]): row for row in selected}
        ratios = np.array(
            [
                pairs[trial, 1]["gib_s"] / pairs[trial, 0]["gib_s"]
                for trial in range(metadata["trials"])
            ]
        )
        result = dict(
            block_bytes=block,
            spacing_bytes=4 * block,
            pairs=len(ratios),
            ratio_median=float(np.median(ratios)),
            ratio_q25=float(np.percentile(ratios, 25)),
            ratio_q75=float(np.percentile(ratios, 75)),
        )
        for order, label in [(0, "sequential"), (1, "random")]:
            values = np.array(
                [row["gib_s"] for row in selected if row["random"] == order]
            )
            result[label + "_gib_s"] = float(np.median(values))
        for number in range(1, metadata["rounds"] + 1):
            start = (number - 1) * metadata["trials_per_round"]
            stop = number * metadata["trials_per_round"]
            result[f"round_{number}_ratio"] = float(np.median(ratios[start:stop]))
        comparisons.append(result)
    write_csv(run / "four_times_spacing_comparison.csv", comparisons)
    fig, ax = plt.subplots(figsize=(9, 4.8), layout="constrained")
    x = np.array(block_sizes, dtype=float)
    medians = np.array([row["ratio_median"] for row in comparisons])
    lower = np.array([row["ratio_q25"] for row in comparisons])
    upper = np.array([row["ratio_q75"] for row in comparisons])
    ax.errorbar(
        x,
        medians,
        yerr=[medians - lower, upper - medians],
        fmt="o",
        color="#24649a",
        capsize=5,
        ms=7,
        label="All trials: median and interquartile range",
    )
    for number, marker in zip(
        range(1, metadata["rounds"] + 1), ["s", "^", "D", "v", "P", "X"] * 10
    ):
        offset = 1.025 ** (number - (metadata["rounds"] + 1) / 2)
        ax.scatter(
            x * offset,
            [row[f"round_{number}_ratio"] for row in comparisons],
            marker=marker,
            facecolors="none",
            edgecolors="#bb6c16",
            s=40,
            label=f"Round {number} median",
        )
    ax.axhline(1, color="#555", ls="--", lw=1, label="Equal bandwidth")
    ax.set_xscale("log", base=2)
    ax.set_xticks(
        [8, 32, 64, 128, 256, 512, 1024], ["8", "32", "64", "128", "256", "512", "1024"]
    )
    ax.set_xlabel("Useful bytes per transfer (four-times spacing)")
    ax.set_ylabel("Random / sequential useful bandwidth (×)")
    ax.set_ylim(bottom=0)
    ax.set_title("Paired access-order comparison · 96 MiB mapped span")
    ax.grid(axis="y", alpha=0.18)
    ax.legend(frameon=False, fontsize=9)
    figures.save_figure(fig, plots, "paired_bandwidth_ratio")
    lines = [
        "# Pattern and granularity follow-up",
        f"{len(rows)} validated fresh-process measurements: {metadata['rounds']} rounds × {metadata['trials_per_round']} trials × {len(metadata['cases'])} conditions. Each timed interval targets {metadata['target_ms']} ms. Every trial retains the pilot’s full warm traversal/pass. CPU {metadata['cpus'][0]}. All samples retained.",
        "Sequential and random orders are adjacent pairs, with alternating order and shuffled condition groups. Bands show the middle half of observations, not confidence intervals. Separate round medians expose run-to-run drift.",
        "## Four-times spacing",
        "| Transfer bytes | Sequential GiB/s | Random GiB/s | Median paired random/sequential | Paired IQR | Round medians |",
        "|---:|---:|---:|---:|---:|---|",
    ]
    for row in comparisons:
        rounds = ", ".join(
            f"{row[f'round_{n}_ratio']:.3f}×" for n in range(1, metadata["rounds"] + 1)
        )
        lines.append(
            f"| {row['block_bytes']} | {row['sequential_gib_s']:.3f} | {row['random_gib_s']:.3f} | {row['ratio_median']:.3f}× | {row['ratio_q25']:.3f}–{row['ratio_q75']:.3f}× | {rounds} |"
        )
    lines += [
        "",
        "![Pattern and granularity sweep](plots/02_pattern_granularity.png)",
        "![Paired bandwidth comparison](plots/paired_bandwidth_ratio.png)",
        "## Interpretation limits",
        "The kernel and fixed mapped span are unchanged. Dense sweeps add measured intermediate sizes and remeasure the original sizes. Trial duration and acquisition schedule differ from the pilot, so differences between campaigns cannot isolate a hardware mechanism. At four-times spacing, useful payload is about 24 MiB within the 96 MiB mapped span. Cache-line traffic depends on block size and alignment, and can exceed that payload. The access-order array also occupies cache. Repeated passes can reuse cache contents. The 8-byte case uses 32-byte spacing and touches more cache-line bytes than its payload.",
        f"Hardware counters available on all measurements: {all(row['perf'] for row in rows)}. No CPU-frequency or background-load controls were changed. Timing alone cannot identify prefetch or cache-set effects.",
        "## Reproduction",
        "`python3 scripts/repeat_pattern.py` then `../.venv-analysis/bin/python scripts/analyze_pattern_repeat.py`. Acquisition sources, commands, raw observations, summaries, and raw-data hash are retained in this run. The original pilot and its latest-run marker are unchanged.",
    ]
    (run / "REPORT.md").write_text("\n\n".join(lines).replace("|\n\n|", "|\n|"))
    import shutil

    analysis_source = run / "analysis-source"
    analysis_source.mkdir(exist_ok=True)
    for name in ["analyze_pattern_repeat.py", "plot.py"]:
        shutil.copy2(Path(__file__).parent / name, analysis_source / name)
    print(json.dumps(comparisons, indent=2))
    print("All measurements validated:", len(rows))
    print("Counters available:", all(row["perf"] for row in rows))
    print(run)


if __name__ == "__main__":
    main()
