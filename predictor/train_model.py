    #!/usr/bin/env python3
"""
Step 4: Train the pre-warming predictor and evaluate it.
Uses logistic regression (simple, explainable) to predict whether the
next hour will be busy. Evaluates with a confusion matrix + metrics.
"""

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (confusion_matrix, accuracy_score,
                             precision_score, recall_score, f1_score)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

FEATURES = ["hour_of_day", "day_of_week",
            "busy_lag1", "busy_lag2", "busy_lag3", "count_lag1"]

# Load the prepared data
train = pd.read_csv("train.csv")
test = pd.read_csv("test.csv")

X_train, y_train = train[FEATURES], train["target_next_busy"]
X_test, y_test = test[FEATURES], test["target_next_busy"]

# --- Train the model ---
model = LogisticRegression(max_iter=1000)
model.fit(X_train, y_train)
print("Model trained on", len(X_train), "hours of history.\n")

# --- Predict on the unseen test set ---
y_pred = model.predict(X_test)


cm = confusion_matrix(y_test, y_pred)
tn, fp, fn, tp = cm.ravel()

print("=== Confusion Matrix ===")
print(f"                  Predicted QUIET   Predicted BUSY")
print(f"  Actual QUIET       {tn:5d} (TN)      {fp:5d} (FP)")
print(f"  Actual BUSY        {fn:5d} (FN)      {tp:5d} (TP)")

print("\n=== What each means for pre-warming ===")
print(f"  TP (correctly warmed):     {tp}  - request came, we were ready")
print(f"  TN (correctly stayed cold):{tn}  - no request, saved resources")
print(f"  FP (warmed for nothing):   {fp}  - wasted resources")
print(f"  FN (missed - cold start):  {fn}  - user hit the delay")

# --- Metrics ---
acc = accuracy_score(y_test, y_pred)
prec = precision_score(y_test, y_pred)
rec = recall_score(y_test, y_pred)
f1 = f1_score(y_test, y_pred)
print("\n=== Performance ===")
print(f"  Accuracy:  {acc:.3f}  (overall correct predictions)")
print(f"  Precision: {prec:.3f}  (when we warm, how often it's needed)")
print(f"  Recall:    {rec:.3f}  (of the busy hours, how many we caught)")
print(f"  F1 score:  {f1:.3f}  (balance of precision and recall)")

plt.rcParams.update({'font.size': 16})
fig, ax = plt.subplots(figsize=(5.5, 5))
im = ax.imshow(cm, cmap="Blues")
labels = ["Quiet", "Busy"]
ax.set_xticks([0,1]); ax.set_xticklabels(["Pred Quiet","Pred Busy"])
ax.set_yticks([0,1]); ax.set_yticklabels(["Actual Quiet","Actual Busy"])
for i in range(2):
    for j in range(2):
        ax.text(j, i, cm[i,j], ha="center", va="center",
                fontsize=18, fontweight="bold",
                color="white" if cm[i,j] > cm.max()/2 else "black")
## ax.set_title(f"Predictor Confusion Matrix (Accuracy {acc:.1%})")
plt.tight_layout(); plt.savefig("figures/confusion_matrix.png", dpi=130)
print("\nSaved: figures/confusion_matrix.png")