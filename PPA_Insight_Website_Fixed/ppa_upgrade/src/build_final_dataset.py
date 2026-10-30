
import csv
import json
from pathlib import Path

# ============================================================
# RTL-INSIGHT: FINAL DATASET BUILDER
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_ROOT / "dataset"

PPA_FILE = DATASET_DIR / "ppa_results.csv"
RTL_FEATURES_FILE = DATASET_DIR / "rtl_features.csv"
BENCHMARK_FEATURES_FILE = DATASET_DIR / "benchmark_features.csv"
YOSYS_CELL_FILE = DATASET_DIR / "yosys_cell_statistics.csv"
YOSYS_RESULTS_FILE = DATASET_DIR / "benchmark_results.csv"

OUTPUT_FILE = DATASET_DIR / "final_merged_dataset.csv"

PPA_METRICS = [
    "Target_Clock_ns",
    "WNS_ns",
    "TNS_ns",
    "Estimated_Total_Power_W",
    "LUTs",
    "Registers",
    "DSPs",
]

# Source-level feature names are standardized here.
# RTL register declarations are kept separate from Vivado Registers.
FEATURE_ALIASES = {
    "modules": "RTL_Modules",
    "module": "RTL_Modules",

    "registers": "RTL_Register_Declarations",
    "wires": "RTL_Wire_Declarations",
    "wire_declarations": "RTL_Wire_Declarations",

    "multipliers": "RTL_Multiplication_Operators",
    "multiplication_operators": "RTL_Multiplication_Operators",

    "adders": "RTL_Addition_Operators",
    "addition_operators": "RTL_Addition_Operators",

    "subtractors": "RTL_Subtraction_Operators",
    "subtraction_operators": "RTL_Subtraction_Operators",

    "always_blocks": "RTL_Always_Blocks",
    "case_blocks": "RTL_Case_Blocks",
    "if_statements": "RTL_If_Statements",
    "else_statements": "RTL_Else_Statements",
    "assign_statements": "RTL_Assign_Statements",

    "data_width": "RTL_Data_Width",
    "output_width": "RTL_Output_Width",

    "has_clock": "RTL_Has_Clock",
    "has_reset": "RTL_Has_Reset",
    "has_enable": "RTL_Has_Enable",
}


def read_csv(path):
    """Read a CSV safely, preserving blank values."""

    if not path.exists():
        print(f"WARNING: {path.name} not found.")
        return []

    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(
            line for line in file if line.strip()
        )

        if not reader.fieldnames:
            return []

        rows = []

        for row in reader:
            cleaned = {}

            for key, value in row.items():
                if key is None:
                    continue

                cleaned[key.strip()] = (
                    value.strip() if value is not None else ""
                )

            if any(value != "" for value in cleaned.values()):
                rows.append(cleaned)

        return rows


def normalize_key(value):
    return value.strip().lower().replace(" ", "_")


def get_design(row):
    """Support common design-name column variations."""

    for key, value in row.items():
        if normalize_key(key) in {
            "design",
            "module",
            "module_name",
            "design_name",
        }:
            if value:
                return value.strip()

    return ""


def load_unique_rows(path):
    """Index rows by design, warning about duplicates."""

    result = {}

    for row in read_csv(path):
        design = get_design(row)

        if not design:
            print(f"WARNING: Row without design in {path.name}")
            continue

        if design in result:
            print(
                f"WARNING: Duplicate {design} in {path.name}; "
                "keeping the latest row."
            )

        result[design] = row

    return result


def canonical_feature_name(column):
    """Map feature headers to a consistent schema."""

    key = normalize_key(column)

    if key == "design":
        return None

    return FEATURE_ALIASES.get(key, "RTL_" + key)


def load_features():
    """Merge and standardize both RTL feature sources."""

    features = {}

    sources = [
        RTL_FEATURES_FILE,
        BENCHMARK_FEATURES_FILE,
    ]

    for path in sources:
        for row in load_unique_rows(path).values():
            design = get_design(row)
            target = features.setdefault(design, {})

            for column, value in row.items():
                canonical = canonical_feature_name(column)

                if canonical is None or value == "":
                    continue

                # Preserve an existing nonblank value.
                # If sources disagree, report it rather than silently
                # overwriting the earlier value.
                if (
                    canonical in target
                    and target[canonical] != ""
                    and target[canonical] != value
                ):
                    print(
                        f"WARNING: Feature conflict for {design}, "
                        f"{canonical}: {target[canonical]} vs {value}"
                    )
                    continue

                target[canonical] = value

    return features


def parse_cell_types(value):
    """Parse the JSON Cell_Types field from benchmark_results.csv."""

    if not value:
        return {}

    try:
        parsed = json.loads(value)

        if isinstance(parsed, dict):
            return parsed

    except (json.JSONDecodeError, TypeError):
        print("WARNING: Could not parse a Yosys Cell_Types value.")

    return {}


