"""Print feature importance from most recent model artifact."""
import sys
from pathlib import Path
import joblib

model_dir = Path(__file__).parent.parent / "models"
artifacts = sorted(model_dir.rglob("model.joblib"), key=lambda p: p.stat().st_mtime)
if not artifacts:
    print("No artifacts found"); sys.exit(1)

newest = artifacts[-1]
print(f"Model: {newest.parent.name}\n")

bundle = joblib.load(newest)
feature_names = bundle.feature_names

def print_importances(label, imp_dict, feature_names):
    print(f"=== {label} ===")
    # imp_dict has keys 'gain' and 'split', each a list aligned with feature_names
    gain = imp_dict.get("gain", [])
    pairs = sorted(zip(feature_names, gain), key=lambda x: x[1], reverse=True)
    print(f"{'Rank':<5} {'Feature':<42} {'Gain':>12}")
    print("-" * 62)
    for i, (name, imp) in enumerate(pairs[:30], 1):
        print(f"{i:<5} {name:<42} {float(imp):>12.4f}")

print_importances("Regressor Feature Importance", bundle.reg_importances, feature_names)
print()
print_importances("Classifier Feature Importance", bundle.clf_importances, feature_names)
