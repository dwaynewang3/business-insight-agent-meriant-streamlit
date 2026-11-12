# Eval run: 20261009-012919-baseline-semantic-off

- Model: claude-sonnet-5-5 at medium effort, tools: full (agent 0.1.0+57629b5499)
- Passed: **7/8** (95% range 53%–98%)
- Categories: pass 7, wrong_result 1
- Key numbers confirmed by their finding's SQL: 29/30 (97%)
- Cost: $0.1983 ($0.0248 per case)
- Latency: median 14.82s, 95th percentile 27.83s
- Queries per case: 3.38; cache read share of input: 0.956
- Fallback answers: none

| Case | Result | Cost | Seconds | Queries | Numbers | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| what-average-claim-cost-auto-tx-2026-q2 | pass | $0.0418 | 27.83 | 7 | 4/5 |  |
| what-cause-share-auto-glass-2026-q1 | pass | $0.0150 | 10.32 | 2 | 3/3 |  |
| what-claim-count-by-month-tx-2025 | pass | $0.0154 | 11.32 | 2 | 3/3 |  |
| what-claim-frequency-by-state-auto-2026-q2 | wrong_result | $0.0259 | 18.91 | 4 | 3/3 | No column in the answer matches the reference's claim_frequency. |
| what-loss-ratio-by-product-2025 | pass | $0.0316 | 26.39 | 4 | 4/4 |  |
| what-median-cycle-time-by-region-2025-q1 | pass | $0.0166 | 9.67 | 2 | 4/4 |  |
| what-open-claims-by-adjuster-southeast | pass | $0.0172 | 10.26 | 2 | 5/5 |  |
| what-top-states-by-loss-ratio-3-home-2025 | pass | $0.0349 | 18.32 | 4 | 3/3 |  |