def load_yosys():
    """Return per-design cell counts and synthesis summaries."""

    cell_counts = {}
    synthesis_info = {}

    # Individual cell statistics, when present.
    for row in read_csv(YOSYS_CELL_FILE):
        design = get_design(row)

        if not design:
            continue

        normalized = {
            normalize_key(key): value
            for key, value in row.items()
        }

        cell_type = normalized.get("cell_type", "")
        count_text = normalized.get("count", "")

        if not cell_type or count_text == "":
            continue

        try:
            count = int(float(count_text))
        except ValueError:
            print(f"WARNING: Invalid cell count for {design}.")
            continue

        cell_counts.setdefault(design, {})[cell_type] = count

    # Aggregate synthesis summaries and JSON cell dictionaries.
    for row in read_csv(YOSYS_RESULTS_FILE):
        design = get_design(row)

        if not design:
            continue

        normalized = {
            normalize_key(key): value
            for key, value in row.items()
        }

        status = normalized.get("status", "")
        count_text = normalized.get("cell_count", "")

        try:
            total_cells = (
                int(float(count_text)) if count_text != "" else ""
            )
        except ValueError:
            total_cells = ""

        synthesis_info[design] = {
            "Yosys_Synthesis_Status": status,
            "Yosys_Synthesized_Cell_Count": total_cells,
        }

        parsed = parse_cell_types(
            normalized.get("cell_types", "")
        )

        # The aggregate JSON provides a complete cell-type summary
        # for that design. Use it when available.
        if parsed:
            cell_counts[design] = {
                str(cell_type): int(count)
                for cell_type, count in parsed.items()
            }

    return cell_counts, synthesis_info


def is_present(value):
    return value is not None and str(value).strip() != ""


def main():
    print("=" * 60)
    print("RTL-INSIGHT FINAL DATASET BUILDER")
    print("=" * 60)

    # 1. Load original PPA/resource records.
    ppa_rows = load_unique_rows(PPA_FILE)

    if not ppa_rows:
        raise ValueError("No designs found in ppa_results.csv")

    print(f"PPA source designs: {len(ppa_rows)}")

    # 2. Load standardized source-level features.
    features = load_features()
    print(f"Designs with RTL features: {len(features)}")

    # 3. Load Yosys statistics.
    cell_counts, synthesis_info = load_yosys()
    print(f"Designs with Yosys cell counts: {len(cell_counts)}")

    # 4. Retain designs from every source.
    designs = sorted(
        set(ppa_rows)
        | set(features)
        | set(cell_counts)
        | set(synthesis_info)
    )

    merged_rows = []

    for design in designs:
        row = {"Design": design}
        ppa = ppa_rows.get(design, {})

        # Preserve PPA-source fields and their values.
        for column, value in ppa.items():
            if normalize_key(column) != "design":
                row[column] = value

        # Metric availability is based on actual nonblank values.
        row["PPA_Record_Available"] = (
            "Yes" if design in ppa_rows else "No"
        )

        row["Timing_Available"] = (
            "Yes"
            if all(
                is_present(ppa.get(metric, ""))
                for metric in [
                    "Target_Clock_ns",
                    "WNS_ns",
                    "TNS_ns",
                ]
            )
            else "No"
        )

        row["Power_Available"] = (
            "Yes"
            if is_present(ppa.get("Estimated_Total_Power_W", ""))
            else "No"
        )

        row["Utilization_Available"] = (
            "Yes"
            if all(
                is_present(ppa.get(metric, ""))
                for metric in ["LUTs", "Registers", "DSPs"]
            )
            else "No"
        )

        # Compatibility flag: Yes means at least one PPA metric
        # is populated, not that every metric is available.
        row["PPA_Available"] = (
            "Yes"
            if any(
                is_present(ppa.get(metric, ""))
                for metric in PPA_METRICS
            )
            else "No"
        )

        # Standardized RTL features.
        design_features = features.get(design, {})

        for column, value in design_features.items():
            if column not in row or not is_present(row[column]):
                row[column] = value

        row["Features_Available"] = (
            "Yes" if design_features else "No"
        )

        # Yosys cell types are separate from Vivado utilization.
        design_cells = cell_counts.get(design, {})

        for cell_type, count in sorted(design_cells.items()):
            safe_cell_type = "".join(
                char if char.isalnum() else "_"
                for char in str(cell_type)
            )
            row[f"Yosys_{safe_cell_type}_Count"] = count

        row["Yosys_Cell_Statistics_Available"] = (
            "Yes" if design_cells else "No"
        )

        info = synthesis_info.get(design, {})

        row["Yosys_Synthesis_Status"] = info.get(
            "Yosys_Synthesis_Status", ""
        )
        row["Yosys_Synthesized_Cell_Count"] = info.get(
            "Yosys_Synthesized_Cell_Count", ""
        )

        merged_rows.append(row)

    # 5. Create a stable column order.
    first_columns = [
        "Design",
        "Tool",
        "Target_Clock_ns",
        "WNS_ns",
        "TNS_ns",
        "Estimated_Total_Power_W",
        "LUTs",
        "Registers",
        "DSPs",
        "PPA_Record_Available",
        "PPA_Available",
        "Timing_Available",
        "Power_Available",
        "Utilization_Available",
        "Features_Available",
    ]

    all_columns = set()

    for row in merged_rows:
        all_columns.update(row.keys())

    fieldnames = [
        column for column in first_columns if column in all_columns
    ]
    fieldnames += sorted(all_columns - set(fieldnames))

    # Only the final merged output is overwritten.
    with OUTPUT_FILE.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(merged_rows)

    print("\n" + "=" * 60)
    print("DATASET BUILD COMPLETED")
    print("=" * 60)
    print(f"Total designs: {len(merged_rows)}")
    print(f"Total columns: {len(fieldnames)}")
    print(f"Output: {OUTPUT_FILE}")

    for row in merged_rows:
        print(
            f"{row['Design']}: "
            f"timing={row['Timing_Available']}, "
            f"power={row['Power_Available']}, "
            f"utilization={row['Utilization_Available']}, "
            f"features={row['Features_Available']}, "
            f"Yosys={row['Yosys_Synthesis_Status'] or 'Unavailable'}"
        )

    print("\nOriginal source CSV files were not modified.")
    print("Missing measurements remain blank.")
    print("RTL features and Yosys statistics remain separate.")
    print("No model training was performed.")


if __name__ == "__main__":
    main()
