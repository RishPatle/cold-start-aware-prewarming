#!/usr/bin/env python3
"""
Step 1: Data preparation for the pre-warming predictor.
Reads the raw Apache log, extracts timestamps, and bins log arrivals
into hourly counts. Saves the result as a CSV we can train on.
"""

import re
import pandas as pd
from datetime import datetime

LOG_PATH = "../data/Apache.log"
OUT_PATH = "hourly_counts.csv"

# Apache timestamp looks like: [Thu Jun 09 06:07:04 2005]
TS_PATTERN = re.compile(r"\[([A-Za-z]{3}) ([A-Za-z]{3}) (\d{2}) (\d{2}):(\d{2}):(\d{2}) (\d{4})\]")
MONTHS = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
          "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}

def parse_timestamps(path):
    """Read the log line by line, pull out each timestamp as a datetime."""
    times = []
    skipped = 0
    with open(path, "r", errors="ignore") as f:
        for line in f:
            m = TS_PATTERN.search(line)
            if not m:
                skipped += 1
                continue
            _, mon, day, hh, mm, ss, year = m.groups()
            try:
                dt = datetime(int(year), MONTHS[mon], int(day),
                              int(hh), int(mm), int(ss))
                times.append(dt)
            except (ValueError, KeyError):
                skipped += 1
    return times, skipped

def main():
    print("Reading log and parsing timestamps...")
    times, skipped = parse_timestamps(LOG_PATH)
    print(f"  Parsed {len(times)} timestamps ({skipped} lines skipped)")

    # Put into a pandas DataFrame
    df = pd.DataFrame({"timestamp": times})

    # Bin by hour: floor each timestamp to the start of its hour
    df["hour_bin"] = df["timestamp"].dt.floor("h")

    # Count how many logs fell in each hour
    hourly = df.groupby("hour_bin").size().reset_index(name="log_count")

    # Build a COMPLETE hourly timeline (fill gaps - hours with zero logs)
    full_range = pd.date_range(hourly["hour_bin"].min(),
                               hourly["hour_bin"].max(), freq="h")
    hourly = hourly.set_index("hour_bin").reindex(full_range, fill_value=0)
    hourly.index.name = "hour_bin"
    hourly = hourly.reset_index().rename(columns={"log_count": "log_count"})
    hourly["log_count"] = hourly["log_count"].astype(int)

    # Save
    hourly.to_csv(OUT_PATH, index=False)

    # Print a quick summary so we can see the pattern
    total_hours = len(hourly)
    busy_hours = (hourly["log_count"] > 0).sum()
    print(f"\n=== Summary ===")
    print(f"  Total hours in timeline: {total_hours}")
    print(f"  Hours with activity:     {busy_hours} ({100*busy_hours/total_hours:.1f}%)")
    print(f"  Hours with zero logs:    {total_hours - busy_hours}")
    print(f"  Max logs in one hour:    {hourly['log_count'].max()}")
    print(f"  Average logs per hour:   {hourly['log_count'].mean():.1f}")
    print(f"\nSaved hourly counts to: {OUT_PATH}")
    print("\nFirst 10 rows:")
    print(hourly.head(10).to_string(index=False))

if __name__ == "__main__":
    main()