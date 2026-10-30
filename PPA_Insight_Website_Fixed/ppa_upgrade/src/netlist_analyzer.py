"""Summarize a PPA-Insight Yosys evidence JSON file into cell statistics CSV."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Export cell counts from a PPA-Insight Yosys evidence JSON.")
    parser.add_argument("evidence", nargs="?", default=None, help="Evidence JSON created by src/yosys_analyzer.py")
    parser.add_argument("--output", default=None, help="Output CSV path")
    args = parser.parse_args()
    candidates = sorted((ROOT / "reports").glob("*_yosys_evidence.json")) if (ROOT / "reports").exists() else []
    evidence_path = Path(args.evidence).expanduser().resolve() if args.evidence else (candidates[-1] if candidates else None)
    if not evidence_path or not evidence_path.is_file():
        parser.error("No evidence JSON found. Run src/yosys_analyzer.py first or pass its JSON path.")
    result = json.loads(evidence_path.read_text(encoding="utf-8"))
    output = Path(args.output).expanduser().resolve() if args.output else ROOT / "dataset" / f"{result.get('top','design')}_yosys_cell_statistics.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Design", "Tool", "Target", "Cell_Type", "Count"])
        writer.writeheader()
        for row in result.get("cell_breakdown", []):
            writer.writerow({"Design": result.get("top", "unknown"), "Tool": "Yosys", "Target": result.get("target", "unknown"), "Cell_Type": row.get("Cell type", "UNKNOWN"), "Count": row.get("Count", 0)})
    print(f"Cell statistics exported to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
