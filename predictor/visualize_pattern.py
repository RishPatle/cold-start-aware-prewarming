#!/usr/bin/env python3
"""
Step 2: Visualise the hourly log pattern before modelling.
Produces charts so we can SEE the traffic rhythm the predictor will learn.
"""

import pandas as pd
import matplotlib
matplotlib.use("Agg")   # save to file, no GUI needed
import matplotlib.pyplot as plt

plt.rcParams.update({'font.size': 18})   # bigger text inside all charts

df = pd.read_csv("hourly_counts.csv", parse_dates=["hour_bin"])

# --- Chart 1: activity over the whole timeline ---
fig, ax = plt.subplots(figsize=(12, 4))
ax.plot(df["hour_bin"], df["log_count"], linewidth=0.5, color="#1F4E79")
ax.set_xlabel("Time"); ax.set_ylabel("Logs in that hour")
plt.tight_layout()
plt.savefig("pattern_timeline.png", dpi=200, bbox_inches="tight")
plt.close()

# --- Chart 2: average activity by hour-of-day (is there a daily rhythm?) ---
df["hour_of_day"] = df["hour_bin"].dt.hour
by_hour = df.groupby("hour_of_day")["log_count"].mean()
fig, ax = plt.subplots(figsize=(9, 4))
ax.bar(by_hour.index, by_hour.values, color="#2E6DA4")
ax.set_xlabel("Hour of day (0-23)"); ax.set_ylabel("Average logs")
ax.set_xticks(range(0, 24))
plt.tight_layout()
plt.savefig("pattern_by_hour.png", dpi=200, bbox_inches="tight")
plt.close()

# --- Chart 3: average activity by day of week ---
df["day_of_week"] = df["hour_bin"].dt.dayofweek  # 0=Mon
by_day = df.groupby("day_of_week")["log_count"].mean()
days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(days, by_day.values, color="#548235")
ax.set_xlabel("Day"); ax.set_ylabel("Average logs")
plt.tight_layout()
plt.savefig("pattern_by_day.png", dpi=200, bbox_inches="tight")
plt.close()

print("Charts saved:")
print("  pattern_timeline.png  - activity over the whole period")
print("  pattern_by_hour.png   - daily rhythm (by hour of day)")
print("  pattern_by_day.png    - weekly rhythm (by day of week)")
