"""Compare the saved scikit-learn classifier with local Ollama on a separate fictional benchmark."""
import argparse
import json
import os
import re
from pathlib import Path
from statistics import median
from time import perf_counter

import httpx
import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

ROOT = Path(__file__).resolve().parent
BENCH = ROOT / "data" / "category_benchmark_synthetic.csv"
TRAIN = ROOT / "data" / "synthetic_labels.csv"
MODEL = ROOT / "artifacts" / "receipt_category_model.joblib"
REPORTS = ROOT / "reports"
LABELS = ["Dairy", "Meat", "Produce", "Household", "Personal Care"]
ALLOWED = [*LABELS, "Unknown"]

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--limit", type=int, help="Use only the first N rows for a connectivity smoke test")
parser.add_argument("--tag", default="run", help="Short result filename label, e.g. before or after")
args = parser.parse_args()
if args.limit is not None and args.limit < 1:
    parser.error("--limit must be positive")
if re.fullmatch(r"[A-Za-z0-9_-]{1,40}", args.tag) is None:
    parser.error("--tag must be 1-40 letters, numbers, hyphens or underscores")

if not MODEL.exists():
    raise SystemExit("Saved ML model missing; run ml/train_category.py first")

benchmark = pd.read_csv(BENCH, dtype=str).fillna("")
training = pd.read_csv(TRAIN, dtype=str).fillna("")
required = {"merchant", "raw_description", "normalized_name", "category"}
for label, df in [("benchmark", benchmark), ("training", training)]:
    if not required.issubset(df.columns):
        raise ValueError(f"Missing required columns in {label}")
    for col in required:
        df[col] = df[col].str.strip()
    if (df[list(required)] == "").any().any():
        raise ValueError(f"Blank required fields in {label}")
if not set(benchmark["category"]).issubset(LABELS):
    raise ValueError("Benchmark contains a category outside the fixed five-category taxonomy")

# Stop obvious evaluation leakage (identical product names or merchant+raw abbreviations).
shared_names = set(benchmark["normalized_name"].str.casefold()) & set(training["normalized_name"].str.casefold())
key = lambda df: set(zip(df["merchant"].str.casefold(), df["raw_description"].str.casefold()))
shared_raw = key(benchmark) & key(training)
if shared_names or shared_raw:
    raise ValueError(f"Training/benchmark overlap: names={shared_names}, raw={shared_raw}")

if args.limit is not None:
    benchmark = benchmark.head(args.limit).copy()
if benchmark.empty:
    raise ValueError("Benchmark is empty")

model = joblib.load(MODEL)  # Only load a model you created yourself.
ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
schema = {
    "type": "object",
    "properties": {"category": {"type": "string", "enum": ALLOWED}},
    "required": ["category"],
    "additionalProperties": False,
}

rows = []
with httpx.Client(timeout=httpx.Timeout(connect=10, read=90, write=15, pool=10)) as client:
    for i, (_, item) in enumerate(benchmark.iterrows(), start=1):
        raw = item["raw_description"]

        begin = perf_counter()
        ml_prediction = str(model.predict([raw])[0])
        ml_seconds = perf_counter() - begin

        begin = perf_counter()
        ollama_prediction = "ERROR"
        ollama_error = ""
        try:
            response = client.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": ollama_model,
                    "stream": False,
                    "format": schema,
                    "options": {"temperature": 0},
                    "keep_alive": "15m",
                    "messages": [
                        {"role": "system", "content": (
                            "Classify one abbreviated receipt item. "
                            "Use only the printed abbreviation. "
                            "Categories: Dairy, Meat, Produce, Household, Personal Care. "
                            "Return Unknown if the category is unclear. "
                            "Return JSON only; don't invent product details."
                        )},
                        {"role": "user", "content": raw},
                    ],
                },
            )
            response.raise_for_status()
            content = json.loads(response.json()["message"]["content"])
            category = content["category"]
            if category not in ALLOWED:
                raise ValueError(f"Unexpected category: {category!r}")
            ollama_prediction = category
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            ollama_error = type(exc).__name__
        ollama_seconds = perf_counter() - begin

        rows.append({
            "merchant": item["merchant"],
            "raw_description": raw,
            "expected": item["category"],
            "sklearn": ml_prediction,
            "ollama": ollama_prediction,
            "sklearn_ms": round(ml_seconds * 1000, 1),
            "ollama_ms": round(ollama_seconds * 1000, 1),
            "ollama_error": ollama_error,
        })
        print(f"{i}/{len(benchmark)} {raw}: expected={item['category']}, "
              f"sklearn={ml_prediction}, ollama={ollama_prediction}" +
              (f" ({ollama_error})" if ollama_error else ""), flush=True)

results = pd.DataFrame(rows)
y = results["expected"]

def score(column):
    predictions = results[column]
    return {
        "accuracy": round(float(accuracy_score(y, predictions)), 3),
        "macro_f1": round(float(f1_score(
            y, predictions, labels=LABELS, average="macro", zero_division=0
        )), 3),
        "correct": int((predictions == y).sum()),
        "errors": int((predictions != y).sum()),
        "median_latency_ms": round(float(median(results[f"{column}_ms"])), 1),
    }

metrics = {
    "dataset": "independent fictional synthetic Day 3 benchmark",
    "benchmark_rows": len(results),
    "mode": "smoke" if args.limit is not None else "full_synthetic_benchmark",
    "ollama_model": ollama_model,
    "ollama_request_failures": int((results["ollama"] == "ERROR").sum()),
    "ollama_abstentions": int((results["ollama"] == "Unknown").sum()),
    "sklearn": score("sklearn"),
    "ollama": score("ollama"),
    "note": "Tiny fictional examples: not a production generalization estimate. "
            "Request failures count as wrong; Ollama may include model load time.",
}
REPORTS.mkdir(exist_ok=True)
suffix = f"_{args.tag}" + ("_smoke" if args.limit is not None else "")
(results).to_csv(REPORTS / f"category_comparison{suffix}.csv", index=False)
(REPORTS / f"category_metrics{suffix}.json").write_text(
    json.dumps(metrics, indent=2), encoding="utf-8"
)
print("\n" + json.dumps(metrics, indent=2))
