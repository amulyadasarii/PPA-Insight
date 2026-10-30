import re
import csv
from pathlib import Path


# =========================================================
# RTL-INSIGHT
# RTL Feature Extraction Engine
# =========================================================

RTL_FILE = Path(__file__).parent.parent / "rtl" / "mac_unit.v"
DATASET_FILE = Path(__file__).parent.parent / "dataset" / "rtl_features.csv"


def extract_features(rtl_code):

    features = {}

    # -----------------------------------------------------
    # 1. Number of modules
    # -----------------------------------------------------
    features["modules"] = len(
        re.findall(r"\bmodule\s+\w+", rtl_code)
    )

    # -----------------------------------------------------
    # 2. Number of registers
    # Includes output reg and internal reg declarations
    # -----------------------------------------------------
    register_matches = re.findall(
        r"\b(?:input|output)?\s*reg\s+(?:\[[^\]]+\]\s*)?(\w+)",
        rtl_code
    )

    features["registers"] = len(register_matches)

    # -----------------------------------------------------
    # 3. Number of wires
    # -----------------------------------------------------
    wire_matches = re.findall(
        r"\bwire\s+(?:\[[^\]]+\]\s*)?[\w,\s]+;",
        rtl_code
    )

    wire_count = 0

    for declaration in wire_matches:

        declaration = declaration.replace("wire", "")
        declaration = declaration.replace(";", "")

        names = declaration.strip().split(",")

        wire_count += len(names)

    features["wires"] = wire_count

    # -----------------------------------------------------
    # 4. Number of multipliers
    # -----------------------------------------------------
    multiplier_matches = re.findall(
        r"\b[A-Za-z_]\w*\s*\*\s*[A-Za-z_]\w*",
        rtl_code
    )

    features["multipliers"] = len(multiplier_matches)

    # -----------------------------------------------------
    # 5. Number of adders
    # -----------------------------------------------------
    adder_matches = re.findall(
        r"\b[A-Za-z_]\w*\s*\+\s*[A-Za-z_]\w*",
        rtl_code
    )

    features["adders"] = len(adder_matches)

    # -----------------------------------------------------
    # 6. Number of subtractors
    # Ignores WIDTH-1 expressions
    # -----------------------------------------------------
    subtractor_matches = re.findall(
        r"\b[A-Za-z_]\w*\s*-\s*[A-Za-z_]\w*",
        rtl_code
    )

    features["subtractors"] = len(subtractor_matches)

    # -----------------------------------------------------
    # 7. Number of always blocks
    # -----------------------------------------------------
    features["always_blocks"] = len(
        re.findall(r"\balways\s*@\s*\(", rtl_code)
    )

    # -----------------------------------------------------
    # 8. Number of assign statements
    # -----------------------------------------------------
    features["assign_statements"] = len(
        re.findall(r"\bassign\b", rtl_code)
    )

    # -----------------------------------------------------
    # 9. Number of if statements
    # -----------------------------------------------------
    features["if_statements"] = len(
        re.findall(r"\bif\s*\(", rtl_code)
    )

    # -----------------------------------------------------
    # 10. Number of else statements
    # -----------------------------------------------------
    features["else_statements"] = len(
        re.findall(r"\belse\b", rtl_code)
    )

    # -----------------------------------------------------
    # 11. Detect parameter WIDTH
    # -----------------------------------------------------
    width_match = re.search(
        r"parameter\s+WIDTH\s*=\s*(\d+)",
        rtl_code
    )

    if width_match:
        features["data_width"] = int(width_match.group(1))
    else:
        features["data_width"] = 0

    # -----------------------------------------------------
    # 12. Detect output width
    # -----------------------------------------------------
    output_width_match = re.search(
        r"output\s+reg\s+\[\s*2\s*\*\s*WIDTH\s*-\s*1\s*:\s*0\s*\]",
        rtl_code
    )

    if output_width_match:
        features["output_width"] = features["data_width"] * 2
    else:
        features["output_width"] = 0

    # -----------------------------------------------------
    # 13. Detect clock
    # -----------------------------------------------------
    features["has_clock"] = int(
        bool(re.search(r"\bclk\b", rtl_code))
    )

    # -----------------------------------------------------
    # 14. Detect reset
    # -----------------------------------------------------
    features["has_reset"] = int(
        bool(re.search(r"\breset\b", rtl_code))
    )

    # -----------------------------------------------------
    # 15. Detect enable
    # -----------------------------------------------------
    features["has_enable"] = int(
        bool(re.search(r"\benable\b", rtl_code))
    )

    return features


def save_features(features):

    DATASET_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(DATASET_FILE, "w", newline="") as file:

        writer = csv.writer(file)

        writer.writerow(
            ["Design"] + list(features.keys())
        )

        writer.writerow(
            [RTL_FILE.stem] + list(features.values())
        )


def main():

    print("====================================")
    print("       RTL-INSIGHT FEATURE REPORT")
    print("====================================")

    if not RTL_FILE.exists():

        print("ERROR: mac_unit.v was not found.")
        return

    # Read the actual Verilog RTL
    rtl_code = RTL_FILE.read_text()

    # Extract features
    features = extract_features(rtl_code)

    print()
    print("RTL Design:", RTL_FILE.name)
    print()

    for feature, value in features.items():

        print(f"{feature:20}: {value}")

    # Save extracted features
    save_features(features)

    print()
    print("Feature data saved successfully!")
    print("Dataset file:", DATASET_FILE)


if __name__ == "__main__":
    main()