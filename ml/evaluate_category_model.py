"""Evaluate saved local classifier on a private, human-reviewed receipt dataset."""
import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

ROOT = Path(__file__).resolve().parent
LABELS = ['Dairy', 'Meat', 'Produce', 'Household', 'Personal Care']
ALLOWED = set(LABELS) | {'Other'}
REQUIRED = ['receipt_group', 'merchant', 'raw_description', 'normalized_name', 'category']


def keys(frame):
    return set(zip(frame['merchant'].str.casefold(), frame['raw_description'].str.casefold()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=ROOT / 'data/private/verified_receipts.csv')
    parser.add_argument('--model', type=Path, default=ROOT / 'artifacts/receipt_category_model.joblib')
    parser.add_argument('--threshold', type=float, default=0.5,
                        help='Illustrative confidence gate, NOT a calibrated probability')
    args = parser.parse_args()
    if not 0 <= args.threshold <= 1:
        parser.error('--threshold must be between 0 and 1')
    if not args.csv.is_file():
        parser.error(f'File missing: {args.csv}. Create it from the private template first.')
    if not args.model.is_file():
        parser.error(f'Model missing: {args.model}. Train Day 2 model first.')

    real = pd.read_csv(args.csv, dtype=str).fillna('')
    if not set(REQUIRED).issubset(real.columns):
        parser.error(f'CSV needs columns: {", ".join(REQUIRED)}')
    for col in REQUIRED:
        real[col] = real[col].str.strip()
    if real.empty:
        parser.error('Your real evaluation CSV has no rows. Add manually verified examples.')
    if (real[REQUIRED] == '').any().any():
        parser.error('CSV contains blank required fields.')
    if not set(real['category']).issubset(ALLOWED):
        parser.error('Categories must be: ' + ', '.join(sorted(ALLOWED)))

    # This is a strict first-pass leakage check, not full semantic de-duplication.
    train = pd.read_csv(ROOT / 'data/synthetic_labels.csv', dtype=str).fillna('')
    benchmark = pd.read_csv(ROOT / 'data/category_benchmark_synthetic.csv', dtype=str).fillna('')
    for df in (train, benchmark):
        for col in ('merchant', 'raw_description', 'normalized_name'):
            df[col] = df[col].str.strip()
    training_keys = keys(train)
    training_names = set(train['normalized_name'].str.casefold())
    eval_keys = keys(real)
    eval_names = set(real['normalized_name'].str.casefold())
    shared = training_keys & eval_keys
    shared_names = training_names & eval_names
    if shared or shared_names:
        parser.error('Real evaluation overlaps synthetic TRAINING data. '
                     'Use independent held-out receipts; overlap detected.')

    model = joblib.load(args.model)  # Only load model artifacts you produced yourself.
    if not hasattr(model, 'predict_proba'):
        parser.error('Model must expose predict_proba')
    probability = model.predict_proba(real['raw_description'].tolist())
    classes = list(model.classes_)
    best_index = probability.argmax(axis=1)
    real['prediction'] = [classes[i] for i in best_index]
    real['score'] = [round(float(probability[j, i]), 4)
                     for j, i in enumerate(best_index)]
    real['route'] = real['score'].apply(lambda v: 'auto_suggest' if v >= args.threshold else 'human_review')
    real['correct'] = real['prediction'] == real['category']
    known = real[real['category'].isin(LABELS)]
    automatic = real[real['route'] == 'auto_suggest']
    metrics = {
        'dataset': 'private independently reviewed receipts',
        'examples': len(real),
        'receipt_groups': int(real['receipt_group'].nunique()),
        'in_scope_examples': len(known),
        'out_of_scope_other': int((real['category'] == 'Other').sum()),
        'model_accuracy_in_scope': (round(float(accuracy_score(known['category'], known['prediction'])), 3)
                                    if len(known) else None),
        'model_macro_f1_in_scope': (round(float(f1_score(known['category'], known['prediction'],
                                                    labels=LABELS, average='macro', zero_division=0)), 3)
                                    if len(known) else None),
        'threshold': args.threshold,
        'automatic_suggestion_coverage': round(len(automatic) / len(real), 3),
        'accuracy_among_automatic_suggestions': (round(float(automatic['correct'].mean()), 3)
                                                 if len(automatic) else None),
        'out_of_scope_items_auto_suggested': int((automatic['category'] == 'Other').sum()),
        'note': ('Score is an uncalibrated classifier probability, not a trustworthy confidence guarantee. '
                 'No threshold has been validated for production automation.'),
    }
    out = ROOT / 'reports'
    out.mkdir(exist_ok=True)
    real.to_csv(out / 'category_evaluation_predictions.csv', index=False)
    (out / 'category_evaluation_metrics.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')
    print(json.dumps(metrics, indent=2))
    print('\nReview wrong or high-risk predictions in: ml/reports/category_evaluation_predictions.csv')
    print(real[['raw_description', 'category', 'prediction', 'score', 'route']].to_string(index=False))


if __name__ == '__main__':
    main()
