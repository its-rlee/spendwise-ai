"""Review the existing local Day 3 before/after reports without retraining."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / 'reports'


def load(tag):
    metrics_path = REPORTS / f'category_metrics_{tag}.json'
    detail_path = REPORTS / f'category_comparison_{tag}.csv'
    if not metrics_path.is_file() or not detail_path.is_file():
        raise SystemExit(f'Missing {tag} report(s): run ml/compare_category_models.py --tag {tag}')
    metrics = json.loads(metrics_path.read_text(encoding='utf-8'))
    with detail_path.open(encoding='utf-8-sig', newline='') as file:
        rows = list(csv.DictReader(file))
    if metrics.get('mode') != 'full_synthetic_benchmark' or len(rows) != metrics.get('benchmark_rows'):
        raise SystemExit(f'{tag}: Only full, matching benchmark runs can be compared.')
    return metrics, { (r['merchant'], r['raw_description']): r for r in rows }


def main():
    before, b_rows = load('before')
    after, a_rows = load('after')
    if set(b_rows) != set(a_rows):
        raise SystemExit('Before/after reports use different benchmark items.')
    print('Model      Stage   Correct/Total  Accuracy  Macro F1  Median latency (ms)')
    for model in ('sklearn', 'ollama'):
        for tag, metrics in (('before', before), ('after', after)):
            s = metrics[model]
            print(f'{model:<10} {tag:<7} {s["correct"]:>2}/{metrics["benchmark_rows"]:<11} '
                  f'{s["accuracy"]:>7.3f}  {s["macro_f1"]:>8.3f}  {s["median_latency_ms"]:>18.1f}')
    print('\nChanged predictions on identical benchmark items:')
    for key in b_rows:
        old, new = b_rows[key], a_rows[key]
        for model in ('sklearn', 'ollama'):
            if old[model] != new[model]:
                print(f'{model:<8} {key[1]:<20} {old[model]} -> {new[model]} '
                      f'(expected {new["expected"]})')
    print('\nNote: Ollama timings can vary with local load and model warm-up.')


if __name__ == '__main__':
    main()
