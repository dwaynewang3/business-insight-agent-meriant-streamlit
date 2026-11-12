# Eval run: 20261102-210003-final-followup

- Model: claude-sonnet-5-5 at medium effort, tools: full (agent 0.2.0+43e10c675c)
- Passed: **5/5** (95% range 57%–100%)
- Categories: pass 5
- Key numbers confirmed by their finding's SQL: 30/30 (100%)
- Cost: $0.4299 ($0.0860 per question)
- Latency: median 32.3s, 95th percentile 47.78s
- Queries per case: 2.2; cache read share of input: 0.965
- Fallback answers: none

| Case | Result | Cost | Seconds | Queries | Numbers | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| followup-frequency-same-for-home | pass | $0.0734 | 27.76 | 1 | 8/8 |  |
| followup-loss-ratio-next-period | pass | $0.0914 | 40.83 | 2 | 4/4 |  |
| followup-average-cost-by-product | pass | $0.0715 | 32.3 | 2 | 4/4 |  |
| followup-open-claims-other-region | pass | $0.1181 | 47.78 | 3 | 9/9 |  |
| followup-paid-by-payee-other-month | pass | $0.0756 | 30.53 | 3 | 5/5 |  |
