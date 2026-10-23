"""Generate the eight Project 2 figures and their supporting tables."""

from pathlib import Path
import sys
import csv
import json
import collections
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titleweight": "bold",
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
    }
)
colors = ["#24649a", "#bb6c16", "#477d62", "#8e679b"]


def summarize_rows(rows, metadata):
    """Validate trial groups and compute medians and interquartile bounds."""
    case_fields = [
        "study",
        "mode",
        "bytes",
        "spacing",
        "block",
        "read_pct",
        "random",
        "huge",
        "streams",
        "threads",
    ]
    groups = collections.defaultdict(list)
    for row in rows:
        assert row["check"] == "pass"
        for k in case_fields[2:] + ["trial", "huge_bytes"]:
            row[k] = int(row[k])
        for k in [
            "elapsed_ns",
            "operations",
            "payload_bytes",
            "ns_per_access",
            "chain_latency_ns",
            "million_accesses_s",
            "gib_s",
            "cycles",
            "llc_read_misses",
            "dtlb_read_misses",
        ]:
            row[k] = float(row[k])
        row["perf"] = row["counters_available"].lower() == "true"
        row["cycles_per_access"] = (
            row["cycles"] / row["operations"] if row["perf"] else float("nan")
        )
        row["llc_misses_per_1000"] = (
            1000 * row["llc_read_misses"] / row["operations"]
            if row["perf"]
            else float("nan")
        )
        row["dtlb_misses_per_1000"] = (
            1000 * row["dtlb_read_misses"] / row["operations"]
            if row["perf"]
            else float("nan")
        )
        groups[tuple((row[k] for k in case_fields))].append(row)
    summary = []
    for key, trials in groups.items():
        assert sorted((x["trial"] for x in trials)) == list(range(metadata["trials"]))
        case = dict(zip(case_fields, key))
        case["huge_verified"] = all(
            (x["huge_bytes"] >= x["bytes"] * x["threads"] for x in trials)
        )
        case["counters_available"] = all((x["perf"] for x in trials))
        for metric in [
            "ns_per_access",
            "chain_latency_ns",
            "million_accesses_s",
            "gib_s",
            "cycles_per_access",
            "llc_misses_per_1000",
            "dtlb_misses_per_1000",
        ]:
            values = np.array([x[metric] for x in trials])
            case[metric] = np.median(values)
            case[metric + "_q25"] = np.percentile(values, 25)
            case[metric + "_q75"] = np.percentile(values, 75)
        summary.append(case)
    return summary


def select_cases(summary, study, **filters):
    return sorted(
        [
            case
            for case in summary
            if case["study"] == study
            and all((case[k] == v for k, v in filters.items()))
        ],
        key=lambda case: (
            case["bytes"],
            case["spacing"],
            case["block"],
            case["read_pct"],
            case["streams"],
            case["threads"],
        ),
    )


def save_figure(fig, plot_dir, name):
    fig.savefig(plot_dir / (name + ".png"), dpi=220, bbox_inches="tight")
    fig.savefig(plot_dir / (name + ".svg"), bbox_inches="tight")
    plt.close(fig)
    return name


def plot_iqr_line(ax, x, cases, metric, label, color, line_style="-", marker="o"):
    y = [case[metric] for case in cases]
    ax.plot(x, y, label=label, color=color, ls=line_style, marker=marker, ms=4)
    ax.fill_between(
        x,
        [case[metric + "_q25"] for case in cases],
        [case[metric + "_q75"] for case in cases],
        color=color,
        alpha=0.13,
    )
    ax.grid(axis="y", alpha=0.18)


def annotate_caches(ax, metadata):
    ax.set_xscale("log", base=2)
    ax.set_xticks(
        [4 * 1024, 64 * 1024, 1024**2, 16 * 1024**2, 192 * 1024**2],
        ["4 KiB", "64 KiB", "1 MiB", "16 MiB", "192 MiB"],
    )
    ax.set_xlabel("Mapped working-set span")
    for cache in metadata["caches"]:
        ax.axvline(cache["bytes"], color="#777", ls=":", lw=1)
        ax.text(
            cache["bytes"],
            0.97,
            "L" + str(cache["level"]),
            transform=ax.get_xaxis_transform(),
            ha="right",
            va="top",
            fontsize=9,
        )


