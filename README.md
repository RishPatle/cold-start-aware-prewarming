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

```
pipeline/
├── functions/          Four pipeline stages + orchestrator (Flask apps)
│   ├── f1-parser/      Regex-parses Apache log lines into structured records
│   ├── f2-filter/      Classifies records by severity, drops low-value entries
│   ├── f3-enricher/    Adds metadata via in-memory knowledge-base lookup
│   ├── f4-aggregator/  Computes summary statistics and raises alerts
│   └── orchestrator/   Calls f1→f2→f3→f4 in sequence, times each stage
├── manifests/          Knative Service definitions (one per function)
├── predictor/          Data prep, feature engineering, model training, sweep
├── benchmark/          Benchmark harness and statistical analysis
├── data/               Loghub Apache log (not committed — see Dataset)
└── results/            Measurement notes
```


## Setup

### 1. Start Minikube
```bash
minikube start --driver=docker
```

### 2. Install Knative Serving + Kourier
Install Knative Serving (v1.13.0) and the Kourier ingress controller, set Kourier
as the ingress class, then patch the Knative config for local images and DNS:

```bash
# Use sslip.io for automatic DNS
kubectl patch configmap/config-domain -n knative-serving \
  --type merge -p '{"data":{"192.168.49.2.sslip.io":""}}'

# Allow locally-loaded images (skip tag resolution for local registries)
kubectl patch configmap/config-deployment -n knative-serving \
  --type merge -p '{"data":{"registries-skipping-tag-resolving":"dev.local,kind.local,ko.local"}}'
```

### 3. Build and load images
Images are built locally and loaded into Minikube (no external registry):
```bash
docker build -t dev.local/<name>:v1 .
minikube image load dev.local/<name>:v1
kubectl apply -f manifests/<name>.yaml
```

### 4. Expose services
Kourier binds to 127.0.0.1, so run the tunnel in a second terminal:
```bash
sudo -E /usr/local/bin/minikube tunnel
```
Then call a service via its sslip.io host:
```bash
curl -H "Host: <svc>.default.192.168.49.2.sslip.io" http://localhost
```

## The four pipeline functions

All functions are Python Flask apps served by gunicorn
(`gunicorn --bind 0.0.0.0:8080 --workers 1 --threads 4 app:app`), on port **8080**.
Each exposes three endpoints:

- **`POST /`** — performs the stage's work and returns JSON.
- **`GET /`** — info endpoint, also used for warm-up pings and human inspection.
- **`GET /healthz`** — readiness probe, returns `ok` (200).

Every response includes `process_uptime_seconds` and `pod` (from `HOSTNAME`),
used as an in-band cold/warm indicator: an uptime below ~5 s means the instance
started fresh on that request.

The stages pass structured data down the chain:

| Stage | Input | Work | Output |
|-------|-------|------|--------|
| **f1-parser** | `{"lines": [...]}` or a raw log line | Regex-parses Apache error-log lines (`[timestamp] [level] message`) into structured records, converting timestamps to ISO format | `parsed` |
| **f2-filter** | `{"parsed": [...]}` | Classifies records by severity, drops low-value entries | `filtered` |
| **f3-enricher** | `{"filtered": [...]}` | Adds metadata via an in-memory knowledge-base lookup | `enriched` |
| **f4-aggregator** | `{"enriched": [...]}` | Computes summary statistics and raises alerts | summary |

Example — f1-parser returns: `records_in`, `records_out`, `parsed`,
`parse_time_ms`, `process_uptime_seconds`, `pod`.

### Knative Service configuration (per function)
- `autoscaling.knative.dev/min-scale: "0"`, `max-scale: "5"`
- `scale-to-zero-pod-retention-period: "0s"`
- `serving.knative.dev/no-tag-resolution: "true"`
- `imagePullPolicy: IfNotPresent`, `containerPort: 8080`
- resources: requests cpu 100m / mem 64Mi; limits cpu 500m / mem 128Mi
- `readinessProbe` on `/healthz`

## The orchestrator

