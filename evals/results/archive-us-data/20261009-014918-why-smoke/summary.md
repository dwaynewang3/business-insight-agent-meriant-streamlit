# Eval run: 20261009-014918-why-smoke

- Model: claude-sonnet-5-5 at medium effort, tools: full (agent 0.1.0+92df8670f7)
- Passed: **3/3** (95% range 44%–100%)
- Categories: pass 3
- LLM grader: claude-opus-5-5, 3 answers, $0.0183
- Key numbers confirmed by their finding's SQL: 16/23 (70%)
- Cost: $0.2127 ($0.0709 per case)
- Latency: median 43.86s, 95th percentile 48.63s
- Queries per case: 8.33; cache read share of input: 0.878
- Fallback answers: none

| Case | Result | Cost | Seconds | Queries | Numbers | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| why-paid-spike-march-2026 | pass | $0.0487 | 29.93 | 7 | 2/4 |  |
| why-southeast-slower-to-close | pass | $0.0765 | 43.86 | 10 | 8/11 |  |
| why-texas-cost-july-2026 | pass | $0.0875 | 48.63 | 8 | 6/8 |  |