def baseline_rows(summary):
    """Select the nominal L1, L2, LLC, and DRAM baseline cases."""
    baselines = [
        select_cases(summary, "working_set", bytes=n, random=1)[0]
        for n in [16 * 1024, 512 * 1024, 8 * 1024**2, 192 * 1024**2]
    ]
    return baselines


def plot_zero_queue(summary, metadata, plot_dir):
    """Plot unloaded pointer-chain latency at four representative sizes."""
    baselines = baseline_rows(summary)
    fig, ax = plt.subplots(figsize=(9, 4.5), layout="constrained")
    y = np.array([case["ns_per_access"] for case in baselines])
    lower = np.array([case["ns_per_access_q25"] for case in baselines])
    upper = np.array([case["ns_per_access_q75"] for case in baselines])
    ax.bar(range(4), y, yerr=[y - lower, upper - y], capsize=4, color=colors[0])
    ax.set_xticks(
        range(4),
        [
            "L1-sized\n16 KiB",
            "L2-sized\n512 KiB",
            "LLC-sized\n8 MiB",
            "DRAM-sized\n192 MiB",
        ],
    )
    ax.set_ylabel("Dependent-load latency (ns)")
    ax.set_title("Unloaded random pointer-chain baseline")
    ax.grid(axis="y", alpha=0.15)
    for i, v in enumerate(y):
        ax.text(i, upper[i] + max(y) * 0.03, f"{v:.2f}", ha="center")
        ax.set_ylim(0, max(upper) * 1.2)
    return save_figure(fig, plot_dir, "01_zero_queue")


def plot_pattern_granularity(summary, metadata, plot_dir):
    """Compare access order, pointer spacing, and useful transfer size."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.7), layout="constrained")
    for order, color in [(0, colors[0]), (1, colors[1])]:
        cases = sorted(
            select_cases(summary, "pattern_latency", random=order),
            key=lambda case: case["spacing"],
        )
        plot_iqr_line(
            axes[0],
            [case["spacing"] for case in cases],
            cases,
            "ns_per_access",
            "Sequential" if order == 0 else "Random",
            color,
        )
        for gap in [1, 4]:
            cases = sorted(
                [
                    case
                    for case in select_cases(summary, "pattern_bandwidth", random=order)
                    if case["spacing"] == gap * case["block"]
                ],
                key=lambda case: case["block"],
            )
            plot_iqr_line(
                axes[1],
                [case["block"] for case in cases],
                cases,
                "gib_s",
                ("Sequential" if order == 0 else "Random")
                + (" · dense" if gap == 1 else " · 4× spacing"),
                color,
                "-" if gap == 1 else "--",
            )
    axes[0].set_xscale("log", base=2)
    axes[0].set_xticks([64, 256, 1024], ["64", "256", "1024"])
    axes[0].set_xlabel("Pointer spacing (bytes)")
    axes[0].set_ylabel("Dependent-load latency (ns)")
    axes[0].set_title("96 MiB pointer chain")
    axes[0].legend(frameon=False)
    axes[1].set_xscale("log", base=2)
    axes[1].set_xticks([8, 64, 256, 1024], ["8", "64", "256", "1024"])
    axes[1].set_xlabel("Useful bytes per transfer")
    axes[1].set_ylabel("Useful bandwidth (GiB/s)")
    axes[1].set_title("96 MiB transfer sweep")
    axes[1].legend(frameon=False, fontsize=9)
    return save_figure(fig, plot_dir, "02_pattern_granularity")


def plot_read_write_mix(summary, metadata, plot_dir):
    """Compare useful bandwidth and average processing time by read/write mix."""
    ratios = sorted({case["read_pct"] for case in summary if case["study"] == "mix"}, reverse=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
    for ax, metric, label in zip(
        axes,
        ["gib_s", "ns_per_access"],
        ["Useful bandwidth (GiB/s)", "Average block processing time (ns)"],
    ):
        for order, color in [(0, colors[0]), (1, colors[1])]:
            cases = [
                select_cases(summary, "mix", read_pct=r, random=order)[0]
                for r in ratios
            ]
            plot_iqr_line(
                ax,
                [100-r for r in ratios],
                cases,
                metric,
                "Sequential" if order == 0 else "Random",
                color,
            )
        ax.set_xticks([100-r for r in ratios], [f"{r}/{100-r}" for r in ratios])
        ax.tick_params(axis="x", labelsize=9)
        ax.set_xlabel("Read/write ratio (%)")
        ax.set_ylabel(label)
        ax.set_ylim(bottom=0)
        ax.legend(frameon=False)
    fig.suptitle("Read/write mix · 96 MiB · 1 KiB transfers")
    return save_figure(fig, plot_dir, "03_read_write_mix")


def plot_intensity(summary, metadata, plot_dir):
    """Show throughput and derived chain latency against measured concurrency."""
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    for column, (study, param, title, xlabel) in enumerate([
        ("intensity_threads", "threads", "Separate physical cores", "Threads (one chain per thread)"),
        ("intensity_streams", "streams", "Independent chains on one core", "Independent chains"),
    ]):
        cases = sorted(select_cases(summary, study), key=lambda case: case[param])
        x = [case[param] for case in cases]
        for row, (metric, ylabel) in enumerate([
            ("million_accesses_s", "Completed dependent loads (million/s)"),
            ("chain_latency_ns", "Mean chain round-trip time (ns)"),
        ]):
            ax = axes[row, column]
            plot_iqr_line(ax, x, cases, metric, "Median; band: interquartile range", colors[column])
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.set_ylim(bottom=0)
            ax.grid(alpha=0.18)
            ax.set_xticks(x if column == 0 else [1, 8, 16, 24, 32, 40, 48, 56, 64])
        axes[0, column].set_title(title)
    fig.suptitle("Intensity sweep · 96 MiB per worker · random dependent loads")
    return save_figure(fig, plot_dir, "04_intensity")


def plot_working_set(summary, metadata, plot_dir):
    """Plot latency and throughput across nominal cache capacities."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.7), layout="constrained")
    for order, color in [(0, colors[0]), (1, colors[1])]:
        cases = select_cases(summary, "working_set", random=order)
        for ax, metric, label in zip(
            axes,
            ["ns_per_access", "million_accesses_s"],
            ["Dependent-load latency (ns)", "Completed dependent loads (million/s)"],
        ):
            plot_iqr_line(
                ax,
                [case["bytes"] for case in cases],
                cases,
                metric,
                "Sequential" if order == 0 else "Random",
                color,
            )
            annotate_caches(ax, metadata)
            ax.set_ylabel(label)
            ax.legend(frameon=False)
    return save_figure(fig, plot_dir, "05_working_set")


