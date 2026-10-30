
import csv
import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATASET = PROJECT_DIR / "dataset"

FEATURE_FILE = DATASET / "benchmark_features.csv"
RESULT_FILE = DATASET / "benchmark_results.csv"
OUTPUT_FILE = DATASET / "combined_benchmark_dataset.csv"


def load_csv(path):
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def main():
    if not FEATURE_FILE.exists() or not RESULT_FILE.exists():
        print("ERROR: Run the feature extractor and benchmark runner first.")
        return

    features = {
        row["Design"]: row
        for row in load_csv(FEATURE_FILE)
    }

    results = {
        row["Design"]: row
        for row in load_csv(RESULT_FILE)
    }

    combined = []

    for design, result in results.items():
        if result.get("Status") != "Success":
            print("Skipping failed synthesis:", design)
            continue

        if design not in features:
            print("Missing RTL features:", design)
            continue

        row = dict(features[design])
        row["Synthesis_Status"] = result["Status"]
        row["Synthesized_Cell_Count"] = result["Cell_Count"]

        try:
            cell_types = json.loads(result["Cell_Types"])
        except (ValueError, TypeError):
            cell_types = {}

        for cell_type, count in cell_types.items():
            row["Cell_" + cell_type] = count

        combined.append(row)

    # Keep a consistent set of columns across all designs.
    columns = []
    for row in combined:
        for key in row:
            if key not in columns:
                columns.append(key)

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(combined)

    print("Combined designs:", len(combined))
    print("Saved to:", OUTPUT_FILE)
    print("These are RTL features and synthesis statistics, not PPA labels.")


if __name__ == "__main__":
    main()
