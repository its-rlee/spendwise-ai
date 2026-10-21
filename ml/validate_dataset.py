
import csv
from collections import Counter
from pathlib import Path

DATASET = (
    Path(__file__).parent
    / "data"
    / "synthetic_labels.csv"
)

REQUIRED = {
    "merchant",
    "raw_description",
    "normalized_name",
    "category",
}

with DATASET.open(
    encoding="utf-8-sig",
    newline="",
) as file:
    reader = csv.DictReader(file)

    if not REQUIRED.issubset(reader.fieldnames or []):
        raise ValueError("Dataset has missing columns")

    rows = list(reader)

if not rows:
    raise ValueError("Dataset is empty")

seen = {}

for number, row in enumerate(rows, start=2):
    for column in REQUIRED:
        if not (row.get(column) or "").strip():
            raise ValueError(
                f"Row {number}: {column} is empty"
            )

    key = (
        row["merchant"].strip().lower(),
        row["raw_description"].strip().lower(),
    )

    category = row["category"].strip()

    if key in seen:
        raise ValueError(
            f"Duplicate or conflicting label "
            f"at row {number}: {key}"
        )

    seen[key] = category

print(f"Validated {len(rows)} labeled examples")

print("\nCategory distribution:")
for category, count in Counter(
    row["category"] for row in rows
).most_common():
    print(f"  {category}: {count}")
