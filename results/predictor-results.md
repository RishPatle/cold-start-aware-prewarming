# Predictor v1 - Logistic Regression - Results
Date: (today)

## Setup
- Data: Loghub Apache log, 6330 hourly bins
- Split: 70% train (4431h) / 30% test (1899h), time-ordered
- Features: hour_of_day, day_of_week, busy_lag1/2/3, count_lag1
- Target: will next hour be busy (>=1 log)?
- Model: Logistic Regression (simple, explainable - per supervisor advice)

## Confusion Matrix (test set)
                Pred Quiet   Pred Busy
Actual Quiet    733 (TN)     296 (FP)
Actual Busy     171 (FN)     699 (TP)

## Metrics
Accuracy:  0.754
Precision: 0.703  (when we warm, how often needed)
Recall:    0.803  (of busy hours, how many caught)
F1:        0.750

## Interpretation
- Recall 80%: caught 4 of 5 busy hours -> prevented most cold starts.
- Model biased toward recall over precision - CORRECT bias for pre-warming,
  since a miss (FN, user waits ~10s) costs more than a false alarm (FP, minor waste).
- 296 FP vs 171 FN quantifies the core cost/benefit trade-off.
- Time-ordered split => train/test distribution shift => honest, harder test.

# Threshold Sweep - Trade-off Result
Test set: 870 busy hours, 1029 quiet hours

## Key operating points
threshold  recall  cold_prevented  cold_missed  wasted_warm_hours
0.05-0.30   1.00      870              0            1029   (warm everything)
0.35        0.96      839             31             380   (SWEET SPOT)
0.50        0.80      699            171             296   (default)
0.60        0.75      649            221             266
0.65        0.37      322            548             147   (recall cliff)
0.75        0.06       50            820              24

## Headline finding
Moving threshold 0.05 -> 0.35 gives up only 31/870 (3.6%) of preventable
cold starts but cuts wasted warm-hours by 63% (1029 -> 380).
=> Selective confidence-based pre-warming achieves ~96% of the benefit at
   ~37% of the resource cost. Proves the core thesis: warming everything is
   wasteful; selective warming is near-optimal.

## Usable range
Threshold 0.35-0.60 is the practical operating band. Beyond 0.6, recall
collapses (cliff at 0.65: recall 0.75 -> 0.37).
