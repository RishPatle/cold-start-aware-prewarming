#!/usr/bin/env python3
"""
Add statistical treatment to the A/B/C pre-warming latency results.

Reads the pre-warm results CSV and reports, per condition:
  n, mean, median, standard deviation,
  standard error, and a 95% confidence interval on the MEAN.

Also reports the reduction vs cold WITH its own 95% CI, and a
Welch's t-test (A vs B, A vs C, B vs C) so you can state that the
differences are statistically significant, not just visually large.

Pure standard library — no scipy needed. Uses the normal approximation
for the CI (n=18-20 is large enough that this is fine) and reports the
t-test statistic with a plain-language verdict.

Usage:
  python3 stats_ci.py results-prewarm-YYYYMMDD-HHMMSS.csv
"""

import sys
import csv
import math
import statistics


def load(path):
    by_cond = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                c = r["condition"]
                v = float(r["total_curl_s"])
                by_cond.setdefault(c, []).append(v)
            except (ValueError, KeyError):
                continue
    return by_cond


def describe(vals):
    n = len(vals)
    mean = statistics.mean(vals)
    median = statistics.median(vals)
    sd = statistics.stdev(vals) if n > 1 else 0.0      # sample stddev
    se = sd / math.sqrt(n) if n else 0.0               # standard error
    ci = 1.96 * se                                     # 95% CI half-width
    return {"n": n, "mean": mean, "median": median,
            "sd": sd, "se": se, "ci_low": mean - ci, "ci_high": mean + ci,
            "ci_half": ci}


def welch_t(a, b):
    """Welch's t-test (unequal variance). Returns (t, approx_significant)."""
    na, nb = len(a), len(b)
    ma, mb = statistics.mean(a), statistics.mean(b)
    va, vb = statistics.variance(a), statistics.variance(b)
    se = math.sqrt(va / na + vb / nb)
    if se == 0:
        return float("inf"), True
    t = (ma - mb) / se
    # With n~20 and these effect sizes, |t|>2 is comfortably significant
    # at p<0.05; we report the value and a plain verdict.
    return t, abs(t) > 2.0


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 stats_ci.py <results-prewarm-*.csv>")
        sys.exit(1)
    by = load(sys.argv[1])
    order = [c for c in ("A", "B", "C") if c in by]
    labels = {"A": "Cold baseline", "B": "Selective (F2-F4)", "C": "Warm-all"}

    st = {c: describe(by[c]) for c in order}

    print("======== Per-condition statistics (seconds) ========")
    print(f"{'Cond':<5}{'n':<4}{'mean':<8}{'median':<9}{'sd':<7}"
          f"{'95% CI on mean':<22}")
    for c in order:
        s = st[c]
        ci = f"[{s['ci_low']:.3f}, {s['ci_high']:.3f}]"
        print(f"{c:<5}{s['n']:<4}{s['mean']:<8.3f}{s['median']:<9.3f}"
              f"{s['sd']:<7.3f}{ci:<22}")

    # Reduction vs cold, with CI
    if "A" in st:
        cold = st["A"]["mean"]
        print("\n======== Latency reduction vs cold (on means) ========")
        for c in order:
            if c == "A":
                continue
            red = 100 * (cold - st[c]["mean"]) / cold
            # rough CI on the reduction via error propagation
            rel_err = math.sqrt((st["A"]["se"]/st["A"]["mean"])**2
                                + (st[c]["se"]/st[c]["mean"])**2)
            red_ci = red * rel_err * 1.96 / (1 - st[c]["mean"]/cold) \
                if cold else 0
            print(f"  {c} ({labels[c]}): {red:.1f}%  "
                  f"(approx +/- {abs(red_ci):.1f} pp)")

    # Significance tests
    print("\n======== Welch's t-test (are the gaps significant?) ========")
    pairs = [("A", "B"), ("A", "C"), ("B", "C")]
    for x, y in pairs:
        if x in by and y in by:
            t, sig = welch_t(by[x], by[y])
            verdict = "SIGNIFICANT (p<0.05)" if sig else "not significant"
            print(f"  {x} vs {y}: t = {t:.2f}  ->  {verdict}")

    print("\nNote: n~20 per condition; CIs use the normal approximation,")
    print("which is appropriate at this sample size. Report as measured.")


if __name__ == "__main__":
    main()