The orchestrator accepts `POST /` with either `{"lines": [...]}` (JSON) or a raw
log line (text/plain), and runs the full pipeline **f1 → f2 → f3 → f4**
sequentially over cluster-internal DNS
(`http://<stage>.default.svc.cluster.local`), with a 60 s per-stage timeout to
tolerate cold starts. It threads each stage's output into the next
(`parsed → filtered → enriched`) and times every call.

It returns:
- `pipeline_result` — the final f4-aggregator output
- `timings.per_stage_ms`, `timings.sum_of_stages_ms`,
  `timings.total_pipeline_ms`, `timings.orchestration_overhead_ms`
- `stage_uptimes_s` — each stage's reported uptime
- `cold_stages_detected` + `cold_stage_count` — stages with uptime < 5 s (fresh pods)
- `orchestrator_uptime_s`, `orchestrator_pod`

This single control point is where pre-warming acts, and the per-stage timing
plus cold-stage detection lets each cold start be attributed to the stage that
incurred it. `GET /` and `GET /healthz` serve info and readiness.

## Running the predictor pipeline

From `predictor/`:
```bash
python3 prepare_data.py       # parse Loghub Apache log → hourly_counts.csv
python3 build_features.py     # features + label, 70/30 time-ordered → train.csv / test.csv
python3 train_model.py        # logistic regression; prints confusion matrix + metrics
python3 threshold_sweep.py    # sweep confidence threshold → threshold_sweep.csv
python3 visualize_pattern.py  # pattern charts
```

**Features:** `hour_of_day`, `day_of_week`, `busy_lag1/2/3`, `count_lag1`.
**Label:** next hour busy (≥ 1 request). **Split:** 70/30 time-ordered (train on
the past, predict the future).

**Model performance (held-out, time-ordered test set):** confusion matrix
TN 733 / FP 296 / FN 171 / TP 699; accuracy 0.754, precision 0.703, recall 0.803,
F1 0.750. The threshold sweep shows a pronounced elbow at **t = 0.35**.

## Running the benchmark (A/B/C)

From `benchmark/`:
```bash
python3 harness_prewarm.py --runs 20 --conditions A,B,C
python3 analyse_prewarm.py <results-csv>   # comparison table + bar chart
python3 stats_test.py <results-csv>        # Mann-Whitney U, Cliff's delta, bootstrap CIs
```

**Conditions:**
- **A — Cold baseline:** no stage warmed (0 warmed).
- **B — Selective:** warm f2-filter, f3-enricher, f4-aggregator; leave f1-parser cold (3 warmed).
- **C — Warm-all:** warm all four stages (4 warmed).

Before each run the harness forces scale-to-zero by polling `kubectl` until the
pods are gone (~45 s). For warmed conditions it then sends HTTP warm-up calls and
polls `process_uptime_seconds` until the stage is confirmed warm, then fires the
measured request. Results are logged to a condition-tagged CSV.

## Results summary

| Condition | Median latency | Reduction vs cold | Stages warmed |
|-----------|---------------|-------------------|---------------|
| A — Cold baseline | 10.52 s | — | 0 |
| B — Selective (f2–f4) | 4.22 s | 59.9% | 3 |
| C — Warm-all | 2.11 s | 80.0% | 4 |

All pairwise differences are statistically significant (Mann-Whitney U, all
p < 10⁻⁶; Cliff's delta = 1.0; non-overlapping bootstrap 95% CIs). The gap
between selective and warm-all is the cost of f1-parser's own cold start, which a
reactive trigger cannot hide.

**Dataset:** Loghub Apache log — 56,481 lines → 52,004 timestamps → 6,334 hourly
bins over ~9 months, 54.5% busy.

## Limitations

- Single-node Minikube cluster (~7.5 GiB), not a multi-node cloud deployment.
- The entry function (f1-parser) cannot be warmed reactively — its arrival is the
  event that triggers the pipeline.
- The predictor is a deliberately simple model (~75% accuracy); some busy hours
  are missed.
- Trained and tested on a single Loghub Apache log; generalisation to other
  workloads is untested.

## Dataset & attribution

Trained on the Apache access log from the Loghub collection
(https://github.com/logpai/loghub). The dataset is not redistributed in this
repository; download it separately into `data/`.

## Author

Rishabh Vijaykumar Patle — MSc Cloud Computing, Newcastle University.