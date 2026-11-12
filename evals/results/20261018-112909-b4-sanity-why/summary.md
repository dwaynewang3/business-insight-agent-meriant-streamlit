# Eval run: 20261018-112909-b4-sanity-why

- Model: claude-sonnet-5-5 at medium effort, tools: full (agent 0.1.0+1ba489d548)
- Passed: **3/3** (95% range 44%–100%)
- Categories: pass 3
- Key numbers confirmed by their finding's SQL: 25/26 (96%)
- Cost: $0.3303 ($0.1101 per question)
- Latency: median 46.52s, 95th percentile 46.96s
- Queries per case: 13; cache read share of input: 0.969
- Fallback answers: none

| Case | Result | Cost | Seconds | Queries | Numbers | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| why-nsw-cost-july-2026 | pass | $0.1254 | 46.96 | 13 | 10/11 |  |
| why-paid-spike-march-2026 | pass | $0.0851 | 34.89 | 11 | 8/8 |  |
| why-west-south-slower-to-close | pass | $0.1198 | 46.52 | 15 | 7/7 |  |
