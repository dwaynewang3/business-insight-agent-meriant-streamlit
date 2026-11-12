# Eval run: 20261015-221503-improve1-why

- Model: claude-sonnet-5-5 at medium effort, tools: full (agent 0.1.0+8f6318acbf)
- Passed: **16/16** (95% range 81%–100%)
- Categories: pass 16
- LLM grader: claude-opus-5-5, 16 answers, $0.1021
- Key numbers confirmed by their finding's SQL: 103/109 (94%)
- Cost: $1.1083 ($0.0693 per question)
- Latency: median 29.785s, 95th percentile 58.55s
- Queries per case: 9.25; cache read share of input: 0.935
- Fallback answers: none

| Case | Result | Cost | Seconds | Queries | Numbers | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| why-texas-cost-july-2026 | pass | $0.0843 | 35.26 | 10 | 8/8 |  |
| why-repair-shop-outlier | pass | $0.0882 | 43.07 | 12 | 9/9 |  |
| why-chicago-repair-cost | pass | $0.0792 | 36.65 | 8 | 4/8 |  |
| why-paid-spike-march-2026 | pass | $0.0458 | 22.71 | 6 | 9/9 |  |
| why-southeast-slower-to-close | pass | $0.0582 | 26.64 | 8 | 4/4 |  |
| why-southeast-open-claims | pass | $0.0570 | 30.31 | 6 | 12/12 |  |
| why-q2-average-cost | pass | $0.0889 | 37.91 | 11 | 6/6 |  |
| why-california-home-claims | pass | $0.1018 | 41.18 | 11 | 12/12 |  |
| why-september-low | pass | $0.0499 | 26.05 | 7 | 7/7 |  |
| why-florida-home-september-2025 | pass | $0.1348 | 58.55 | 20 | 8/8 |  |
| why-texas-claims-may-2025 | pass | $0.0625 | 29.63 | 11 | 4/5 |  |
| why-north-water-early-2026 | pass | $0.0540 | 28.04 | 8 | 4/4 |  |
| why-southeast-claims-may-2025 | pass | $0.0518 | 22.78 | 9 | 2/2 |  |
| why-auto-book-shrinking | pass | $0.0611 | 29.94 | 11 | 7/7 |  |
| why-southeast-auto-frequency | pass | $0.0515 | 24.5 | 5 | 3/3 |  |
| why-june-2026-duplicates | pass | $0.0394 | 19.78 | 5 | 4/5 |  |
