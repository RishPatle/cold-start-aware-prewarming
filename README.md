# Cold-Start-Aware Scheduling for Serverless Function Pipelines

MSc dissertation project (Newcastle University, MSc Cloud Computing). A framework
that predicts demand and **selectively pre-warms** serverless pipeline stages to
hide cold-start latency, while preserving the cost efficiency of scale-to-zero.

**Measured result:** selective pre-warming cut median end-to-end pipeline latency
by **59.9%** on a live Knative pipeline, validated with Mann-Whitney U tests
(all p < 0.001).

## The problem
Serverless functions scale to zero when idle, so the next request pays a cold
start. In pipelines these delays stack: a four-stage pipeline here took ~10s cold
vs ~0.06s warm, roughly 150x slower.

## The idea
Warming every stage wastes resources. Cold start dominates the response time of
light functions but not heavy ones, so this framework warms only the stages where
cold start dominates, driven by a demand predictor.

## Key results
| Condition | Median latency | Reduction |
|-----------|---------------|-----------|
| Cold baseline | 10.52s | - |
| Selective (warm F2-F4) | 4.22s | 59.9% |
| Warm-all | 2.11s | 80.0% |

## Tech stack
Kubernetes, Knative Serving, Docker, Minikube, Kourier, Python, scikit-learn,
pandas, NumPy, matplotlib, SciPy.

## Repository structure
- `functions/` - four-stage pipeline (parser, filter, enricher, aggregator) + orchestrator
- `manifests/` - Knative service definitions
- `predictor/` - demand-prediction model, feature engineering, threshold sweep
- `benchmark/` - benchmark harness and statistical analysis
- `results/` - measurement notes

## Dataset
Trained on the Apache access log from the Loghub collection
(https://github.com/logpai/loghub). Not redistributed here; download separately
into `data/`.

## Author
Rishabh Vijaykumar Patle - MSc Cloud Computing, Newcastle University
