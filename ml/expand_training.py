"""Append synthetic training examples without mixing in the Day 3 benchmark."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TRAIN = ROOT / "data" / "synthetic_labels.csv"
EXTRA = ROOT / "data" / "training_additions_day03.csv"
BENCH = ROOT / "data" / "benchmark_day03.csv"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


fields, original = read_csv(TRAIN)
extra_fields, additions = read_csv(EXTRA)
_, benchmark = read_csv(BENCH)
if fields != extra_fields:
    raise ValueError("Training CSV and additions must have identical columns")

benchmark_names = {r["normalized_name"].strip().casefold() for r in benchmark}
benchmark_raw = {(r["merchant"].strip().casefold(),
                  r["raw_description"].strip().casefold()) for r in benchmark}

existing = {(r["merchant"].strip().casefold(),
             r["raw_description"].strip().casefold()) for r in original}

new_rows = []
for row in additions:
    key = (row["merchant"].strip().casefold(), row["raw_description"].strip().casefold())
    if key in benchmark_raw or row["normalized_name"].strip().casefold() in benchmark_names:
        raise ValueError(f"Training/benchmark overlap found: {key}")
    if key not in existing:
        new_rows.append(row)
        existing.add(key)

# Never put benchmark rows into training.
if new_rows:
    with TRAIN.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows([*original, *new_rows])
print(f"Added {len(new_rows)} examples; training CSV now has {len(original) + len(new_rows)} rows")
