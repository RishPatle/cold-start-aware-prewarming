# F3-Enricher: Initial Cold/Warm Measurements

**Date:** 24 May 2026
**Function:** F3-Enricher (third stage of log processing pipeline)
**Platform:** Knative on Minikube (k8s 1.34), single-node WSL2 Ubuntu

## Setup
- Image: dev.local/f3-enricher:v1
- Resources: 100m CPU request, 500m limit; 128Mi memory request, 256Mi limit
- Scale-to-zero: 30s grace period, 0s pod retention
- Workload: Knowledge-base lookup (12 keywords), classification of records

## Single-shot measurements

### Cold start (after forced scale-to-zero)
- **Total response time: 1,938 ms**
- Enrich work (in-band): 0.13 ms
- Pure cold-start overhead: ~1,938 ms (99.99% of total)
- Pod uptime at response: 0.68 s (confirmed fresh pod)
- Pod: f3-enricher-00001-deployment-75bf6c584b-zngll
- KB hit: yes (matched keyword "jni")

### Warm response (immediate follow-up)
- **Total response time: 14 ms**
- Enrich work (in-band): 0.09 ms
- Pure platform overhead: ~14 ms
- Pod uptime at response: 5.84 s (same pod confirmed)
- KB hit: yes (matched keyword "ldap")

## Enrichment behaviour verified
- KB has 12 keyword mappings (LDAP, JNI, Digest, suEXEC, mod_jk, etc.)
- Records correctly tagged with subsystem, category, known_issue,
  recommended_action, estimated_impact
- Unmatched records correctly default to subsystem="unknown"

## Observations

1. F3 cold-start ratio = ~138x (1938 / 14). Highest of three stages so far.

2. F3's cold start (1.94s) is slightly higher than F2's (1.30s) but lower
   than F1's (2.20s). All three are in the 1-2.2 second range, suggesting
   pure cold-start overhead is largely workload-independent in our setup.

3. KB lookup itself is extremely fast (~0.1 ms even cold). Almost all
   observed latency is platform overhead, not application work. This
   reinforces the methodological position that cold-start research must
   focus on platform-level mitigation, not application-level optimisation.

4. The KB is in-memory (Python dict) so no external network call is made.
   This is a deliberate Phase 1 simplification — in production this would
   be a database or cache call. Phase 2 (if time permits) will replace
   this with a separate always-on Knative service to introduce realistic
   external-dependency latency.

## Aggregate observations across F1, F2, F3

| Stage   | Cold start | Warm | Ratio |
|---------|-----------:|-----:|------:|
| F1      | 2,195 ms   | 48 ms| 46x   |
| F2      | 1,295 ms   | 12 ms| 108x  |
| F3      | 1,938 ms   | 14 ms| 138x  |
| Sum     | 5,428 ms   | 74 ms|       |

These per-function numbers will be compared against the actual end-to-end
pipeline cold start once F4 is built and the four functions are wired
together. The gap between "sum of individual cold starts" and "actual
pipeline cold start" is the central novel measurement of this dissertation.

## Next steps

- Build F4 (Aggregator) — last function before wiring.
- Wire F1 → F2 → F3 → F4 with HTTP calls.
- Run first pipeline-level cold-start measurement.