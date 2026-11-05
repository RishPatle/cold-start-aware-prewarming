#!/usr/bin/env python3
"""
Analyse the pre-warming benchmark CSV: print a comparison table and
save a bar chart of median latency for conditions A / B / C.

Usage:
  python3 analyse_prewarm.py results-prewarm-YYYYMMDD-HHMMSS.csv

Reports numbers EXACTLY as measured. No tuning, no fitting.
"""

import sys
import csv
import statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

LABELS = {"A": "Cold\nbaseline", "B": "Selective\n(F2-F4)", "C": "Warm\nall"}
COLORS = {"A": "#C0504D", "B": "#548235", "C": "#1F4E79"}


def load(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                r["total_curl_s"] = float(r["total_curl_s"])
                r["stages_warmed"] = int(r["stages_warmed"])
                rows.append(r)
            except (ValueError, KeyError):
                continue
    return rows


def stats_for(values):
    s = sorted(values)
    n = len(s)
    mean = sum(s) / n
    median = statistics.median(s)
    p95 = s[min(n - 1, int(round(0.95 * (n - 1))))]
    stddev = statistics.pstdev(s) if n > 1 else 0.0
    return {"n": n, "mean": mean, "median": median,
            "p95": p95, "stddev": stddev, "min": s[0], "max": s[-1]}


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyse_prewarm.py <results-prewarm-*.csv>")
        sys.exit(1)
    path = sys.argv[1]
    rows = load(path)
    if not rows:
        print("No usable rows in", path)
        sys.exit(1)

    # Group totals by condition
    by_cond = {}
    warmed_by_cond = {}
    for r in rows:
        c = r["condition"]
        by_cond.setdefault(c, []).append(r["total_curl_s"])
        warmed_by_cond[c] = r["stages_warmed"]

    order = [c for c in ("A", "B", "C") if c in by_cond]
    st = {c: stats_for(by_cond[c]) for c in order}

    # ---- Print full stats ----
    print("======== Per-condition statistics (seconds) ========")
    for c in order:
        s = st[c]
        print(f"  {c} ({LABELS[c].replace(chr(10),' ')}): "
              f"n={s['n']} mean={s['mean']:.3f} median={s['median']:.3f} "
              f"p95={s['p95']:.3f} min={s['min']:.3f} max={s['max']:.3f} "
              f"stddev={s['stddev']:.3f}")

    # ---- Comparison table ----
    print("\n======== Comparison (median latency) ========")
    print(f"{'Cond':<6}{'Median(s)':<12}{'% reduction vs cold':<22}{'Stages warmed':<14}")
    cold_med = st["A"]["median"] if "A" in st else None
    table_rows = []
    for c in order:
        med = st[c]["median"]
        if cold_med:
            red = 100.0 * (cold_med - med) / cold_med
            red_str = f"{red:.1f}%"
        else:
            red = 0.0
            red_str = "n/a"
        print(f"{c:<6}{med:<12.3f}{red_str:<22}{warmed_by_cond[c]:<14}")
        table_rows.append((c, med, red, warmed_by_cond[c]))

    # ---- Bar chart: median latency A/B/C ----
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    xs = list(range(len(order)))
    meds = [st[c]["median"] for c in order]
    bars = ax.bar(xs, meds, color=[COLORS[c] for c in order], width=0.6)
    ax.set_xticks(xs)
    ax.set_xticklabels([LABELS[c] for c in order])
    ax.set_ylabel("Median end-to-end latency (s)")
    # ax.set_title("Pipeline latency: cold vs selective vs warm-all")
    for b, c in zip(bars, order):
        h = b.get_height()
        warmed = warmed_by_cond[c]
        ax.text(b.get_x() + b.get_width() / 2, h + max(meds) * 0.01,
                f"{h:.2f}s\n({warmed} warmed)", ha="center",
                va="bottom", fontsize=9, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_ylim(0, max(meds) * 1.18)
    plt.tight_layout()
    out = "prewarm_comparison.png"
    plt.savefig(out, dpi=140)
    print(f"\nBar chart saved to: {out}")

    # ---- Honest one-line read ----
    if "A" in st and "B" in st and "C" in st:
        b_red = 100.0 * (st["A"]["median"] - st["B"]["median"]) / st["A"]["median"]
        c_red = 100.0 * (st["A"]["median"] - st["C"]["median"]) / st["A"]["median"]
        print("\n======== Honest read ========")
        print(f"  Selective (B) warmed {warmed_by_cond['B']} stages, "
              f"cut median latency by {b_red:.1f}% vs cold.")
        print(f"  Warm-all  (C) warmed {warmed_by_cond['C']} stages, "
              f"cut median latency by {c_red:.1f}% vs cold.")
        if warmed_by_cond["C"] > 0:
            eff = b_red / c_red if c_red else 0
            frac_cost = warmed_by_cond["B"] / warmed_by_cond["C"]
            print(f"  => Selective captured {eff*100:.0f}% of warm-all's benefit "
                  f"at {frac_cost*100:.0f}% of the warming cost.")
        print("  (Report these EXACTLY as measured.)")


if __name__ == "__main__":
    main()