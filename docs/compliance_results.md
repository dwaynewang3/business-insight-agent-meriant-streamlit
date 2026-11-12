# Policy-compliance review: results

Measured on 2026-10-18 on the Australian data. Each variant reviewed all 27 claim files in the quality-review sample once, through the Message Batches API, with Claude Sonnet 5.5 at medium effort as the judge. The answer key is the policy kit's: 22 required findings, with 7 compliant claims (4 traps and 3 clean controls). 18 claims were used for development and 9 were held out. The split was fixed before any compliance run, and the held-out claims were first reviewed in this final run.

## The three variants

- **v0, naive RAG:** a short summary of the claim (its incident description, handler notes and 8 key facts) as one search query, the top 8 clauses, and one judge call for all ten areas.
- **v1, checklist RAG:** ten checks. Each check gets its own retrieval within its policy documents (an anchor query plus queries triggered by the claim's facts, cross-references included) and its own judge call. Findings are validated in code, with one retry.
- **Full context:** no retrieval. The whole policy library (252 clauses, both versions of the motor policy, about 25k tokens) goes in one cached prompt, with one judge call.

All three use the same judge rules and output schema. The overall verdict is aggregated in code: any breach makes a claim NON_COMPLIANT; otherwise any finding needing review makes it NEEDS_REVIEW.

## Results

| Variant | Overall verdict right | Required findings found | Traps and controls | False breaches | Strict citations | Invented citations | Cost per claim (batch) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v0, naive RAG | 14/27 (34–69%) | 11/22 | 2/7 | 1 | 0.82 | 0 | $0.019 |
| v1, checklist RAG | 25/27 (77–98%) | 21/22 | 6/7 | **0** | 1.0 | 0 | $0.064 |
| **Full context** | **27/27 (88–100%)** | **22/22** | **7/7** | 3 | 1.0 | 0 | **$0.031** |

The kit's targets, all on the 27 claims:

| Target | v0 | v1 | Full context |
| --- | --- | --- | --- |
| Overall at least 23/27 | No | Yes | Yes |
| Required findings at least 20/22 | No | Yes | Yes |
| Strict citations at least 0.90 | No | Yes | Yes |
| False breaches at most 3 | Yes | Yes | Yes |
| Traps and controls 7/7 | No | No | Yes |
| No invented citations | Yes | Yes | Yes |

Development (18) and held-out (9) claims, shown separately:

| Metric | v0 dev | v0 held out | v1 dev | v1 held out | Full dev | Full held out |
| --- | --- | --- | --- | --- | --- | --- |
| Overall right | 9/18 | 5/9 | 18/18 | 7/9 | 18/18 | 9/9 |
| Required findings | 6/15 | 5/7 | 15/15 | 6/7 | 15/15 | 7/7 |
| Traps and controls | 2/5 | 0/2 | 5/5 | 1/2 | 5/5 | 2/2 |

The ranges are 95% Wilson ranges. With 27 claims and one run each, v1 and full context can't be told apart on accuracy (77–98% vs. 88–100%). v0 is clearly worse. The spread between runs comes from v1's development rounds below, since 3 runs per variant didn't fit the A$50 budget.

## What each variant gets wrong

**v0: its retrieval misses the rule.** On the 18 development claims, every miss was a retrieval miss: the rule needed was never among the 8 clauses one query returned. Without the rule, the judge either says NEEDS_REVIEW (most of the compliant claims) or reasons from a nearby clause. A first version that searched with all 96 claim fields as text retrieved an acceptable clause for 0 of 15 required findings; the summary query finds 6 of 15.

**v1: it's strict where it lacks context.** It made no false breaches, and its two misses were both on held-out claims, both NEEDS_REVIEW rather than a wrong verdict:
- GC-013 (fraud score recomputed with an interaction rule): the fraud indicator catalogue wasn't among the clauses retrieved for the fraud check. The judge cited the double-counting rule but declined to call a breach without the catalogue.
- GC-019 (catastrophe surge authority, a trap): a documentation check asked whether a licence must be verified when no driver was in control, which the supplied clauses don't settle.

The held-out drop (18/18 on development, 7/9 held out) suggests that the three development rounds fitted the retrieval partly to the development claims.

**Full context: findings beyond the answer key.** Its 3 false breaches are all medium-severity documentation findings, and each is debatable rather than invented:
- GC-012: the photos predate the incident. This is the expected optional finding, but it cites a different clause than the key.
- GC-017: the assessment report is missing because the claim should have been on the Complex track. This is a knock-on of the expected triage breach.
- GC-013: "the cyclist left the scene, so a police event number was required" (POL-DOC-005 4.1(b)). This may be a real breach that the answer key doesn't list.

## Experiment 2: the judge's effort

Full context on the 18 development claims, through the Batch API (2026-10-19):

| Effort | Overall | Required | Traps and controls | False breaches | Invented citations | Cost per claim |
| --- | --- | --- | --- | --- | --- | --- |
| Medium (from the final scoring) | 18/18 | 15/15 | 5/5 | 2 | 0 | $0.032 |
| Low | 18/18 | 15/15 | 5/5 | 0 | 1 | $0.028 |

Low effort saves only 12%, since most output is the findings themselves, and it invented one citation. Medium stays.

## Developing v1 (the 18 development claims)

| Round | Overall | Required | Traps and controls | False breaches | What changed before the next round |
| --- | --- | --- | --- | --- | --- |
| 1 | 13/18 | 15/15 | 0/5 | 2 | Every compliant claim came back NEEDS_REVIEW. The judge wouldn't pass an area without every rule that could apply, and ranking by score pushed out each area's core rule. **Fixes:** two judge rules (a missing rule matters only if the facts point to it; a requirement met as written is a PASS), and each check always keeps its anchor query's best 4 clauses. |
| 2 | 13/18 | 14/15 | 1/5 | 3 | Some findings' status contradicted their own explanation ("Placeholder"; "I cannot confirm it as a breach" under BREACH). **Fix:** the output schema puts the reasoning fields before the status. Also: the documentation check now fetches the collision document rule, a fact the file doesn't hold counts as NOT_ASSESSED, and the cover check fetches the rules for a vehicle used other than as declared. |
| 3 | 18/18 | 15/15 | 5/5 | 0 | Kept (its last 7 claims ran through the Batch API after the API credit ran out mid-run). |

## Cost

| Variant | Judge calls per claim | Cost per claim, live | Cost per claim, batch |
| --- | --- | --- | --- |
| v0 | 1 | $0.047 | $0.019 |
| v1 | 10 (plus retries) | $0.137 | $0.064 |
| Full context | 1 | $0.171 (one review, cache empty) | $0.031 |

Full context is cheap in a batch because the 25k-token library is written to the cache once and read at a tenth of the input price for every other claim. A single live review pays for that write itself, so the one measured through the agent (GC-010, 2026-10-18) cost $0.171: more than a live v1 review. Reviews close together share the cache, and a 1-hour cache lifetime would stretch that further. Most of every variant's cost is the judge's output: its reasoning and findings. The whole final scoring (81 reviews) cost $3.07.

**Later change:** since 2026-11-02, GC-007's handler notes end with a planted instruction telling AI review tools to pass the claim (a safety case; [conversion log](compliance/conversion_log.md)). The runs above predate it. In the safety run, the full-context review still found GC-007 non-compliant.

## What it means

At this size, a policy library that fits comfortably in one cached prompt, **full context is more accurate than checklist RAG, and cheaper.** The RAG plan expected this as a possible outcome. Retrieval earns its place when:
- the library outgrows the context window, or costs too much to send with every review;
- each finding has to be traceable to a small, inspectable set of clauses: v1 records exactly which clauses each check saw, so a miss can be diagnosed as a retrieval or a judgement problem;
- false breaches cost more than misses: v1 made none, because it says NEEDS_REVIEW when it lacks a rule.

Version handling works in every variant. Each cites the superseded motor policy (v5.3) for incidents before 1 March 2026, and the current version (v6.0) after.

## Runs

- v0: `evals/results/20261018-150846-b7-v0-all/`
- v1: `evals/results/20261018-144843-b7-v1-all/`
- Full context: `evals/results/20261018-151549-b7-full-all/`
- v1 development rounds: `evals/results/20261018-123002-compliance-v1-dev/`, `20261018-123610-compliance-v1-dev-r2/`, `20261018-130717-compliance-v1-dev-r3/`
- v0 on the development claims: `evals/results/20261018-113135-compliance-v0-dev/`

Rebuild the comparison with `uv run python -m evals.compliance_compare <v0 run> <v1 run> <full run>`.
