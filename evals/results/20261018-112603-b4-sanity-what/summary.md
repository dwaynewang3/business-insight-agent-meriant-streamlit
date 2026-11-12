# Eval run: 20261018-112603-b4-sanity-what

- Model: claude-sonnet-5-5 at medium effort, tools: full (agent 0.1.0+1ba489d548)
- Passed: **8/8** (95% range 68%–100%)
- Categories: pass 8
- Key numbers confirmed by their finding's SQL: 31/31 (100%)
- Cost: $0.4726 ($0.0591 per question)
- Latency: median 20.240000000000002s, 95th percentile 41.76s
- Queries per case: 7.75; cache read share of input: 0.965
- Fallback answers: none

| Case | Result | Cost | Seconds | Queries | Numbers | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| what-claim-frequency-by-state-motor-2026-q2 | pass | $0.0693 | 25.51 | 4 | 8/8 |  |
| what-loss-ratio-by-product-2025 | pass | $0.0524 | 21.31 | 5 | 4/4 |  |
| what-average-claim-cost-motor-nsw-2026-q2 | pass | $0.0535 | 22.07 | 7 | 2/2 |  |
| what-claim-count-by-month-nsw-2025 | pass | $0.0492 | 16.88 | 8 | 1/1 |  |
| what-open-claims-by-adjuster-west-south | pass | $0.0512 | 19.17 | 8 | 6/6 |  |
| what-median-cycle-time-by-region-2025-q1 | pass | $0.0354 | 13.15 | 5 | 4/4 |  |
| what-top-states-by-loss-ratio-3-home-2025 | pass | $0.0434 | 17.99 | 5 | 3/3 |  |
| what-cause-share-motor-glass-2026-q1 | pass | $0.1183 | 41.76 | 20 | 3/3 |  |