def plot_cache_misses(summary, metadata, plot_dir):
    """Pair timing with measured LLC misses, or explain unavailable counters."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.7), layout="constrained")
    cases = select_cases(summary, "working_set", random=1)
    plot_iqr_line(
        axes[0],
        [case["bytes"] for case in cases],
        cases,
        "ns_per_access",
        "Random chain",
        colors[0],
    )
    annotate_caches(axes[0], metadata)
    axes[0].set_ylabel("Dependent-load latency (ns)")
    axes[0].set_title("Measured runtime impact")
    if all((case["counters_available"] for case in cases)):
        plot_iqr_line(
            axes[1],
            [case["bytes"] for case in cases],
            cases,
            "llc_misses_per_1000",
            "LLC read misses",
            colors[1],
        )
        annotate_caches(axes[1], metadata)
        axes[1].set_ylabel("LLC read misses / 1,000 loads")
    else:
        axes[1].axis("off")
        axes[1].text(
            0.5,
            0.5,
            "Counter correlation unavailable\n\nperf_event_open was denied or the group\ncould not run without multiplexing.\nTiming alone does not establish cache misses.",
            ha="center",
            va="center",
            transform=axes[1].transAxes,
        )
    return save_figure(fig, plot_dir, "06_cache_miss_impact")


def plot_page_locality(summary, metadata, plot_dir):
    """Compare normal pages with verified or incomplete huge-page backing."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.7), layout="constrained")
    for ax, order in zip(axes, [0, 1]):
        for huge, color in [(0, colors[0]), (1, colors[1])]:
            cases = select_cases(summary, "tlb", random=order, huge=huge)
            label = (
                "4 KiB pages"
                if not huge
                else (
                    "Verified THP backing"
                    if all((case["huge_verified"] for case in cases))
                    else "THP requested; backing incomplete"
                )
            )
            plot_iqr_line(
                ax,
                [case["bytes"] / 1024**2 for case in cases],
                cases,
                "ns_per_access",
                label,
                color,
            )
        ax.set_xscale("log", base=2)
        ax.set_xticks([4, 16, 64, 192], ["4", "16", "64", "192"])
        ax.set_xlabel("Mapped span (MiB), one load per 4 KiB")
        ax.set_ylabel("Dependent-load latency (ns)")
        ax.set_title("Sequential pages" if order == 0 else "Random pages")
        ax.legend(frameon=False, fontsize=9)
    return save_figure(fig, plot_dir, "07_tlb_pages")


