# Eval run: 20261014-232010-why-dev-baseline-x3

- Model: claude-sonnet-5-5 at medium effort, tools: full (agent 0.1.0+92df8670f7)
- Passed in every run: **12/16 cases** (95% range 50%–90%), 3 runs each
- Runs passed: 41/48; per run: 14/16, 13/16, 14/16
- Mixed results across runs: why-chicago-repair-cost, why-southeast-open-claims, why-texas-cost-july-2026
- Categories: pass 41, missing_evidence 3, wrong_explanation 4
- LLM grader: claude-opus-5-5, 48 answers, $0.3219
- Key numbers confirmed by their finding's SQL: 208/304 (68%)
- Cost: $3.0008 ($0.0625 per question)
- Latency: median 29.36s, 95th percentile 54.6s
- Queries per case: 8.6; cache read share of input: 0.925
- Fallback answers: none

| Case | Result | Cost | Seconds | Queries | Numbers | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| why-auto-book-shrinking | pass | $0.0698 | 35.01 | 11 | 8/8 |  |
| why-auto-book-shrinking.r2 | pass | $0.0445 | 25.7 | 6 | 4/8 |  |
| why-auto-book-shrinking.r3 | pass | $0.0537 | 25.05 | 8 | 2/4 |  |
| why-california-home-claims | pass | $0.0669 | 30.81 | 10 | 6/8 |  |
| why-california-home-claims.r2 | pass | $0.0549 | 25.23 | 8 | 1/6 |  |
| why-california-home-claims.r3 | pass | $0.0908 | 36.68 | 15 | 4/6 |  |
| why-chicago-repair-cost | wrong_explanation | $0.0726 | 42.33 | 10 | 1/7 | The agent correctly finds that the non-preferred shop RS-041 is costing more per claim and taking a much larger share of Chicago work. It misses that most of th |
| why-chicago-repair-cost.r2 | pass | $0.0944 | 54.6 | 11 | 8/10 |  |
| why-chicago-repair-cost.r3 | wrong_explanation | $0.0998 | 44.88 | 12 | 4/9 | The agent correctly finds the volume shift to the costly non-preferred shop RS-041 and its rising costs. However, it explicitly rules out adjuster concentration |
| why-florida-home-september-2025 | pass | $0.0374 | 16.56 | 7 | 3/4 |  |
| why-florida-home-september-2025.r2 | pass | $0.0463 | 20.04 | 10 | 1/4 |  |
| why-florida-home-september-2025.r3 | pass | $0.0608 | 32.4 | 10 | 3/7 |  |
| why-june-2026-duplicates | pass | $0.0285 | 15.5 | 3 | 3/3 |  |
| why-june-2026-duplicates.r2 | pass | $0.0299 | 15.4 | 4 | 2/3 |  |
| why-june-2026-duplicates.r3 | pass | $0.0326 | 16.77 | 5 | 1/3 |  |
| why-north-water-early-2026 | pass | $0.0510 | 25.46 | 6 | 9/9 |  |
| why-north-water-early-2026.r2 | pass | $0.0551 | 26.78 | 7 | 3/4 |  |
| why-north-water-early-2026.r3 | pass | $0.0603 | 31.35 | 6 | 6/6 |  |
| why-paid-spike-march-2026 | pass | $0.0617 | 32.07 | 9 | 3/4 |  |
| why-paid-spike-march-2026.r2 | pass | $0.0444 | 23.77 | 7 | 7/7 |  |
| why-paid-spike-march-2026.r3 | pass | $0.0554 | 28.59 | 10 | 4/4 |  |
| why-q2-average-cost | pass | $0.1390 | 67.96 | 19 | 6/8 |  |
| why-q2-average-cost.r2 | pass | $0.0662 | 32.16 | 7 | 7/9 |  |
| why-q2-average-cost.r3 | pass | $0.0961 | 1237.58 | 8 | 5/8 |  |
| why-repair-shop-outlier | missing_evidence | $0.0565 | 28.06 | 6 | 4/6 | The report doesn't mention ADJ-024 or Adam Sanchez. |
| why-repair-shop-outlier.r2 | missing_evidence | $0.0829 | 38.82 | 9 | 8/9 | The report doesn't mention ADJ-024 or Adam Sanchez. |
| why-repair-shop-outlier.r3 | missing_evidence | $0.0762 | 34.42 | 9 | 6/7 | The report doesn't mention ADJ-024 or Adam Sanchez. |
| why-september-low | pass | $0.0460 | 25.57 | 6 | 3/6 |  |
| why-september-low.r2 | pass | $0.0519 | 25.16 | 7 | 4/6 |  |
| why-september-low.r3 | pass | $0.0471 | 23.24 | 7 | 1/5 |  |
| why-southeast-auto-frequency | pass | $0.0439 | 19.64 | 5 | 3/3 |  |
| why-southeast-auto-frequency.r2 | pass | $0.0877 | 36.1 | 13 | 2/5 |  |
| why-southeast-auto-frequency.r3 | pass | $0.0445 | 22.63 | 5 | 3/3 |  |
| why-southeast-claims-may-2025 | pass | $0.0421 | 17.78 | 6 | 2/4 |  |
| why-southeast-claims-may-2025.r2 | pass | $0.0345 | 15.78 | 5 | 2/4 |  |
| why-southeast-claims-may-2025.r3 | pass | $0.0440 | 20.62 | 7 | 5/6 |  |
| why-southeast-open-claims | pass | $0.0592 | 29.71 | 7 | 5/9 |  |
| why-southeast-open-claims.r2 | wrong_explanation | $0.0599 | 30.07 | 7 | 3/9 | The agent correctly identifies the May 2026 departures of two adjusters, and the resulting capacity loss, as the main cause. However, its answer also asserts a  |
| why-southeast-open-claims.r3 | pass | $0.0604 | 29.36 | 8 | 4/8 |  |
| why-southeast-slower-to-close | pass | $0.0685 | 33.67 | 9 | 8/8 |  |
| why-southeast-slower-to-close.r2 | pass | $0.0658 | 30.59 | 11 | 7/7 |  |
| why-southeast-slower-to-close.r3 | pass | $0.0703 | 33.54 | 11 | 9/11 |  |
| why-texas-claims-may-2025 | pass | $0.0592 | 31.37 | 10 | 2/3 |  |
| why-texas-claims-may-2025.r2 | pass | $0.1077 | 52.98 | 20 | 4/7 |  |
| why-texas-claims-may-2025.r3 | pass | $0.0543 | 24.67 | 10 | 3/4 |  |
| why-texas-cost-july-2026 | pass | $0.1020 | 33.15 | 11 | 3/6 |  |
| why-texas-cost-july-2026.r2 | wrong_explanation | $0.0574 | 27.6 | 7 | 6/9 | The agent correctly names the July 14-16 DFW hailstorm as the cause of the jump. However, it also presents large fire and liability claims as a supported second |
| why-texas-cost-july-2026.r3 | pass | $0.0670 | 29.36 | 8 | 10/10 |  |
