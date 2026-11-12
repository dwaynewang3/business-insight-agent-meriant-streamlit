# Eval run: 20261015-215027-improve1-what

- Model: claude-sonnet-5-5 at medium effort, tools: full (agent 0.1.0+8f6318acbf)
- Passed: **84/84** (95% range 96%–100%)
- Categories: pass 84
- Key numbers confirmed by their finding's SQL: 307/311 (99%)
- Cost: $2.6701 ($0.0318 per question)
- Latency: median 15.585s, 95th percentile 29.89s
- Queries per case: 4.89; cache read share of input: 0.954
- Fallback answers: none

| Case | Result | Cost | Seconds | Queries | Numbers | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| what-claim-frequency-by-state-auto-2026-q2 | pass | $0.0466 | 12.86 | 3 | 8/8 |  |
| what-claim-frequency-by-state-home-2026-q2 | pass | $0.1347 | 57.95 | 20 | 8/8 |  |
| what-claim-frequency-by-state-auto-2025-q1 | pass | $0.0213 | 13.18 | 2 | 8/8 |  |
| what-claim-frequency-by-state-home-2025-q3 | pass | $0.0394 | 16.91 | 6 | 8/8 |  |
| what-claim-frequency-by-state-auto-2025-q4 | pass | $0.0379 | 16.47 | 5 | 8/8 |  |
| what-claim-frequency-by-state-home-2026-q1 | pass | $0.0349 | 15.47 | 5 | 8/8 |  |
| what-loss-ratio-by-product-2025 | pass | $0.0388 | 18.63 | 4 | 2/2 |  |
| what-loss-ratio-by-product-2026-h1 | pass | $0.0423 | 22.4 | 5 | 2/2 |  |
| what-loss-ratio-by-product-2026-q2 | pass | $0.0287 | 18.89 | 3 | 2/2 |  |
| what-loss-ratio-by-product-the-last-12-months | pass | $0.0468 | 24.8 | 6 | 6/6 |  |
| what-average-claim-cost-auto-tx-2026-q2 | pass | $0.0276 | 17.96 | 4 | 2/2 |  |
| what-average-claim-cost-home-fl-2025 | pass | $0.0381 | 20.02 | 5 | 3/3 |  |
| what-average-claim-cost-auto-il-2025-h1 | pass | $0.0353 | 20.31 | 5 | 2/2 |  |
| what-average-claim-cost-home-ny-2026-q2 | pass | $0.0281 | 13.4 | 4 | 2/2 |  |
| what-average-claim-cost-auto-ca-2025-q3 | pass | $0.0270 | 12.88 | 4 | 2/2 |  |
| what-average-claim-cost-home-tx-2026-07 | pass | $0.0397 | 18.58 | 7 | 2/2 |  |
| what-average-claim-cost-auto-ga-2025-q2 | pass | $0.0346 | 16.74 | 5 | 2/2 |  |
| what-average-claim-cost-home-oh-2026-h1 | pass | $0.0371 | 19.9 | 5 | 2/2 |  |
| what-average-claim-cost-auto-nc-2026-q3 | pass | $0.0340 | 19.76 | 5 | 2/2 |  |
| what-average-claim-cost-by-product-2026-q2 | pass | $0.0319 | 15.7 | 5 | 2/2 |  |
| what-average-claim-cost-by-product-2025 | pass | $0.0372 | 17.62 | 5 | 2/2 |  |
| what-average-claim-cost-by-product-2026-q1 | pass | $0.0459 | 29.89 | 6 | 6/6 |  |
| what-claim-count-by-cause-auto-north-2025-01 | pass | $0.0225 | 11.94 | 4 | 5/5 |  |
| what-claim-count-by-cause-home-north-2026-02 | pass | $0.0148 | 7.59 | 2 | 5/5 |  |
| what-claim-count-by-cause-home-southeast-2025-09 | pass | $0.0184 | 10.04 | 3 | 5/5 |  |
| what-claim-count-by-cause-auto-texas-2026-07 | pass | $0.0255 | 12.8 | 4 | 5/5 |  |
| what-claim-count-by-cause-home-california-2026-06 | pass | $0.0270 | 16.07 | 5 | 5/5 |  |
| what-claim-count-by-cause-auto-southeast-2025-03 | pass | $0.0243 | 14.98 | 4 | 6/6 |  |
| what-claim-count-by-cause-home-texas-2025-05 | pass | $0.0358 | 17.18 | 7 | 5/5 |  |
| what-claim-count-by-cause-auto-california-2026-01 | pass | $0.0355 | 17.93 | 7 | 5/5 |  |
| what-claim-count-by-month-tx-2025 | pass | $0.0243 | 11.47 | 4 | 2/2 |  |
| what-claim-count-by-month-oh-2025 | pass | $0.0247 | 12.03 | 4 | 1/1 |  |
| what-claim-count-by-month-fl-2026-01-2026-09 | pass | $0.0212 | 11.36 | 3 | 3/3 |  |
| what-claim-count-by-month-ny-2026-h1 | pass | $0.0353 | 23.04 | 6 | 6/6 |  |
| what-open-claims-by-adjuster-southeast | pass | $0.0195 | 11.74 | 3 | 6/6 |  |
| what-open-claims-by-adjuster-texas | pass | $0.0386 | 24.75 | 7 | 4/4 |  |
| what-open-claims-by-adjuster-north | pass | $0.0228 | 11.49 | 4 | 3/3 |  |
| what-open-claims-by-adjuster-california | pass | $0.0335 | 16.55 | 6 | 7/7 |  |
| what-median-cycle-time-by-region-2025-q1 | pass | $0.0164 | 8.61 | 2 | 4/4 |  |
| what-median-cycle-time-by-region-2025-q3 | pass | $0.0231 | 14.46 | 4 | 4/4 |  |
| what-median-cycle-time-by-region-2026-q1 | pass | $0.0194 | 10.82 | 3 | 4/4 |  |
| what-median-cycle-time-by-region-2026-q2 | pass | $0.0250 | 13.37 | 4 | 4/4 |  |
| what-paid-amount-by-month-2026-q1 | pass | $0.0265 | 17.25 | 4 | 5/5 |  |
| what-paid-amount-by-month-2025-h2 | pass | $0.0350 | 18.09 | 6 | 6/6 |  |
| what-paid-amount-by-month-2026-q2 | pass | $0.0333 | 17.92 | 7 | 3/3 |  |
| what-paid-amount-by-payee-2025-06 | pass | $0.0214 | 10.95 | 4 | 4/4 |  |
| what-paid-amount-by-payee-2026-03 | pass | $0.0297 | 18.51 | 5 | 0/4 |  |
| what-paid-amount-by-payee-2026-08 | pass | $0.0467 | 23.63 | 10 | 4/4 |  |
| what-policies-in-force-by-state-home-2026-06 | pass | $0.0170 | 8.1 | 2 | 8/8 |  |
| what-policies-in-force-by-state-auto-2025-12 | pass | $0.0172 | 8.22 | 2 | 8/8 |  |
| what-policies-in-force-by-state-home-2025 | pass | $0.0340 | 64.68 | 6 | 8/8 |  |
| what-earned-premium-by-product-2025 | pass | $0.0149 | 10.64 | 2 | 2/2 |  |
| what-earned-premium-by-product-2026-h1 | pass | $0.0111 | 5.72 | 1 | 2/2 |  |
| what-earned-premium-by-product-2026-q3 | pass | $0.0148 | 7.33 | 2 | 2/2 |  |
| what-claim-count-by-channel-home-2025 | pass | $0.0379 | 20.49 | 7 | 5/5 |  |
| what-claim-count-by-channel-home-2026-h1 | pass | $0.0196 | 12.93 | 3 | 4/4 |  |
| what-claim-count-by-channel-auto-2026-q3 | pass | $0.0243 | 15.94 | 4 | 3/3 |  |
| what-top-states-by-loss-ratio-3-home-2025 | pass | $0.0365 | 23.01 | 3 | 3/3 |  |
| what-top-states-by-loss-ratio-3-auto-2026-h1 | pass | $0.0611 | 29.28 | 7 | 3/3 |  |
| what-top-states-by-loss-ratio-2-auto-2025 | pass | $0.0391 | 21.26 | 4 | 2/2 |  |
| what-cause-share-auto-glass-2026-q1 | pass | $0.0205 | 10.13 | 4 | 3/3 |  |
| what-cause-share-home-water-damage-2025 | pass | $0.0230 | 14.4 | 4 | 3/3 |  |
| what-cause-share-auto-hail-2026-q3 | pass | $0.0190 | 11.38 | 3 | 3/3 |  |
| what-cause-share-home-wind-hail-2026-q3 | pass | $0.0152 | 8.68 | 1 | 3/3 |  |
| what-claim-count-change-home-2025-q2-2026-q2 | pass | $0.0252 | 13.45 | 3 | 3/3 |  |
| what-claim-count-change-auto-2025-h1-2026-h1 | pass | $0.1101 | 44.17 | 20 | 3/3 |  |
| what-claim-count-change-home-2025-q1-2026-q1 | pass | $0.0243 | 11.49 | 3 | 3/3 |  |
| what-shop-average-claim-cost-chicago-2025 | pass | $0.0528 | 23.33 | 8 | 4/4 |  |
| what-shop-average-claim-cost-chicago-2026-03-2026-09 | pass | $0.0563 | 27.61 | 9 | 5/5 |  |
| what-shop-average-claim-cost-dallas-fort-worth-2026-h1 | pass | $0.0721 | 35.75 | 11 | 6/6 |  |
| what-shop-average-claim-cost-miami-2025 | pass | $0.0409 | 20.18 | 8 | 4/4 |  |
| what-open-claims-by-region-texas | pass | $0.0130 | 8.39 | 2 | 1/1 |  |
| what-open-claims-by-region-california | pass | $0.0146 | 8.96 | 3 | 1/1 |  |
| what-open-claims-by-region-southeast | pass | $0.0142 | 6.66 | 3 | 1/1 |  |
| what-open-claims-by-region-north | pass | $0.0148 | 8.91 | 3 | 1/1 |  |
| what-incurred-losses-total-home-2026-q3 | pass | $0.0255 | 15.06 | 4 | 1/1 |  |
| what-incurred-losses-total-auto-2025 | pass | $0.0371 | 20.15 | 6 | 2/2 |  |
| what-incurred-losses-total-home-2026-q1 | pass | $0.0392 | 22.9 | 5 | 2/2 |  |
| what-claims-reported-2026-08 | pass | $0.0147 | 9.81 | 3 | 1/1 |  |
| what-claims-reported-2026-01 | pass | $0.0161 | 9.29 | 3 | 1/1 |  |
| what-claim-count-total-2025-q4 | pass | $0.0150 | 6.99 | 3 | 1/1 |  |
| what-claim-count-total-last-month | pass | $0.0261 | 14.97 | 5 | 1/1 |  |
| what-paid-amount-total-2025 | pass | $0.0229 | 12.98 | 5 | 1/1 |  |
| what-paid-amount-total-2026-so-far | pass | $0.0422 | 21.91 | 8 | 3/3 |  |