def plot_cache_reuse(summary, metadata, plot_dir):
    """Show why reused cache-sized buffers cannot measure DRAM bandwidth."""
    fig, ax = plt.subplots(figsize=(8, 4.5), layout="constrained")
    cases = select_cases(summary, "pitfall")
    bandwidth = np.array([case["gib_s"] for case in cases])
    lower = np.array([case["gib_s_q25"] for case in cases])
    upper = np.array([case["gib_s_q75"] for case in cases])
    ax.bar(
        range(2),
        bandwidth,
        color=colors[:2],
        yerr=[bandwidth - lower, upper - bandwidth],
        capsize=4,
    )
    ax.set_xticks([0, 1], ["Reused 32 KiB buffer", "Reused 192 MiB buffer"])
    ax.set_ylabel("Useful read bandwidth (GiB/s)")
    ax.set_title("Pitfall: cache reuse is not DRAM bandwidth")
    ax.grid(axis="y", alpha=0.15)
    return save_figure(fig, plot_dir, "08_cache_reuse_pitfall")


def write_tables(run_dir, metadata, rows, summary, baselines):
    """Write the latency table and explicit counter/page-backing coverage."""
    with (run_dir / "latency_table.csv").open("w") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "regime",
                "span_bytes",
                "latency_ns",
                "q25_ns",
                "q75_ns",
                "cycles_per_load",
            ],
        )
        w.writeheader()
        for label, case in zip(
            ["L1-sized", "L2-sized", "LLC-sized", "DRAM-sized"], baselines
        ):
            w.writerow(
                dict(
                    regime=label,
                    span_bytes=case["bytes"],
                    latency_ns=case["ns_per_access"],
                    q25_ns=case["ns_per_access_q25"],
                    q75_ns=case["ns_per_access_q75"],
                    cycles_per_load=(
                        case["cycles_per_access"]
                        if case["counters_available"]
                        else "unavailable"
                    ),
                )
            )
    coverage = {
        "profile": metadata["profile"],
        "trials": len(rows),
        "configurations": len(summary),
        "correctness": "all passed",
        "hardware_counters": all((case["counters_available"] for case in summary)),
        "huge_pages_verified": all(
            (case["huge_verified"] for case in select_cases(summary, "tlb", huge=1))
        ),
        "missing_required_evidence": [],
    }
    if not coverage["hardware_counters"]:
        coverage["missing_required_evidence"] = [
            "Cache-miss/runtime correlation",
            "TLB-miss/runtime correlation",
            "Core cycles per access",
        ]
    (run_dir / "coverage.json").write_text(json.dumps(coverage, indent=2))
    return coverage


