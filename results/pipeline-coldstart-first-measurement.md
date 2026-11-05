# Pipeline-Level Cold Start — FIRST END-TO-END MEASUREMENT

**Date:** 1 June 2026
**Architecture:** Orchestrated (orchestrator calls F1->F2->F3->F4 sequentially)
**Significance:** First measurement of compounded cold start across the full chain.

## Setup
- Orchestrator: dev.local/orchestrator:v1, timeoutSeconds=300
- All 4 functions at min-scale=0 (scaled to zero before the request)
- Input: 5 raw Apache log lines
- Internal calls via cluster DNS (f1-parser.default.svc.cluster.local, etc.)
- Single request, all four stages COLD

## Result: all 4 stages cold

| Stage          | Stage time (ms) | Pod uptime (s) | Status |
|----------------|----------------:|---------------:|--------|
| F1 parser      | 1,766.65        | 0.0364         | 200    |
| F2 filter      | 1,925.30        | 0.395          | 200    |
| F3 enricher    | 2,082.01        | 0.3695         | 200    |
| F4 aggregator  | 2,132.81        | 0.6395         | 200    |
| **TOTAL**      | **7,907.95**    |                |        |

- Orchestration overhead: 1.18 ms (negligible)
- cold_stage_count: 4 (all confirmed cold via uptime < 5s)
- Pipeline produced correct F4 summary: 5 records, error_rate 0.4, 1 alert

## THE CENTRAL COMPARISON

| Measurement                          | Value     |
|--------------------------------------|----------:|
| Sum of individual standalone cold starts | 6,870 ms |
| Sum of stage times within pipeline       | 7,907 ms |
| Actual end-to-end pipeline cold start    | 7,908 ms |

## Key observations (for dissertation)

1. In a sequential orchestrated pipeline, cold-start cost is approximately
   ADDITIVE across stages: total ~= sum of per-stage times. Orchestration
   overhead is negligible (~1 ms).

2. Over 99% of the 7.9s end-to-end latency is cold-start overhead; actual
   processing work across all four stages totals < 5 ms.

3. Per-stage cold-start times measured THROUGH the orchestrator differ from
   standalone measurements taken earlier:
     | Stage | Standalone | In-pipeline |
     |-------|-----------:|------------:|
     | F1    | 2,195 ms   | 1,767 ms    |
     | F2    | 1,295 ms   | 1,925 ms    |
     | F3    | 1,938 ms   | 2,082 ms    |
     | F4    | 1,442 ms   | 2,133 ms    |
   Likely causes: internal DNS path vs ingress/tunnel path, image-cache
   warmth differences, and concurrent pod scheduling pressure when multiple
   cold starts occur close together. TO INVESTIGATE with repeated sampling.

4. This 7.9s fully-cold pipeline latency is the motivating baseline for the
   pre-warming predictor: the target is to hide downstream cold starts so
   that end-to-end latency approaches a single stage's cold start (~2s).

## Next steps
- Repeat this measurement N>=30 times for statistical robustness (mean, P50,
  P95, std dev) rather than a single shot.
- Measure the "all warm" pipeline time as the lower bound.
- Build a benchmark harness script to automate cold/warm pipeline runs.
- Then begin Phase 3: the selective pre-warming predictor.