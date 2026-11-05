#!/usr/bin/env python3
"""
Step 3: Build training features from the hourly counts.
For each hour, create clues (features) and the answer (was next hour busy?).
Then split 70% train / 30% test, preserving time order.
"""

import pandas as pd

IN_PATH = "hourly_counts.csv"
BUSY_THRESHOLD = 1   # an hour is "busy" if it has >= 1 log (production-realistic)

def main():
    df = pd.read_csv(IN_PATH, parse_dates=["hour_bin"])

    # Label each hour: busy (1) or not (0)
    df["is_busy"] = (df["log_count"] >= BUSY_THRESHOLD).astype(int)

    # --- FEATURES (the clues the model sees) ---
    # Time-based clues
    df["hour_of_day"] = df["hour_bin"].dt.hour
    df["day_of_week"] = df["hour_bin"].dt.dayofweek   # 0=Mon .. 6=Sun

    # Recent-activity clues: was each of the last 1, 2, 3 hours busy?
    df["busy_lag1"] = df["is_busy"].shift(1)
    df["busy_lag2"] = df["is_busy"].shift(2)
    df["busy_lag3"] = df["is_busy"].shift(3)
    # How many logs in the previous hour (recent load level)
    df["count_lag1"] = df["log_count"].shift(1)

    # --- LABEL (the answer the model predicts) ---
    # Will the NEXT hour be busy? This is what we want to predict in advance.
    df["target_next_busy"] = df["is_busy"].shift(-1)

    # Drop rows with missing values (the first few and the very last, due to shifting)
    feature_cols = ["hour_of_day", "day_of_week",
                    "busy_lag1", "busy_lag2", "busy_lag3", "count_lag1"]
    df_model = df.dropna(subset=feature_cols + ["target_next_busy"]).copy()
    df_model[feature_cols + ["target_next_busy"]] = \
        df_model[feature_cols + ["target_next_busy"]].astype(int)

    # --- 70/30 split, preserving time order (train on past, test on future) ---
    split_idx = int(len(df_model) * 0.70)
    train = df_model.iloc[:split_idx]
    test = df_model.iloc[split_idx:]

    # Save both sets
    train.to_csv("train.csv", index=False)
    test.to_csv("test.csv", index=False)

    # Summary
    print("=== Feature building complete ===")
    print(f"  Total usable rows: {len(df_model)}")
    print(f"  Train rows (70%):  {len(train)}")
    print(f"  Test rows (30%):   {len(test)}")
    print(f"\n  Features used: {feature_cols}")
    print(f"\n  Busy rate in train: {100*train['target_next_busy'].mean():.1f}%")
    print(f"  Busy rate in test:  {100*test['target_next_busy'].mean():.1f}%")
    print("\n  Saved: train.csv, test.csv")
    print("\nFirst 5 training rows (features + answer):")
    print(train[feature_cols + ["target_next_busy"]].head().to_string(index=False))

if __name__ == "__main__":
    main()