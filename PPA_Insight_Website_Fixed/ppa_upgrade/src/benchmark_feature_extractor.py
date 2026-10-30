
import csv
import re
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
BENCHMARK_DIR = PROJECT_DIR / "rtl" / "benchmarks"
DATASET_DIR = PROJECT_DIR / "dataset"
OUTPUT_FILE = DATASET_DIR / "benchmark_features.csv"


def remove_comments(code):
    """Remove Verilog comments before extracting source features."""
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)
    return code


def extract_features(path):
    code = remove_comments(path.read_text(encoding="utf-8"))

    module_names = re.findall(r"\bmodule\s+(\w+)", code)

    # Count declared register names, not physical FPGA flip-flops.
    output_regs = re.findall(
        r"\boutput\s+(?:(?:wire|reg|logic)\s+)?"
        r"(?:signed\s+)?(?:\[[^\]]+\]\s*)?(\w+)",
        code,
    )

    reg_declarations = re.findall(
        r"\breg\s+(?:signed\s+)?(?:\[[^\]]+\]\s*)?([^;]+);",
        code,
    )

    declared_regs = set(output_regs)

    for declaration in reg_declarations:
        for name in declaration.split(","):
            name = re.sub(r"\s*=.*", "", name).strip()
            match = re.match(r"(\w+)", name)
            if match:
                declared_regs.add(match.group(1))

    # Count wire names declared in each wire statement.
    wire_declarations = re.findall(
        r"\bwire\s+(?:signed\s+)?(?:\[[^\]]+\]\s*)?([^;]+);",
        code,
    )

    wire_count = 0
    for declaration in wire_declarations:
        wire_count += len(declaration.split(","))

    # Exclude the * used in always @(*) from multiplication counts.
    operator_code = re.sub(r"@\s*\(\s*\*\s*\)", "", code)

    return {
        "Design": path.stem,
        "Modules": len(module_names),
        "Registers": len(declared_regs),
        "Wire_Declarations": wire_count,
        "Multiplication_Operators": len(
            re.findall(r"\*", operator_code)
        ),
        "Addition_Operators": len(re.findall(r"\+", code)),
        "Subtraction_Operators": len(
            re.findall(r"(?<![+\-])-(?![+\-])", code)
        ),
        "Always_Blocks": len(
            re.findall(r"\balways\s*@\s*\(", code)
        ),
        "Case_Blocks": len(re.findall(r"\bcase\s*\(", code)),
        "If_Statements": len(re.findall(r"\bif\s*\(", code)),
        "Assign_Statements": len(re.findall(r"\bassign\b", code)),
        "Has_Clock": int(bool(re.search(r"\bclk\b", code))),
        "Has_Reset": int(bool(re.search(r"\breset\b", code))),
        "Has_Enable": int(bool(re.search(r"\benable\b", code))),
    }


def main():
    files = sorted(BENCHMARK_DIR.glob("*.v"))

    if not files:
        print(
            "ERROR: No Verilog benchmark files found in "
            f"{BENCHMARK_DIR}"
        )
        return

    rows = [extract_features(path) for path in files]
    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = list(rows[0].keys())

    with OUTPUT_FILE.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("=" * 48)
    print("RTL-INSIGHT BENCHMARK FEATURE EXTRACTOR")
    print("=" * 48)

    for row in rows:
        print(
            f"{row['Design']}: "
            f"{row['Modules']} module(s), "
            f"{row['Registers']} declared register name(s), "
            f"{row['Always_Blocks']} always block(s), "
            f"{row['Multiplication_Operators']} multiplication "
            f"operator(s)"
        )

    print("\nDesigns processed:", len(rows))
    print("Saved to:", OUTPUT_FILE)
    print("\nNote: these are preliminary regex-based source features.")


if __name__ == "__main__":
    main()
