# Eval run: 20261019-204720-test-final-why

- Model: claude-sonnet-5-5 at medium effort, tools: full (agent 0.1.0+43e10c675c)
- Passed: **7/7** (95% range 65%–100%)
- Categories: pass 7
- LLM grader: claude-opus-5-5, 7 answers, $0.0405
- Key numbers confirmed by their finding's SQL: 50/50 (100%)
- Cost: $0.8226 ($0.1175 per question)
- Latency: median 50.51s, 95th percentile 67.49s
- Queries per case: 15.29; cache read share of input: 0.974
- Fallback answers: none

| Case | Result | Cost | Seconds | Queries | Numbers | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| why-wa-claims-june-2026 | pass | $0.1159 | 47.93 | 20 | 4/4 |  |
| why-queensland-repair-shops | pass | $0.1176 | 52.64 | 13 | 13/13 |  |
| why-paid-jump-may-2026 | pass | $0.0431 | 32.64 | 4 | 4/4 |  |
| why-vic-tas-slower-to-close | pass | $0.1807 | 60.68 | 20 | 8/8 |  |
| why-nsw-early-theft | pass | $0.1163 | 50.51 | 18 | 12/12 |  |
| why-september-drop | pass | $0.1562 | 67.49 | 20 | 3/3 |  |
| why-queensland-storm-february | pass | $0.0927 | 41.05 | 12 | 6/6 |  |
