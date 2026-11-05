# Cold-Start-Aware Scheduling for Serverless Function Pipelines

A framework that predicts demand and **selectively pre-warms** Knative serverless
functions to reduce cold-start latency in multi-stage pipelines, while preserving
the cost efficiency of scale-to-zero. MSc dissertation project, Newcastle
University (MSc Cloud Computing).

**Measured result:** on a live four-stage Knative pipeline, selective pre-warming
cut median end-to-end latency by **59.9%** (10.52 s → 4.22 s) while warming three
of four stages — close to the 80.0% achieved by warming all four. All pairwise
differences are statistically significant (Mann-Whitney U, p < 10⁻⁶).

---

## Overview

Serverless functions scale to zero when idle, so the first request after an idle
period pays a **cold start** while a fresh instance is built. In pipelines —
chains of functions where each stage feeds the next — these delays compound. In
this project a four-stage pipeline took roughly **10 s cold versus 0.06 s warm,
about 150× slower**.

Warming every stage hides the delay but wastes the resources that make
scale-to-zero worthwhile. The key insight: cold start dominates the response time
of lightweight functions but is only a small fraction for heavier ones. This
framework therefore warms **only the stages where cold start dominates**, driven
by a demand predictor, capturing most of the benefit at a fraction of the cost.

## Architecture

Three layers:

- **Offline** — a logistic-regression model is trained on nine months of real log
  timestamps to forecast whether the next hour will be busy.
- **Online** — a predictor ("brain") decides when demand is coming; a trigger
  ("hands") warms the selected downstream stages before the request arrives. An
  orchestrator calls the four-stage pipeline in sequence and times each stage.
- **Evaluation** — a purpose-built benchmark harness measures end-to-end latency
  under cold, selective, and warm-all conditions.

**Stack:** Windows 11 → WSL2 (Ubuntu 24.04) → Docker Engine → Minikube v1.38.1
(Docker driver, single-node) → Kubernetes v1.34.1 → Knative Serving v1.13.0 →
Kourier ingress.

## Prerequisites & versions

| Component | Version |
|-----------|---------|
| OS | Windows 11 + WSL2 (Ubuntu 24.04) |
| Docker | Docker Engine (native in WSL2) |
| Minikube | v1.38.1 (Docker driver, single-node) |
| Kubernetes | v1.34.1 |
| Knative Serving | v1.13.0 |
| Ingress | Kourier |
| Python | 3.11 |
| Hardware used | Intel Core Ultra 5 125H, 16 GB RAM (~7.5 GiB to WSL2), 18 cores |

Python dependencies: `flask==3.0.3`, `gunicorn==23.0.0` (functions); `pandas`,
`numpy`, `scikit-learn`, `scipy`, `matplotlib` (predictor and analysis).

## Repository structure