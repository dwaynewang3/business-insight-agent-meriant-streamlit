# Eval run: 20261014-224733-full-what-dev-baseline

- Model: claude-sonnet-5-5 at medium effort, tools: full (agent 0.1.0+92df8670f7)
- Passed: **84/84** (95% range 96%–100%)
- Categories: pass 84
- Key numbers confirmed by their finding's SQL: 306/336 (91%)
- Cost: $2.3510 ($0.0280 per case)
- Latency: median 12.92s, 95th percentile 29.51s
- Queries per case: 4.4; cache read share of input: 0.946
- Fallback answers: none

| Case | Result | Cost | Seconds | Queries | Numbers | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| what-claim-frequency-by-state-auto-2026-q2 | pass | $0.0389 | 19.6 | 2 | 8/8 |  |
| what-claim-frequency-by-state-home-2026-q2 | pass | $0.0413 | 34.87 | 6 | 8/8 |  |
| what-claim-frequency-by-state-auto-2025-q1 | pass | $0.0218 | 12.81 | 2 | 8/8 |  |
| what-claim-frequency-by-state-home-2025-q3 | pass | $0.0236 | 11.86 | 3 | 8/8 |  |
| what-claim-frequency-by-state-auto-2025-q4 | pass | $0.0203 | 9.31 | 2 | 8/8 |  |
| what-claim-frequency-by-state-home-2026-q1 | pass | $0.0283 | 13.84 | 4 | 8/8 |  |
| what-loss-ratio-by-product-2025 | pass | $0.0397 | 19.58 | 5 | 4/4 |  |
| what-loss-ratio-by-product-2026-h1 | pass | $0.0511 | 25.9 | 6 | 2/4 |  |
| what-loss-ratio-by-product-2026-q2 | pass | $0.0360 | 29.51 | 5 | 2/2 |  |
| what-loss-ratio-by-product-the-last-12-months | pass | $0.0484 | 22.25 | 6 | 2/4 |  |
| what-average-claim-cost-auto-tx-2026-q2 | pass | $0.0270 | 14.24 | 4 | 1/1 |  |
| what-average-claim-cost-home-fl-2025 | pass | $0.0540 | 24.58 | 10 | 2/3 |  |
| what-average-claim-cost-auto-il-2025-h1 | pass | $0.0324 | 15.8 | 5 | 2/2 |  |
| what-average-claim-cost-home-ny-2026-q2 | pass | $0.0330 | 31.46 | 5 | 2/2 |  |
| what-average-claim-cost-auto-ca-2025-q3 | pass | $0.0266 | 41.89 | 4 | 2/2 |  |
| what-average-claim-cost-home-tx-2026-07 | pass | $0.0268 | 12.68 | 4 | 2/2 |  |
| what-average-claim-cost-auto-ga-2025-q2 | pass | $0.0266 | 13.54 | 4 | 2/2 |  |
| what-average-claim-cost-home-oh-2026-h1 | pass | $0.0392 | 22.71 | 6 | 2/3 |  |
| what-average-claim-cost-auto-nc-2026-q3 | pass | $0.0423 | 28.2 | 7 | 2/2 |  |
| what-average-claim-cost-by-product-2026-q2 | pass | $0.0268 | 15.24 | 4 | 2/2 |  |
| what-average-claim-cost-by-product-2025 | pass | $0.0369 | 21.93 | 6 | 3/4 |  |
| what-average-claim-cost-by-product-2026-q1 | pass | $0.0451 | 22.02 | 6 | 5/7 |  |
| what-claim-count-by-cause-auto-north-2025-01 | pass | $0.0183 | 8.79 | 3 | 5/5 |  |
| what-claim-count-by-cause-home-north-2026-02 | pass | $0.0258 | 12.8 | 5 | 5/5 |  |
| what-claim-count-by-cause-home-southeast-2025-09 | pass | $0.0268 | 15.06 | 5 | 6/6 |  |
| what-claim-count-by-cause-auto-texas-2026-07 | pass | $0.0193 | 8.63 | 3 | 6/6 |  |
| what-claim-count-by-cause-home-california-2026-06 | pass | $0.0147 | 7.73 | 2 | 5/5 |  |
| what-claim-count-by-cause-auto-southeast-2025-03 | pass | $0.0160 | 7.39 | 2 | 6/6 |  |
| what-claim-count-by-cause-home-texas-2025-05 | pass | $0.0263 | 11.49 | 5 | 6/6 |  |
| what-claim-count-by-cause-auto-california-2026-01 | pass | $0.0301 | 13.62 | 6 | 6/6 |  |
| what-claim-count-by-month-tx-2025 | pass | $0.0243 | 11.0 | 4 | 3/3 |  |
| what-claim-count-by-month-oh-2025 | pass | $0.0170 | 7.95 | 2 | 1/1 |  |
| what-claim-count-by-month-fl-2026-01-2026-09 | pass | $0.0350 | 15.28 | 6 | 9/9 |  |
| what-claim-count-by-month-ny-2026-h1 | pass | $0.0248 | 13.03 | 4 | 6/6 |  |
| what-open-claims-by-adjuster-southeast | pass | $0.0246 | 12.54 | 4 | 6/6 |  |
| what-open-claims-by-adjuster-texas | pass | $0.0236 | 12.42 | 4 | 3/3 |  |
| what-open-claims-by-adjuster-north | pass | $0.0189 | 9.75 | 3 | 7/7 |  |
| what-open-claims-by-adjuster-california | pass | $0.0321 | 17.59 | 6 | 7/7 |  |
| what-median-cycle-time-by-region-2025-q1 | pass | $0.0221 | 10.95 | 4 | 4/4 |  |
| what-median-cycle-time-by-region-2025-q3 | pass | $0.0228 | 10.39 | 4 | 4/4 |  |
| what-median-cycle-time-by-region-2026-q1 | pass | $0.0229 | 9.82 | 4 | 4/4 |  |
| what-median-cycle-time-by-region-2026-q2 | pass | $0.0206 | 11.16 | 3 | 4/4 |  |
| what-paid-amount-by-month-2026-q1 | pass | $0.0343 | 16.61 | 5 | 1/5 |  |
| what-paid-amount-by-month-2025-h2 | pass | $0.0382 | 18.22 | 7 | 7/7 |  |
| what-paid-amount-by-month-2026-q2 | pass | $0.0216 | 11.1 | 4 | 3/3 |  |
| what-paid-amount-by-payee-2025-06 | pass | $0.0263 | 13.31 | 5 | 4/4 |  |
| what-paid-amount-by-payee-2026-03 | pass | $0.0279 | 13.97 | 5 | 4/4 |  |
| what-paid-amount-by-payee-2026-08 | pass | $0.0194 | 9.99 | 4 | 4/4 |  |
| what-policies-in-force-by-state-home-2026-06 | pass | $0.0169 | 7.96 | 2 | 8/8 |  |
| what-policies-in-force-by-state-auto-2025-12 | pass | $0.0190 | 8.66 | 3 | 8/8 |  |
| what-policies-in-force-by-state-home-2025 | pass | $0.0166 | 11.81 | 2 | 8/8 |  |
| what-earned-premium-by-product-2025 | pass | $0.0124 | 5.9 | 2 | 2/2 |  |
| what-earned-premium-by-product-2026-h1 | pass | $0.0142 | 7.63 | 2 | 2/2 |  |
| what-earned-premium-by-product-2026-q3 | pass | $0.0124 | 6.7 | 2 | 2/2 |  |
| what-claim-count-by-channel-home-2025 | pass | $0.0349 | 27.81 | 7 | 3/4 |  |
| what-claim-count-by-channel-home-2026-h1 | pass | $0.0198 | 12.1 | 3 | 4/4 |  |
| what-claim-count-by-channel-auto-2026-q3 | pass | $0.0300 | 18.82 | 6 | 3/3 |  |
| what-top-states-by-loss-ratio-3-home-2025 | pass | $0.0336 | 17.57 | 3 | 0/4 |  |
| what-top-states-by-loss-ratio-3-auto-2026-h1 | pass | $0.0440 | 21.38 | 4 | 3/3 |  |
| what-top-states-by-loss-ratio-2-auto-2025 | pass | $0.0385 | 18.82 | 5 | 3/3 |  |
| what-cause-share-auto-glass-2026-q1 | pass | $0.0140 | 10.83 | 2 | 2/3 |  |
| what-cause-share-home-water-damage-2025 | pass | $0.0131 | 6.87 | 2 | 3/3 |  |
| what-cause-share-auto-hail-2026-q3 | pass | $0.0236 | 11.11 | 4 | 4/6 |  |
| what-cause-share-home-wind-hail-2026-q3 | pass | $0.0181 | 9.08 | 3 | 3/3 |  |
| what-claim-count-change-home-2025-q2-2026-q2 | pass | $0.0261 | 12.57 | 4 | 2/3 |  |
| what-claim-count-change-auto-2025-h1-2026-h1 | pass | $0.0330 | 14.0 | 5 | 3/3 |  |
| what-claim-count-change-home-2025-q1-2026-q1 | pass | $0.0245 | 10.22 | 4 | 2/3 |  |
| what-shop-average-claim-cost-chicago-2025 | pass | $0.0495 | 35.63 | 7 | 3/3 |  |
| what-shop-average-claim-cost-chicago-2026-03-2026-09 | pass | $0.0569 | 24.03 | 9 | 3/3 |  |
| what-shop-average-claim-cost-dallas-fort-worth-2026-h1 | pass | $0.0476 | 23.26 | 8 | 4/4 |  |
| what-shop-average-claim-cost-miami-2025 | pass | $0.0469 | 23.39 | 7 | 4/4 |  |
| what-open-claims-by-region-texas | pass | $0.0199 | 10.08 | 4 | 1/1 |  |
| what-open-claims-by-region-california | pass | $0.0166 | 7.94 | 4 | 1/1 |  |
| what-open-claims-by-region-southeast | pass | $0.0162 | 7.44 | 3 | 1/1 |  |
| what-open-claims-by-region-north | pass | $0.0172 | 8.21 | 4 | 2/2 |  |
| what-incurred-losses-total-home-2026-q3 | pass | $0.0288 | 14.0 | 5 | 1/1 |  |
| what-incurred-losses-total-auto-2025 | pass | $0.0327 | 14.69 | 6 | 1/3 |  |
| what-incurred-losses-total-home-2026-q1 | pass | $0.0349 | 20.58 | 5 | 1/3 |  |
| what-claims-reported-2026-08 | pass | $0.0177 | 11.12 | 4 | 1/1 |  |
| what-claims-reported-2026-01 | pass | $0.0174 | 8.89 | 4 | 1/2 |  |
| what-claim-count-total-2025-q4 | pass | $0.0190 | 8.32 | 4 | 1/1 |  |
| what-claim-count-total-last-month | pass | $0.0230 | 11.87 | 4 | 0/2 |  |
| what-paid-amount-total-2025 | pass | $0.0293 | 13.7 | 6 | 2/2 |  |
| what-paid-amount-total-2026-so-far | pass | $0.0325 | 18.21 | 6 | 3/3 |  |
