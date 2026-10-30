
import csv
import math
from pathlib import Path

# ============================================================
# RTL-INSIGHT DATASET VALIDATOR
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_DIR / "dataset"

PPA_FILE = DATASET_DIR / "ppa_results.csv"
RTL_FEATURES_FILE = DATASET_DIR / "rtl_features.csv"
BENCHMARK_FEATURES_FILE = DATASET_DIR / "benchmark_features.csv"
FINAL_DATASET_FILE = DATASET_DIR / "final_merged_dataset.csv"

PPA_NUMERIC_COLUMNS = [
    "Target_Clock_ns",
    "WNS_ns",
    "TNS_ns",
    "Estimated_Total_Power_W",
    "LUTs",
    "Registers",
    "DSPs",
]

INTEGER_COLUMNS = {"LUTs", "Registers", "DSPs"}


def read_csv(path):
    """Read CSV rows, ignoring blank lines and UTF-8 BOMs."""
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", newline="", encoding="utf-8-sig") as file:
        lines = (line for line in file if line.strip())
        reader = csv.DictReader(lines)

        if not reader.fieldnames:
            raise ValueError(f"CSV header is missing: {path.name}")

        reader.fieldnames = [
            name.strip().lstrip("\ufeff") if name else ""
            for name in reader.fieldnames
        ]

        rows = []
        for row in reader:
            cleaned = {}
            for key, value in row.items():
                if key is not None:
                    cleaned[key.strip()] = (
                        value.strip() if value is not None else ""
                    )
            if any(cleaned.values()):
                rows.append(cleaned)

        return rows


def get_design(row):
    """Extract a design name from a CSV row."""
    for key in (
        "Design", "design", "Module", "module",
        "Module_Name", "Design_Name"
    ):
        value = row.get(key, "")
        if value:
            return value.strip()
    return ""


def design_names(rows):
    return [get_design(row) for row in rows if get_design(row)]


