import pandas as pd
from scipy.stats import mannwhitneyu
import numpy as np

df = pd.read_csv("results-prewarm-20260804-131338.csv")

def get(cond):
    return df[df['condition'] == cond]['total_curl_s'].values

A = get('A'); B = get('B'); C = get('C')
print(f"Sample sizes: A={len(A)}, B={len(B)}, C={len(C)}")
print(f"Medians: A={np.median(A):.3f}, B={np.median(B):.3f}, C={np.median(C):.3f}\n")

def cliffs_delta(x, y):
    n, m = len(x), len(y)
    greater = sum(xi > yj for xi in x for yj in y)
    less = sum(xi < yj for xi in x for yj in y)
    return (greater - less) / (n * m)

def boot_ci(x, n=10000):
    meds = [np.median(np.random.choice(x, len(x), replace=True)) for _ in range(n)]
    return np.percentile(meds, 2.5), np.percentile(meds, 97.5)

print("=== Mann-Whitney U tests ===")
for name, x, y in [("A vs B", A, B), ("B vs C", B, C), ("A vs C", A, C)]:
    u, p = mannwhitneyu(x, y, alternative='two-sided')
    d = cliffs_delta(x, y)
    print(f"{name}: U={u:.1f}, p={p:.2e}, Cliff's delta={d:.3f}")

print("\n=== Bootstrap 95% CIs on medians ===")
for name, x in [("A", A), ("B", B), ("C", C)]:
    lo, hi = boot_ci(x)
    print(f"{name} median 95% CI: [{lo:.3f}, {hi:.3f}]")