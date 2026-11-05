#!/usr/bin/env python3
"""
Step 5: Confidence threshold sweep.
Runs the predictor at every threshold and measures the trade-off two ways:
  (1) ML framing: precision vs recall
  (2) Cost framing: cold starts prevented vs wasted warm-hours
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_curve
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({'font.size': 14})

FEATURES = ["hour_of_day", "day_of_week",
            "busy_lag1", "busy_lag2", "busy_lag3", "count_lag1"]

train = pd.read_csv("train.csv")
test = pd.read_csv("test.csv")
X_train, y_train = train[FEATURES], train["target_next_busy"]
X_test, y_test = test[FEATURES], test["target_next_busy"]

model = LogisticRegression(max_iter=1000)
model.fit(X_train, y_train)
proba = model.predict_proba(X_test)[:, 1]

y_test = y_test.values
total_busy = int(y_test.sum())
total_quiet = int((y_test == 0).sum())

# --- Sweep every threshold ---
thresholds = np.linspace(0.05, 0.95, 19)
rows = []
for t in thresholds:
    warm = (proba >= t).astype(int)
    tp = int(((warm == 1) & (y_test == 1)).sum())
    fp = int(((warm == 1) & (y_test == 0)).sum())
    fn = int(((warm == 0) & (y_test == 1)).sum())
    tn = int(((warm == 0) & (y_test == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    rows.append({
        "threshold": round(t, 2),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "cold_starts_prevented": tp,
        "cold_starts_missed": fn,
        "wasted_warm_hours": fp,
    })

sweep = pd.DataFrame(rows)
sweep.to_csv("threshold_sweep.csv", index=False)

# --- Chart 1: precision-recall ---
prec, rec, _ = precision_recall_curve(y_test, proba)
fig, ax = plt.subplots(figsize=(6, 5))
ax.plot(rec, prec, color="#1F4E79", linewidth=2)
ax.set_xlabel("Recall (fraction of busy hours caught)")
ax.set_ylabel("Precision (fraction of warmings that were needed)")
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("figures/precision_recall.png", dpi=200, bbox_inches="tight")
plt.close()

# --- Chart 2: cost framing ---
fig, ax = plt.subplots(figsize=(7, 5))
ax.plot(sweep["wasted_warm_hours"], sweep["cold_starts_prevented"],
        marker="o", color="#548235", linewidth=2)
for _, r in sweep.iterrows():
    if r["threshold"] in [0.15, 0.35, 0.50, 0.65, 0.85]:
        ax.annotate(f"t={r['threshold']}",
                    (r["wasted_warm_hours"], r["cold_starts_prevented"]),
                    textcoords="offset points", xytext=(6, -10), fontsize=11)
ax.set_xlabel("Wasted warm-hours (resource cost)")
ax.set_ylabel("Cold starts prevented (benefit)")
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("figures/tradeoff_curve.png", dpi=200, bbox_inches="tight")
plt.close()

print("=== Threshold sweep ===")
print(f"Test set: {total_busy} actually-busy hours, {total_quiet} quiet hours\n")
print(sweep.to_string(index=False))
print("\nSaved: threshold_sweep.csv, figures/precision_recall.png, figures/tradeoff_curve.png")