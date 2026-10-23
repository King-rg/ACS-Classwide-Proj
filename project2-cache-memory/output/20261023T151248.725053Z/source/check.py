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
    # Explicit warm mode remains compatible; prepared modes reject incompatible input
    # before opening counters or making measurements.
    warm_case=["latency","32768","64","8","100","1","0","1","2",cpu,"warm"]
    assert json.loads(subprocess.check_output([str(executable),*warm_case],text=True))["check"]=="pass"
    base=["latency","8388608","64","8","100","1","0","1","2",cpu]
    invalid_prepared=[base+["unknown"],base+["l3-resident"],base+["l3-resident","1048576"],
                      base+["cache-flushed","2097152"],base+["warm","2097152"]]
    for index,value in [(0,"bandwidth"),(1,"4194304"),(2,"128"),(3,"16"),(4,"70"),
                        (5,"0"),(6,"1"),(7,"2"),(9,cpu+","+cpu)]:
        case=base.copy();case[index]=value
        invalid_prepared.append(case+["cache-flushed"])
    for case in invalid_prepared:
        result=subprocess.run([str(executable),*case],capture_output=True)
        assert result.returncode!=0,case
    print(f"Explicit warm compatibility and {len(invalid_prepared)} invalid preparation cases passed.")
    invalid_result = subprocess.run(
        [str(executable), "latency", "4096", "0", "8", "100", "1", "0", "1", "2", cpu],
        capture_output=True,
    )
    assert invalid_result.returncode != 0
    print(f"{len(cases)} correctness cases passed; invalid input rejected.")


if __name__ == "__main__":
    main()
