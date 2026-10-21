
import json
import random
from pathlib import Path

import joblib
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
)
from sklearn.pipeline import Pipeline


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "synthetic_labels.csv"
ARTIFACTS = ROOT / "artifacts"
REPORTS = ROOT / "reports"

# 1. Load and validate labeled data.
df = pd.read_csv(DATA, dtype=str).fillna("")

required = [
    "merchant",
    "raw_description",
    "normalized_name",
    "category",
]

if not set(required).issubset(df.columns):
    raise ValueError("Dataset is missing required columns")

for column in required:
    df[column] = df[column].str.strip()

if (df[required] == "").any().any():
    raise ValueError("Dataset has missing required values")

# Never train on unknown category labels.
df = df[
    df["category"].str.casefold() != "uncategorized"
].copy()

if df.empty:
    raise ValueError("No labeled examples remain")

# Group all versions of one product together.
df["product_group"] = (
    df["normalized_name"].str.casefold()
)

if (
    df.groupby("product_group")["category"].nunique() > 1
).any():
    raise ValueError("Conflicting categories for a product")

# 2. Hold out one product group per category.
rng = random.Random(42)
test_rows = []

for category, subset in df.groupby(
    "category", sort=True
):
    groups = sorted(subset["product_group"].unique())

    if len(groups) < 2:
        raise ValueError(
            f"Need at least two products in {category}"
        )

    selected = rng.choice(groups)

    test_rows.extend(
        subset.index[
            subset["product_group"] == selected
        ].tolist()
    )

train = df.loc[~df.index.isin(test_rows)]
test = df.loc[df.index.isin(test_rows)]

assert set(train["product_group"]).isdisjoint(
    set(test["product_group"])
)

# 3. Use abbreviations as input, NOT reviewed names.
X_train = train["raw_description"].tolist()
X_test = test["raw_description"].tolist()

y_train = train["category"].tolist()
y_test = test["category"].tolist()

labels = sorted(df["category"].unique())

# 4. Baseline: always predict the most frequent class.
baseline = DummyClassifier(
    strategy="most_frequent"
)

baseline.fit([[0] for _ in X_train], y_train)
baseline_pred = baseline.predict(
    [[0] for _ in X_test]
)

# 5. Train a real ML classification pipeline.
model = Pipeline([
    (
        "tfidf",
        TfidfVectorizer(
            analyzer="char",
            ngram_range=(2, 4),
            lowercase=True,
        ),
    ),
    (
        "classifier",
        LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
        ),
    ),
])

model.fit(X_train, y_train)
predictions = model.predict(X_test)

# 6. Evaluate on held-out products only.
def evaluate(predicted):
    return {
        "accuracy": round(
            float(accuracy_score(y_test, predicted)), 3
        ),
        "macro_f1": round(
            float(
                f1_score(
                    y_test,
                    predicted,
                    labels=labels,
                    average="macro",
                    zero_division=0,
                )
            ),
            3,
        ),
    }


metrics = {
    "dataset": "fictional synthetic receipt items",
    "train_examples": len(train),
    "test_examples": len(test),
    "split": "one held-out product group per category",
    "baseline": evaluate(baseline_pred),
    "classifier": evaluate(predictions),
    "sklearn_version": sklearn.__version__,
    "pandas_version": pd.__version__,
}

# 7. Save model and reports locally.
ARTIFACTS.mkdir(exist_ok=True)
REPORTS.mkdir(exist_ok=True)

joblib.dump(
    model,
    ARTIFACTS / "receipt_category_model.joblib",
)

(REPORTS / "category_training_metrics.json").write_text(
    json.dumps(metrics, indent=2),
    encoding="utf-8",
)

holdout = test[
    ["merchant", "raw_description", "category"]
].copy()

holdout["predicted"] = predictions
holdout["correct"] = (
    holdout["category"] == holdout["predicted"]
)

holdout.to_csv(
    REPORTS / "category_training_holdout.csv",
    index=False,
)

print(json.dumps(metrics, indent=2))

print("\nHoldout predictions:")
print(holdout.to_string(index=False))

print("\nClassification report:")
print(
    classification_report(
        y_test,
        predictions,
        labels=labels,
        zero_division=0,
    )
)
