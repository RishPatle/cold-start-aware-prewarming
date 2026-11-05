# F2-Filter: Initial Cold/Warm Measurements

**Date:** 21 May 2026
**Function:** F2-Filter (second stage of log processing pipeline)
**Platform:** Knative on Minikube (k8s 1.34), single-node WSL2 Ubuntu

## Setup
- Image: dev.local/f2-filter:v1
- Resources: 100m CPU request, 500m limit; 128Mi memory request, 256Mi limit
- Scale-to-zero: 30s grace period, 0s pod retention
- Workload: log-record classification (level → severity, category, alert flag, kept/dropped)

## Single-shot measurements

### Cold start
- **Total response time: 1,295 ms**
- Filter work (in-band): 1.10 ms
- Pure cold-start overhead: ~1,294 ms (99.9% of total)
- Pod uptime at response: 0.11 s (confirmed fresh pod)
- Pod: f2-filter-00001-deployment-8c54df9d-qmcfq

### Warm response (immediate follow-up)
- **Total response time: 12 ms**
- Filter work (in-band): 0.20 ms
- Pure platform overhead: ~12 ms
- Pod uptime at response: 4.30 s (same pod as cold)
- Pod: f2-filter-00001-deployment-8c54df9d-qmcfq

## Filtering behaviour verified
- 5 input records → 3 kept, 2 dropped
- "info" and "debug" levels correctly dropped (out of KEEP_LEVELS set)
- "error" level correctly flagged with should_alert=true

## Observations

1. F2 cold-start ratio = ~108x (cold / warm). Even more dramatic than F1's
   46x ratio.

2. F2's cold start (1.3s) is faster than F1's (2.2s). Likely because the
   container image shares base layers with F1 that were already cached on
   the node. This is an important methodological note: container image
   caching state significantly affects observed cold start. The benchmark
   harness should either (a) explicitly invalidate image cache between
   runs, or (b) report results conditioned on image-cache state.

3. F2 actually does very little work (~0.2ms warm) since it's just dict
   manipulation and lookups. Almost all observed latency in the cold case
   is platform overhead.

## Next steps

- Build F3 (Enricher) and F4 (Aggregator) following the same pattern.
- Once all 4 are deployed standalone, wire them together with HTTP calls
  so F1 → F2 → F3 → F4 forms an actual chain.
- Run the FIRST pipeline-level cold-start measurement.  