def write_report(
    run_dir, plot_dir, metadata, rows, summary, baselines, figure_names, coverage
):
    """Write an evidence-backed Markdown report linking all generated figures."""
    paragraphs = [
        (
            "# Project 2 pilot results"
            if metadata["profile"] == "quick"
            else "# Project 2 results"
        ),
        (
            f"{len(rows)} validated observations across {len(summary)} configurations. {metadata['trials']} trials per configuration; median and interquartile range. This is a short pilot, not a claim of a stable hardware limit."
            if metadata["profile"] == "quick"
            else f"{len(rows)} validated observations; {metadata['trials']} trials per configuration."
        ),
        "## Unloaded latency baseline",
        "| Nominal regime | Span | Median ns/load |",
        "|---|---:|---:|",
    ]
    for label, case in zip(
        ["L1-sized", "L2-sized", "LLC-sized", "DRAM-sized"], baselines
    ):
        paragraphs.append(
            f"| {label} | {case['bytes'] / 1024:g} KiB | {case['ns_per_access']:.2f} |"
        )
    paragraphs += [
        "",
        "The labels refer to nominal cache capacities. Sequential prefetching, software overhead, page translation and other machine activity also affect observed latency. No core-cycle conversion is invented when counters are inaccessible.",
        "## Required figures",
    ]
    labels = [
        "Zero-queue approximation: unloaded dependent-load baseline",
        "Pattern and transfer-granularity sweep",
        "Read/write mix sweep",
        "Intensity: throughput versus chain latency",
        "Working-set sweep across cache capacities",
        "Cache-miss impact: timing plus counter availability",
        "Page locality and verified huge pages",
        "Pitfall: warm cache mistaken for DRAM bandwidth",
    ]
    for file, label in zip(figure_names, labels):
        paragraphs += [
            "### " + label,
            f"![{label}]({(plot_dir / (file + '.png')).resolve()})",
            "",
        ]
    intensity = sorted(
        select_cases(summary, "intensity_streams"), key=lambda x: x["streams"]
    )
    small, large = select_cases(summary, "pitfall")
    paragraphs += [
        "## Observations",
        f"The small reused buffer measured {small['gib_s']:.2f} GiB/s versus {large['gib_s']:.2f} GiB/s for the 192 MiB buffer, a {small['gib_s'] / large['gib_s']:.1f}× difference. The small-buffer result is cache bandwidth, not DRAM bandwidth.",
        f"Across {intensity[0]['streams']} to {intensity[-1]['streams']} independent chains, throughput increased from {intensity[0]['million_accesses_s']:.2f} to {intensity[-1]['million_accesses_s']:.2f} million loads/s, while mean chain round-trip time changed from {intensity[0]['chain_latency_ns']:.2f} to {intensity[-1]['chain_latency_ns']:.2f} ns. The tested pilot range does not by itself establish a stable saturation knee.",
    ]
    paragraphs += [
        "## Interpretation and limits",
        f"Huge-page backing verified for all THP cases: **{coverage['huge_pages_verified']}**. Hardware counters available throughout: **{coverage['hardware_counters']}**.",
        "The cache/TLB studies include measured timing, but a denied counter means the required miss correlation remains open. No missing counter is rendered as a zero.",
        "Bandwidth counts useful payload, not actual DRAM bus traffic. Average block processing time in the mix study is not an individual memory-request latency.",
        "For the intensity sweep, throughput × mean chain round-trip time estimates the number of software-active chains. This is a consistency check of the software concurrency, not an independent estimate of hardware MSHR occupancy. A short pilot may not exhibit a definitive saturation knee.",
        "The page-locality sweep holds one data access per 4 KiB of mapped span; its touched cache-line footprint is smaller than its virtual span. THP can change translation locality without requiring a whole-span data working set.",
        "## Reproduction",
        "Run `make full`, then use the plotting command in the project README. Raw CSVs, processed tables, run metadata, source snapshots and SHA-256 are retained beside these figures.",
        "## AI-use note",
        "Codex assisted with this C harness, acquisition/plotting scripts and setup documentation. Pointer-ring uniqueness, bounds, data checksums, writes, and input rejection were exercised. Counter results and huge-page backing are checked rather than assumed.",
    ]
    (run_dir / "REPORT.md").write_text(
        "\n\n".join(paragraphs).replace("|\n\n|", "|\n|")
    )
    print(json.dumps(coverage, indent=2))
    print(run_dir / "REPORT.md")


def main():
    """Read one recorded run and generate its summaries, figures, and report."""
    run_dir = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else ROOT / "output" / (ROOT / "output/LATEST").read_text().strip()
    )
    plot_dir = run_dir / "plots"
    plot_dir.mkdir(exist_ok=True)
    metadata = json.loads((run_dir / "metadata.json").read_text())
    with (run_dir / "raw.csv").open() as source:
        rows = list(csv.DictReader(source))
    summary = summarize_rows(rows, metadata)
    with (run_dir / "summary.csv").open("w") as output:
        writer = csv.DictWriter(output, fieldnames=summary[0])
        writer.writeheader()
        writer.writerows(summary)
    renderers = [
        plot_zero_queue,
        plot_pattern_granularity,
        plot_read_write_mix,
        plot_intensity,
        plot_working_set,
        plot_cache_misses,
        plot_page_locality,
        plot_cache_reuse,
    ]
    figure_names = [render(summary, metadata, plot_dir) for render in renderers]
    baselines = baseline_rows(summary)
    coverage = write_tables(run_dir, metadata, rows, summary, baselines)
    write_report(
        run_dir, plot_dir, metadata, rows, summary, baselines, figure_names, coverage
    )


if __name__ == "__main__":
    main()
