
import csv
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_DIR / "dataset"

RTL_CSV = DATASET_DIR / "rtl_features.csv"
CELL_CSV = DATASET_DIR / "yosys_cell_statistics.csv"
OUTPUT_CSV = DATASET_DIR / "unified_design_metrics.csv"


def read_rtl_features():
    """Read RTL feature rows."""
    with open(RTL_CSV, newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    if not rows:
        raise ValueError("rtl_features.csv contains no design rows.")

    return rows


def read_cell_statistics():
    """Read Yosys cell counts separately for each design."""
    counts_by_design = {}

    with open(CELL_CSV, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        required_columns = {"Design", "Cell_Type", "Count"}
        if not reader.fieldnames or not required_columns.issubset(
            set(reader.fieldnames)
        ):
            raise ValueError(
                "yosys_cell_statistics.csv must contain "
                "Design, Cell_Type, and Count columns."
            )

        for row in reader:
            design = row["Design"].strip()
            cell_type = row["Cell_Type"].strip()

            if not design or not cell_type:
                raise ValueError(
                    "Found an empty Design or Cell_Type value "
                    "in yosys_cell_statistics.csv."
                )

            try:
                count = int(row["Count"])
            except (ValueError, TypeError):
                raise ValueError(
                    f"Invalid cell count for {design}, {cell_type}: "
                    f"{row['Count']!r}"
                )

            if count < 0:
                raise ValueError(
                    f"Negative cell count for {design}, {cell_type}."
                )

            design_counts = counts_by_design.setdefault(design, {})
            column_name = f"cell_{cell_type}"

            if column_name in design_counts:
                raise ValueError(
                    f"Duplicate cell statistic for {design}, {cell_type}. "
                    "Aggregate duplicate rows before merging."
                )

            design_counts[column_name] = count

    return counts_by_design


def get_design_name(row):
    """Accept either Design or design as the feature column name."""
    for column in ("Design", "design"):
        if column in row and row[column].strip():
            return row[column].strip()

    raise ValueError(
        "rtl_features.csv must contain a non-empty Design or design column."
    )


def main():
    print("=" * 48)
    print("RTL-INSIGHT UNIFIED METRICS BUILDER")
    print("=" * 48)

    for path in (RTL_CSV, CELL_CSV):
        if not path.is_file():
            print(f"ERROR: Required file not found:\n{path}")
            return

    try:
        rtl_rows = read_rtl_features()
        cell_counts_by_design = read_cell_statistics()

        output_rows = []

        for rtl_row in rtl_rows:
            design = get_design_name(rtl_row)
            combined = dict(rtl_row)

            # Merge only statistics belonging to this design.
            cell_counts = cell_counts_by_design.get(design, {})
            combined.update(cell_counts)

            if design in cell_counts_by_design:
                combined["synthesis_tool"] = "Yosys"
                combined["synthesis_status"] = "Success"
            else:
                combined["synthesis_tool"] = ""
                combined["synthesis_status"] = "Missing cell statistics"

            output_rows.append(combined)

        # Include all fields found in any output row.
        fieldnames = list(
            dict.fromkeys(
                key
                for row in output_rows
                for key in row.keys()
            )
        )

        with open(
            OUTPUT_CSV, "w", newline="", encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames,
                extrasaction="raise"
            )
            writer.writeheader()
            writer.writerows(output_rows)

        print("\nUnified metrics created successfully!")
        print("Design rows:", len(output_rows))
        print("RTL features:", len(rtl_rows[0]))
        print("Designs with Yosys statistics:",
              len(cell_counts_by_design))
        print("Output:", OUTPUT_CSV)

        print("\nPer-design synthesis status:")
        for row in output_rows:
            print(
                f"  {get_design_name(row)}: "
                f"{row['synthesis_status']}"
            )

        print(
            "\nNote: This is a feature dataset, not yet an ML "
            "training dataset."
        )
        print(
            "Missing cell statistics are not treated as zero."
        )

    except (ValueError, KeyError, csv.Error) as error:
        print(f"\nERROR: {error}")


if __name__ == "__main__":
    main()
