# Eval run: 20261016-234053-b4-sanity-why

- Model: claude-sonnet-5-5 at medium effort, tools: full (agent 0.1.0+627eeab97c)
- Passed: **0/3** (95% range 0%–56%)
- Categories: error 3
- Cost: $0.0000 ($0.0000 per question)
- Latency: median 0.84s, 95th percentile 1.59s
- Queries per case: 0; cache read share of input: None
- Fallback answers: none

| Case | Result | Cost | Seconds | Queries | Numbers | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| why-nsw-cost-july-2026 | error | $0.0000 | 1.59 | 0 |  | API error: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'The compiled grammar is too large, which would cause perfo |
| why-paid-spike-march-2026 | error | $0.0000 | 0.84 | 0 |  | API error: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'The compiled grammar is too large, which would cause perfo |
| why-west-south-slower-to-close | error | $0.0000 | 0.8 | 0 |  | API error: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'The compiled grammar is too large, which would cause perfo |
