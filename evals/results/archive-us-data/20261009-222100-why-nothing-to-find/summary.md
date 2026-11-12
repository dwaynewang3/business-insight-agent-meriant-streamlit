# Eval run: 20261009-222100-why-nothing-to-find

- Model: claude-sonnet-5-5 at medium effort, tools: full (agent 0.1.0+92df8670f7)
- Passed: **5/5** (95% range 57%–100%)
- Categories: pass 5
- LLM grader: claude-opus-5-5, 5 answers, $0.0297
- Key numbers confirmed by their finding's SQL: 19/28 (68%)
- Cost: $0.2547 ($0.0509 per question)
- Latency: median 22.77s, 95th percentile 34.07s
- Queries per case: 6.6; cache read share of input: 0.926
- Fallback answers: none

| Case | Result | Cost | Seconds | Queries | Numbers | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| why-auto-book-shrinking | pass | $0.0475 | 22.77 | 6 | 6/8 |  |
| why-june-2026-duplicates | pass | $0.0379 | 19.9 | 5 | 3/3 |  |
| why-north-water-early-2026 | pass | $0.0570 | 34.07 | 8 | 4/6 |  |
| why-southeast-auto-frequency | pass | $0.0798 | 32.15 | 10 | 5/5 |  |
| why-southeast-claims-may-2025 | pass | $0.0325 | 14.77 | 4 | 1/6 |  |
