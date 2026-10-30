"""Portable command-line Yosys synthesis wrapper used by PPA-Insight.

Example:
    python src/yosys_analyzer.py --rtl examples/counter8.v --top counter8
Set YOSYS_BIN or add Yosys to PATH when it is not automatically detected.
"""
from __future__ import annotations
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from synthesis_engine import parse_rtl_modules, run_yosys


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthesize RTL using Yosys and export cell evidence.")
    parser.add_argument("--rtl", default=str(ROOT / "examples" / "counter8.v"), help="Path to a Verilog/SystemVerilog source file")
    parser.add_argument("--top", default=None, help="Top module (defaults to first detected module)")
    parser.add_argument("--target", choices=["generic", "xc7"], default="generic", help="Synthesis target")
    args = parser.parse_args()
    rtl_path = Path(args.rtl).expanduser().resolve()
    if not rtl_path.is_file():
        parser.error(f"RTL file not found: {rtl_path}")
    source = rtl_path.read_text(encoding="utf-8", errors="replace")
    top = args.top or next(iter(parse_rtl_modules(source)), None)
    if not top:
        parser.error("No module declaration detected; supply valid RTL.")
    target = "Xilinx 7-series (xc7)" if args.target == "xc7" else "Generic synthesis"
    try:
        result = run_yosys(source, top, target)
    except Exception as exc:
        print(f"Synthesis failed: {exc}", file=sys.stderr)
        return 1
    report_dir = ROOT / "reports"
    dataset_dir = ROOT / "dataset"
    report_dir.mkdir(parents=True, exist_ok=True)
    dataset_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = report_dir / f"{rtl_path.stem}_yosys_evidence.json"
    evidence_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    cells_path = dataset_dir / f"{rtl_path.stem}_yosys_cells.csv"
    with cells_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Design", "Tool", "Target", "Cell_Type", "Count"])
        writer.writeheader()
        for cell in result["cell_breakdown"]:
            writer.writerow({"Design": rtl_path.stem, "Tool": "Yosys", "Target": target, "Cell_Type": cell["Cell type"], "Count": cell["Count"]})
    print(f"Status: {result['status']}\nTop module: {top}\nTarget: {target}\nVersion: {result['version']}")
    for metric, value in result["metrics"].items():
        print(f"{metric}: {'not available' if value is None else value}")
    print(f"Evidence JSON: {evidence_path}\nCell CSV: {cells_path}")
    print(result["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
