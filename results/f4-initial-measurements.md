# F4-Aggregator: Initial Cold/Warm Measurements

**Date:** 1 June 2026
**Function:** F4-Aggregator (fourth and final stage of log processing pipeline)
**Platform:** Knative on Minikube (k8s 1.34), single-node WSL2 Ubuntu

## Setup
- Image: dev.local/f4-aggregator:v1
- Resources: 100m CPU request, 500m limit; 128Mi memory request, 256Mi limit
- Scale-to-zero: 30s grace period, 0s pod retention
- Workload: aggregation (Counter-based stats) + threshold-based alerting

## Single-shot measurements

### Cold start
- **Total response time: 1,442 ms**
- Aggregate work (in-band): 0.16 ms
- Pure cold-start overhead: ~1,442 ms
- Pod uptime at response: 0.0056 s (confirmed fresh pod)
- Pod: f4-aggregator-00001-deployment-5b758ccdc6-94phd

### Warm response (immediate follow-up)
- **Total response time: 19 ms**
- Aggregate work (in-band): 0.13 ms
- Pod uptime at response: 9.81 s (same pod confirmed)

## Aggregation + alerting verified
- 5-record test: error_rate 0.6, high=3/medium=1/low=1, known_issues=3
- Correctly raised 2 alerts: WARNING (error rate) + CRITICAL (high severity)
- top_subsystems ranked correctly (JNI=2 leading)

## COMPLETE PER-FUNCTION BASELINE (all 4 stages)

| Stage | Cold start | Warm | Ratio |
|-------|-----------:|-----:|------:|
| F1 Parser    | 2,195 ms | 48 ms | 46x  |
| F2 Filter    | 1,295 ms | 12 ms | 108x |
| F3 Enricher  | 1,938 ms | 14 ms | 138x |
| F4 Aggregator| 1,442 ms | 19 ms | 76x  |
| **SUM**      | **6,870 ms** | **93 ms** | |

This sum (6,870 ms) is the "naive" expectation: what you'd predict the
pipeline cold start to be if you just added up the individual stages.
The next experiment measures the ACTUAL end-to-end pipeline cold start
and compares it against this sum. The gap is the central novel finding.

## Next step: WIRE THE PIPELINE
- Modify F1 to call F2, F2 to call F3, F3 to call F4 (HTTP chaining).
- Send one request to F1, measure total end-to-end time.
- Compare actual pipeline cold start vs sum of individuals (6,870 ms).
