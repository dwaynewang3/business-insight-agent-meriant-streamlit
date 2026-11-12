# Eval run: 20261015-212151-exp1-semantic-off

- Model: claude-sonnet-5-5 at medium effort, tools: semantic_off (agent 0.1.0+8f58416920)
- Passed: **83/84** (95% range 94%–100%)
- Categories: pass 83, wrong_result 1
- Key numbers confirmed by their finding's SQL: 328/340 (96%)
- Cost: $1.8206 ($0.0217 per question)
- Latency: median 10.370000000000001s, 95th percentile 19.8s
- Queries per case: 3.07; cache read share of input: 0.925
- Fallback answers: none

| Case | Result | Cost | Seconds | Queries | Numbers | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| what-claim-frequency-by-state-auto-2026-q2 | pass | $0.0389 | 16.13 | 2 | 8/8 |  |
| what-claim-frequency-by-state-home-2026-q2 | pass | $0.0233 | 12.18 | 2 | 8/8 |  |
| what-claim-frequency-by-state-auto-2025-q1 | wrong_result | $0.0229 | 13.17 | 3 | 8/8 | No column in the answer matches the reference's claim_frequency. |
| what-claim-frequency-by-state-home-2025-q3 | pass | $0.0195 | 10.5 | 2 | 2/2 |  |
| what-claim-frequency-by-state-auto-2025-q4 | pass | $0.0343 | 16.51 | 5 | 8/8 |  |
| what-claim-frequency-by-state-home-2026-q1 | pass | $0.0199 | 9.71 | 2 | 8/8 |  |
| what-loss-ratio-by-product-2025 | pass | $0.0362 | 17.46 | 5 | 6/6 |  |
| what-loss-ratio-by-product-2026-h1 | pass | $0.0309 | 15.29 | 4 | 6/6 |  |
| what-loss-ratio-by-product-2026-q2 | pass | $0.0339 | 17.41 | 4 | 6/6 |  |
| what-loss-ratio-by-product-the-last-12-months | pass | $0.0447 | 23.96 | 5 | 2/4 |  |
| what-average-claim-cost-auto-tx-2026-q2 | pass | $0.0362 | 19.95 | 5 | 2/2 |  |
| what-average-claim-cost-home-fl-2025 | pass | $0.0278 | 16.3 | 4 | 3/3 |  |
| what-average-claim-cost-auto-il-2025-h1 | pass | $0.0261 | 15.73 | 4 | 3/3 |  |
| what-average-claim-cost-home-ny-2026-q2 | pass | $0.0293 | 15.52 | 5 | 2/3 |  |
| what-average-claim-cost-auto-ca-2025-q3 | pass | $0.0238 | 13.43 | 3 | 3/3 |  |
| what-average-claim-cost-home-tx-2026-07 | pass | $0.0238 | 14.41 | 3 | 4/4 |  |
| what-average-claim-cost-auto-ga-2025-q2 | pass | $0.0281 | 16.19 | 4 | 3/3 |  |
| what-average-claim-cost-home-oh-2026-h1 | pass | $0.0362 | 19.41 | 5 | 4/4 |  |
| what-average-claim-cost-auto-nc-2026-q3 | pass | $0.0276 | 18.1 | 4 | 2/2 |  |
| what-average-claim-cost-by-product-2026-q2 | pass | $0.0352 | 18.65 | 5 | 4/4 |  |
| what-average-claim-cost-by-product-2025 | pass | $0.0351 | 19.18 | 5 | 4/4 |  |
| what-average-claim-cost-by-product-2026-q1 | pass | $0.0302 | 17.44 | 4 | 4/4 |  |
| what-claim-count-by-cause-auto-north-2025-01 | pass | $0.0132 | 9.27 | 2 | 6/6 |  |
| what-claim-count-by-cause-home-north-2026-02 | pass | $0.0131 | 7.15 | 2 | 5/5 |  |
| what-claim-count-by-cause-home-southeast-2025-09 | pass | $0.0129 | 6.38 | 2 | 6/6 |  |
| what-claim-count-by-cause-auto-texas-2026-07 | pass | $0.0145 | 9.67 | 2 | 6/6 |  |
| what-claim-count-by-cause-home-california-2026-06 | pass | $0.0133 | 8.31 | 2 | 5/5 |  |
| what-claim-count-by-cause-auto-southeast-2025-03 | pass | $0.0130 | 7.63 | 2 | 6/6 |  |
| what-claim-count-by-cause-home-texas-2025-05 | pass | $0.0131 | 6.5 | 2 | 6/6 |  |
| what-claim-count-by-cause-auto-california-2026-01 | pass | $0.0137 | 8.26 | 2 | 5/5 |  |
| what-claim-count-by-month-tx-2025 | pass | $0.0137 | 7.9 | 2 | 3/3 |  |
| what-claim-count-by-month-oh-2025 | pass | $0.0145 | 7.69 | 2 | 3/3 |  |
| what-claim-count-by-month-fl-2026-01-2026-09 | pass | $0.0167 | 9.16 | 2 | 9/9 |  |
| what-claim-count-by-month-ny-2026-h1 | pass | $0.0154 | 8.92 | 2 | 6/6 |  |
| what-open-claims-by-adjuster-southeast | pass | $0.0159 | 9.13 | 2 | 6/6 |  |
| what-open-claims-by-adjuster-texas | pass | $0.0168 | 8.06 | 2 | 3/3 |  |
| what-open-claims-by-adjuster-north | pass | $0.0185 | 9.91 | 3 | 3/3 |  |
| what-open-claims-by-adjuster-california | pass | $0.0183 | 9.67 | 3 | 3/3 |  |
| what-median-cycle-time-by-region-2025-q1 | pass | $0.0147 | 7.97 | 2 | 4/4 |  |
| what-median-cycle-time-by-region-2025-q3 | pass | $0.0140 | 7.41 | 2 | 4/4 |  |
| what-median-cycle-time-by-region-2026-q1 | pass | $0.0177 | 9.37 | 3 | 4/4 |  |
| what-median-cycle-time-by-region-2026-q2 | pass | $0.0161 | 9.33 | 2 | 4/4 |  |
| what-paid-amount-by-month-2026-q1 | pass | $0.0297 | 14.64 | 4 | 1/4 |  |
| what-paid-amount-by-month-2025-h2 | pass | $0.0237 | 11.58 | 3 | 6/6 |  |
| what-paid-amount-by-month-2026-q2 | pass | $0.0150 | 8.63 | 2 | 3/3 |  |
| what-paid-amount-by-payee-2025-06 | pass | $0.0147 | 8.56 | 2 | 4/4 |  |
| what-paid-amount-by-payee-2026-03 | pass | $0.0315 | 15.32 | 6 | 6/6 |  |
| what-paid-amount-by-payee-2026-08 | pass | $0.0196 | 10.98 | 4 | 4/4 |  |
| what-policies-in-force-by-state-home-2026-06 | pass | $0.0109 | 6.91 | 2 | 3/3 |  |
| what-policies-in-force-by-state-auto-2025-12 | pass | $0.0135 | 10.65 | 2 | 8/8 |  |
| what-policies-in-force-by-state-home-2025 | pass | $0.0140 | 7.83 | 2 | 8/8 |  |
| what-earned-premium-by-product-2025 | pass | $0.0109 | 6.24 | 2 | 2/2 |  |
| what-earned-premium-by-product-2026-h1 | pass | $0.0107 | 6.93 | 2 | 2/2 |  |
| what-earned-premium-by-product-2026-q3 | pass | $0.0109 | 6.09 | 2 | 2/2 |  |
| what-claim-count-by-channel-home-2025 | pass | $0.0130 | 7.22 | 2 | 3/3 |  |
| what-claim-count-by-channel-home-2026-h1 | pass | $0.0145 | 7.54 | 2 | 4/4 |  |
| what-claim-count-by-channel-auto-2026-q3 | pass | $0.0139 | 7.63 | 2 | 3/3 |  |
| what-top-states-by-loss-ratio-3-home-2025 | pass | $0.0346 | 16.81 | 4 | 3/3 |  |
| what-top-states-by-loss-ratio-3-auto-2026-h1 | pass | $0.0411 | 19.63 | 6 | 3/3 |  |
| what-top-states-by-loss-ratio-2-auto-2025 | pass | $0.0311 | 16.02 | 3 | 3/3 |  |
| what-cause-share-auto-glass-2026-q1 | pass | $0.0177 | 10.38 | 3 | 3/3 |  |
| what-cause-share-home-water-damage-2025 | pass | $0.0134 | 7.01 | 2 | 3/3 |  |
| what-cause-share-auto-hail-2026-q3 | pass | $0.0224 | 10.95 | 3 | 2/4 |  |
| what-cause-share-home-wind-hail-2026-q3 | pass | $0.0143 | 7.82 | 2 | 3/3 |  |
| what-claim-count-change-home-2025-q2-2026-q2 | pass | $0.0194 | 11.15 | 3 | 2/3 |  |
| what-claim-count-change-auto-2025-h1-2026-h1 | pass | $0.0214 | 10.45 | 3 | 2/3 |  |
| what-claim-count-change-home-2025-q1-2026-q1 | pass | $0.0172 | 8.45 | 2 | 2/3 |  |
| what-shop-average-claim-cost-chicago-2025 | pass | $0.0316 | 21.33 | 5 | 3/3 |  |
| what-shop-average-claim-cost-chicago-2026-03-2026-09 | pass | $0.0387 | 20.22 | 6 | 3/3 |  |
| what-shop-average-claim-cost-dallas-fort-worth-2026-h1 | pass | $0.0349 | 16.96 | 5 | 4/4 |  |
| what-shop-average-claim-cost-miami-2025 | pass | $0.0351 | 19.8 | 5 | 4/4 |  |
| what-open-claims-by-region-texas | pass | $0.0112 | 6.54 | 2 | 2/2 |  |
| what-open-claims-by-region-california | pass | $0.0110 | 6.98 | 2 | 2/2 |  |
| what-open-claims-by-region-southeast | pass | $0.0113 | 6.54 | 2 | 2/2 |  |
| what-open-claims-by-region-north | pass | $0.0113 | 7.37 | 2 | 2/2 |  |
| what-incurred-losses-total-home-2026-q3 | pass | $0.0290 | 14.45 | 4 | 4/4 |  |
| what-incurred-losses-total-auto-2025 | pass | $0.0390 | 18.7 | 6 | 5/5 |  |
| what-incurred-losses-total-home-2026-q1 | pass | $0.0278 | 15.37 | 4 | 3/4 |  |
| what-claims-reported-2026-08 | pass | $0.0107 | 5.7 | 2 | 1/1 |  |
| what-claims-reported-2026-01 | pass | $0.0106 | 6.14 | 2 | 1/1 |  |
| what-claim-count-total-2025-q4 | pass | $0.0161 | 8.85 | 3 | 2/2 |  |
| what-claim-count-total-last-month | pass | $0.0167 | 10.36 | 3 | 3/3 |  |
| what-paid-amount-total-2025 | pass | $0.0187 | 11.64 | 3 | 2/2 |  |
| what-paid-amount-total-2026-so-far | pass | $0.0244 | 13.02 | 4 | 3/3 |  |
