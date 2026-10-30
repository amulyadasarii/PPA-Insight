
import csv
import json
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
BENCHMARK_DIR = PROJECT_DIR / "rtl" / "benchmarks"
REPORT_DIR = PROJECT_DIR / "reports"
DATASET_DIR = PROJECT_DIR / "dataset"

SUITE_DIR = Path(
    r"C:\Users\Admin\Downloads\oss-cad-suite-windows-x64-20261009"
    r"\oss-cad-suite"
)
YOSYS_EXE = SUITE_DIR / "bin" / "yosys.exe"
print("Yosys executable:", YOSYS_EXE)
print("Executable exists:", YOSYS_EXE.is_file())

RESULTS_CSV = DATASET_DIR / "benchmark_results.csv"


def run_benchmark(rtl_file):
    design = rtl_file.stem
    script_file = REPORT_DIR / f"{design}_benchmark.ys"
    log_file = REPORT_DIR / f"{design}_benchmark.log"
    json_file = REPORT_DIR / f"{design}_benchmark.json"

    script = "\n".join([
        f'read_verilog "{rtl_file.as_posix()}"',
        f"hierarchy -check -top {design}",
        "proc",
        "opt",
        "check",
        "synth_xilinx -family xc7",
        "stat",
        f'write_json "{json_file.as_posix()}"',
        ""
    ])

    script_file.write_text(script, encoding="utf-8")

    try:
        result = subprocess.run(
            [str(YOSYS_EXE), "-s", str(script_file)],
            cwd=str(SUITE_DIR),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=240
        )

        combined_log = (result.stdout or "") + "\n" + (result.stderr or "")
        log_file.write_text(combined_log, encoding="utf-8")

        if result.returncode != 0 or not json_file.exists():
            return {
                "Design": design,
                "Status": "Failed",
                "Cell_Count": "",
                "Cell_Types": "",
                "Log_File": str(log_file),
                "Error": combined_log[-1500:]
            }

        netlist = json.loads(json_file.read_text(encoding="utf-8"))
        module = netlist.get("modules", {}).get(design)

        if module is None:
            raise ValueError("Top module missing from synthesized netlist.")

        cells = module.get("cells", {})
        counts = {}

        for cell in cells.values():
            cell_type = cell.get("type", "UNKNOWN")
            counts[cell_type] = counts.get(cell_type, 0) + 1

        return {
            "Design": design,
            "Status": "Success",
            "Cell_Count": len(cells),
            "Cell_Types": json.dumps(counts, sort_keys=True),
            "Log_File": str(log_file),
            "Error": ""
        }

    except Exception as error:
        return {
            "Design": design,
            "Status": "Failed",
            "Cell_Count": "",
            "Cell_Types": "",
            "Log_File": str(log_file),
            "Error": str(error)
        }


def main():
    print("=" * 48)
    print("RTL-INSIGHT AUTOMATED BENCHMARK RUNNER")
    print("=" * 48)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    if not YOSYS_EXE.is_file():
        print("ERROR: Yosys executable not found:")
        print(YOSYS_EXE)
        return

    rtl_files = sorted(BENCHMARK_DIR.glob("*.v"))

    if not rtl_files:
        print("ERROR: No .v files found in:", BENCHMARK_DIR)
        return

    results = []

    for rtl_file in rtl_files:
        print(f"\nSynthesizing {rtl_file.name}...")
        row = run_benchmark(rtl_file)
        results.append(row)
        print("Status:", row["Status"])

        if row["Status"] == "Success":
            print("Synthesized cells:", row["Cell_Count"])
        else:
            print("Error:", row["Error"][-500:])

    columns = [
        "Design", "Status", "Cell_Count",
        "Cell_Types", "Log_File", "Error"
    ]

    with RESULTS_CSV.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(results)

    successful = sum(r["Status"] == "Success" for r in results)

    print("\nResults saved to:", RESULTS_CSV)
    print("Successful:", successful)
    print("Failed:", len(results) - successful)
    print("\nCell counts are synthesis statistics, not PPA labels.")


if __name__ == "__main__":
    main()
