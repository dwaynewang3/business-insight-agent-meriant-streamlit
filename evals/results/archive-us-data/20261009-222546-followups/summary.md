# Eval run: 20261009-222546-followups

- Model: claude-sonnet-5-5 at medium effort, tools: full (agent 0.1.0+92df8670f7)
- Passed: **5/5** (95% range 57%–100%)
- Categories: pass 5
- Key numbers confirmed by their finding's SQL: 28/30 (93%)
- Cost: $0.2713 ($0.0543 per case)
- Latency: median 26.1s, 95th percentile 30.45s
- Queries per case: 1.6; cache read share of input: 0.926
- Fallback answers: none

| Case | Result | Cost | Seconds | Queries | Numbers | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| followup-average-cost-by-product | pass | $0.0569 | 26.1 | 2 | 4/4 |  |
| followup-frequency-same-for-home | pass | $0.0590 | 27.23 | 1 | 8/8 |  |
| followup-loss-ratio-next-period | pass | $0.0700 | 30.45 | 2 | 4/6 |  |
| followup-open-claims-other-region | pass | $0.0518 | 22.5 | 2 | 8/8 |  |
| followup-paid-by-payee-other-month | pass | $0.0336 | 15.83 | 1 | 4/4 |  |
