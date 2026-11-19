# Eval run: 20261117-235919-stress-why

- Model: claude-sonnet-5-5 at medium effort, tools: full (agent 0.2.0+ce1cc164f7)
- Passed: **3/3** (95% range 44%–100%)
- Categories: pass 3
- LLM grader: claude-opus-5-5, 3 answers, $0.0267
- Key numbers confirmed by their finding's SQL: 21/21 (100%)
- Cost: $0.3790 ($0.1263 per question)
- Latency: median 49.4s, 95th percentile 67.86s
- Queries per case: 15; cache read share of input: 0.962
- Fallback answers: none

| Case | Result | Cost | Seconds | Queries | Numbers | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| why-vic-paid-may-2026 | pass | $0.1618 | 67.86 | 20 | 6/6 |  |
| why-nsw-motor-cost-winter-2026 | pass | $0.1146 | 49.4 | 12 | 8/8 |  |
| why-home-storm-drop-2026 | pass | $0.1027 | 44.64 | 13 | 7/7 |  |
