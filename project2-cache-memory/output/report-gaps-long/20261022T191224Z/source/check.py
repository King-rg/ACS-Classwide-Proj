"""Exercise small valid cases and reject invalid benchmark options."""

from pathlib import Path
import subprocess
import json
import os


def main():
    """Check both benchmark modes, access orders, stream counts, and page requests."""
    root = Path(__file__).resolve().parents[1]
    cpu = str(min(os.sched_getaffinity(0)))
    executable = root / "build/memory_bench"
    cases = [
        ["latency", "32768", "64", "8", "100", "1", "0", str(streams), "2", cpu]
        for streams in [1, 2, 8, 64]
    ]
    cases += [
        [
            "bandwidth",
            "65536",
            str(spacing),
            str(block_bytes),
            str(read_percent),
            str(random_order),
            "0",
            "1",
            "2",
            cpu,
        ]
        for spacing, block_bytes in [(64, 8), (256, 64), (1024, 1024)]
        for read_percent in [0, 50, 70, 100]
        for random_order in [0, 1]
    ]
    cases += [
        ["latency", "4194304", "4096", "8", "100", "1", str(huge_pages), "1", "2", cpu]
        for huge_pages in [0, 1]
    ]
    for case in cases:
        result = json.loads(
            subprocess.check_output([str(executable), *case], text=True)
        )
        assert result["check"] == "pass" and result["elapsed_ns"] > 0
        if case[6] == "0":
            assert result["huge_bytes"] == 0
    invalid_result = subprocess.run(
        [str(executable), "latency", "4096", "0", "8", "100", "1", "0", "1", "2", cpu],
        capture_output=True,
    )
    assert invalid_result.returncode != 0
    print(f"{len(cases)} correctness cases passed; invalid input rejected.")


if __name__ == "__main__":
    main()
