# F1-Parser: Initial Cold/Warm Measurements

**Date:** 21 May 2026
**Function:** F1-Parser (first stage of log processing pipeline)
**Platform:** Knative on Minikube (k8s 1.34), single-node WSL2 Ubuntu

## Setup
- Image: dev.local/f1-parser:v1
- Resources: 100m CPU request, 500m limit; 128Mi memory request, 256Mi limit
- Scale-to-zero: 30s grace period, 0s pod retention
- Workload: Apache error log line parsing (regex + datetime conversion)

## Single-shot measurements

### Cold start
- **Total response time: 2,195 ms**
- Parse work (in-band): 8.89 ms
- Pure cold-start overhead: ~2,186 ms (99.6% of total)
- Pod uptime at response time: 0.11 s (confirmed fresh pod)
- Pod ID: f1-parser-00001-deployment-84d7b6ff97-gvkcf

### Warm response (immediate follow-up)
- **Total response time: 48 ms**
- Parse work (in-band): 0.16 ms
- Pure platform overhead: ~48 ms (mostly network round-trip)
- Pod uptime at response time: 13.5 s (same pod as cold)
- Pod ID: f1-parser-00001-deployment-84d7b6ff97-gvkcf

## Observations

1. Cold start ratio = 46x (cold / warm). For F1 specifically, cold start
   dominates total response time (99.6%) — the parser is doing very little
   actual work compared to platform overhead.

2. F1's cold start (2.2s) is lower than the earlier fn1-hello measurement
   (3.6s). This is likely because the container image was pre-cached on the
   node from a prior build, not pulled from a registry. This is a
   methodological note: experiments should control for image-cache state
   between runs.

3. Parse work itself takes only ~0.16 ms warm — regex matching and
   timestamp parsing are extremely fast for individual lines.

## Next steps

- Build F2 (Filter) using the same pattern.
- Run a 50-sample cold/warm benchmark per function once all 4 stages are
  deployed.
- Then measure pipeline-level cold start (with all 4 cold) and compare to
  the sum of individual cold starts.