def main():
    print("=" * 55)
    print("RTL-INSIGHT DATASET VALIDATOR")
    print("=" * 55)

    required_files = [
        PPA_FILE,
        RTL_FEATURES_FILE,
        BENCHMARK_FEATURES_FILE,
        FINAL_DATASET_FILE,
    ]

    for path in required_files:
        if not path.is_file():
            print(f"\nERROR: Missing file: {path}")
            return

    try:
        ppa_rows = read_csv(PPA_FILE)
        rtl_rows = read_csv(RTL_FEATURES_FILE)
        benchmark_rows = read_csv(BENCHMARK_FEATURES_FILE)
        final_rows = read_csv(FINAL_DATASET_FILE)
    except (OSError, ValueError, csv.Error) as error:
        print(f"\nERROR reading CSV: {error}")
        return

    print("\nInput dataset counts:")
    print(f"PPA records              : {len(ppa_rows)}")
    print(f"RTL feature records      : {len(rtl_rows)}")
    print(f"Benchmark feature records: {len(benchmark_rows)}")
    print(f"Final merged records     : {len(final_rows)}")

    errors = []
    warnings = []

    # --------------------------------------------------------
    # 1. Validate supplied PPA records without changing them.
    # --------------------------------------------------------

    required_columns = [
        "Design", "Tool", *PPA_NUMERIC_COLUMNS
    ]

    ppa_headers = set(ppa_rows[0].keys()) if ppa_rows else set()

    for column in required_columns:
        if column not in ppa_headers:
            errors.append(f"ppa_results.csv is missing column: {column}")

    ppa_design_list = design_names(ppa_rows)

    for design in sorted({
        name for name in ppa_design_list
        if ppa_design_list.count(name) > 1
    }):
        errors.append(f"Duplicate design in PPA file: {design}")

    for row_number, row in enumerate(ppa_rows, start=2):
        design = get_design(row) or f"row {row_number}"

        if not get_design(row):
            errors.append(f"Row {row_number}: missing Design name")

        if not row.get("Tool", "").strip():
            errors.append(f"{design}: Tool is missing")

        for column in PPA_NUMERIC_COLUMNS:
            value = row.get(column, "").strip()

            if not value:
                warnings.append(f"{design}: {column} is unavailable")
                continue

            try:
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError
                if column in INTEGER_COLUMNS:
                    if number < 0 or not number.is_integer():
                        errors.append(
                            f"{design}: {column} must be a "
                            "non-negative integer"
                        )
            except ValueError:
                errors.append(
                    f"{design}: invalid numeric value for "
                    f"{column}: {value}"
                )

    if errors:
        print("\nPPA file structure and values: FAIL")
        for error in errors:
            print("-", error)
    else:
        print("\nPPA file structure and supplied values: PASS")

    if warnings:
        print("\nMissing-metric warnings:")
        for warning in warnings:
            print("-", warning)

    # --------------------------------------------------------
    # 2. Compare design names across sources.
    # --------------------------------------------------------

    ppa_designs = set(design_names(ppa_rows))
    rtl_designs = set(design_names(rtl_rows))
    benchmark_designs = set(design_names(benchmark_rows))
    feature_designs = rtl_designs | benchmark_designs
    final_designs = set(design_names(final_rows))

    print("\nDesign matching:")
    print("PPA designs        :", sorted(ppa_designs))
    print("RTL feature designs:", sorted(rtl_designs))
    print("Benchmark designs  :", sorted(benchmark_designs))
    print("Final designs      :", sorted(final_designs))

    unmatched_ppa = ppa_designs - feature_designs
    if unmatched_ppa:
        warnings.append(
            "PPA designs without feature records: "
            + str(sorted(unmatched_ppa))
        )
    else:
        print("PPA-to-feature design matching: PASS")

    missing_final = ppa_designs - final_designs
    extra_final = final_designs - ppa_designs

    if missing_final:
        errors.append(
            "PPA designs missing from final dataset: "
            + str(sorted(missing_final))
        )
    else:
        print("All PPA designs are present in final dataset: PASS")

    # Extra designs are allowed if they have features and/or Yosys
    # results. They must not be treated as having PPA labels.
    if extra_final:
        print(
            "Additional designs without supplied PPA records:",
            sorted(extra_final)
        )

        final_by_name = {
            get_design(row): row
            for row in final_rows
            if get_design(row)
        }

        for design in sorted(extra_final):
            row = final_by_name[design]

            ppa_flag = row.get("PPA_Available", "").strip().lower()
            if ppa_flag and ppa_flag != "no":
                errors.append(
                    f"{design}: PPA_Available must be No "
                    "because no PPA record exists"
                )

            for column in PPA_NUMERIC_COLUMNS:
                if column in row and row[column].strip():
                    errors.append(
                        f"{design}: {column} has a value but no "
                        "corresponding PPA record exists"
                    )
    else:
        print("No additional designs without PPA records.")

    # --------------------------------------------------------
    # 3. Check duplicate design names in all files.
    # --------------------------------------------------------

    print("\nDuplicate-record checks:")

    for label, rows in (
        ("PPA", ppa_rows),
        ("RTL features", rtl_rows),
        ("Benchmark features", benchmark_rows),
        ("Final dataset", final_rows),
    ):
        names = design_names(rows)
        duplicates = sorted({
            name for name in names if names.count(name) > 1
        })

        if duplicates:
            errors.append(f"{label}: duplicate design names {duplicates}")
            print(f"{label}: FAIL — duplicates {duplicates}")
        else:
            print(f"{label}: no duplicate design names")

    # --------------------------------------------------------
    # 4. Final result.
    # --------------------------------------------------------

    print("\n" + "=" * 55)
    print("VALIDATION SUMMARY")
    print("=" * 55)

    if errors:
        print("Result: FAIL — fix the errors above.")
    else:
        print("Result: STRUCTURAL CHECKS PASSED.")
        if warnings:
            print("Warnings remain for unavailable metrics or features.")
        if extra_final:
            print(
                "Unmeasured designs are allowed and are not treated "
                "as PPA-labelled training examples."
            )

    print("\nImportant:")
    print("- Missing measurements remain blank, not zero.")
    print("- Extra designs may have Yosys results but no Vivado PPA.")
    print("- Validation does not guarantee measurement accuracy.")
    print("- Estimated power is not measured hardware power.")
    print("- Three PPA-labelled designs are insufficient for "
          "reliable ML evaluation.")
    print("=" * 55)


if __name__ == "__main__":
    main()
