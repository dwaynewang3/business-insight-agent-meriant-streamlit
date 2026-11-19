# Baseline results and failure modes

> **History.** Everything on this page was measured on the earlier US version of the data, before the move to the Australian market on 2026-10-16, so it names US places (Texas, Chicago, the Southeast). The planted incidents are the same in the Australian data, in Australian settings. These runs weren't repeated on the Australian data; the final evaluation (DEV_PLAN Phase 6) measures the Australian agent. Run folders are in `evals/results/archive-us-data/`.

The first full measurement of the agent, on the development data, before any tuning: Claude Sonnet 5.5 at medium effort with every tool (agent version `0.1.0+92df8670f7`). The held-out test data hasn't been scored yet, so these numbers show where the agent stands during development, not how it will do on unseen data.

## Results

| Run | Result | Cost | Time |
| --- | --- | --- | --- |
| 84 "what" questions, once each (2026-10-14) | 84/84 correct (95% range 96–100%) | $2.35, $0.028 a question | median 13 s, 95th percentile 30 s |
| 16 "why" questions, 3 runs each (2026-10-14/15) | 12/16 passed in all 3 runs (95% range 50–90%); 41/48 runs passed | $3.00, $0.063 a question, plus $0.32 for the LLM grader | median 29 s, 95th percentile 55 s |

Results folders: `evals/results/archive-us-data/20261014-224733-full-what-dev-baseline/` and `evals/results/archive-us-data/20261014-232010-why-dev-baseline-x3/`.

**Against the success criteria** ([scoping](scoping.md) section 5):

| Area | Target | Development data |
| --- | --- | --- |
| "What" questions | ≥ 90% correct (on the test data) | 100% (84/84) |
| "Why" questions | ≥ 80% of planted causes found | 85% of runs (28/33) |
| Unsupported causes | ≤ 1 per answer on average | 0.04 (2 of 48 answers) |
| Questions with nothing to find | no invented cause | 15/15 runs |
| Cost | ≤ $0.50 per "why" question | $0.06 |
| Speed | median ≤ 30 s ("what"), ≤ 2 min ("why") | 13 s, 29 s |
| Trust | every number links to the SQL that produced it | **not met**: 91% of key numbers in "what" answers, 68% in "why" answers |

**Consistency.** The model accepts no temperature setting, so each "why" question ran 3 times. Three cases had mixed results; in each, the main cause was found every time, and a run failed for an extra unsupported cause or a missed detail.

**Caveats.** The 84 "what" questions come from 22 templates, so they're less varied than 84 real questions. The agent's instructions name six typical causes, each matching an incident in this data. Both make the development scores look better than they will on the test data.

## Experiment 1: the semantic layer on vs. off

The same 84 "what" questions, model, effort and instructions, with and without the semantic layer's metric tools. "Off" removes the agreed metric definitions and the SQL compiler (`get_metric`, `query_metric`, and catalog search, which also returns metric definitions). It keeps `run_sql`, the table docs and the glossary, which still defines each metric in words.

| | Semantic layer on | Off |
| --- | --- | --- |
| Correct | 84/84 (95% range 96–100%) | 83/84 (94–100%) |
| Cost per question | $0.028 | $0.022 |
| Median time | 13 s | 10 s |
| Tool calls per question | 4.4 | 3.1 |
| Key numbers traceable to their query | 91% | 96% |

- **Accuracy can't be told apart on this data**: one question differs. The "on" run used a metric tool in 82 of 84 questions, so the gap isn't from the tools going unused.
- **The one difference is a definition mistake the agreed metric prevents.** Without it, the agent summed policy-months over a quarter and then divided by 3 again, so its claim frequency was a third of the agreed figure, while its own interpretation described the right formula. The same mistake appeared in the first smoke run on 2026-10-09.
- **"Off" is cheaper, faster and more traceable here**, because the agent makes fewer calls and, with no agreed metric to compare against, reports one figure per question instead of the agreed metric plus a corrected one.
- **Compared with dbt Labs' 2026 benchmark** (90.0% without a semantic layer, 98.2% with it, on an insurance schema), the gap here is much smaller. Likely reasons: the "off" arm keeps a glossary that defines each metric in words, and the templated questions name their metric plainly.

**What it means:** most of the accuracy comes from documented definitions; the compiled metrics remove the remaining definition mistakes and make every answer use the official calculation, which business users see as the "Agreed metric" label. The semantic layer stays on, for about $0.006 a question.

## Failure modes

### 1. The steering pattern behind a repair-shop outlier is missed (5 of 6 runs)

The data has one Chicago repair shop (RS-041) with inflated costs, a growing share of the work since March 2026, and one adjuster (ADJ-024) handling most of its claims, which points to claim steering.

- **"Is any repair shop an outlier on cost?"** failed in all 3 runs. The agent finds RS-041 every time and proposes an invoice review, but it treats the question as a "what" question, tests no explanations, and never checks who handles the shop's claims.
- **"Why did Chicago repair costs rise?"** failed in 2 of 3 runs. The agent finds the shift of work to RS-041 and its higher costs, but says it's unclear why claims moved there. In one run it ruled out adjuster concentration.

A fraud analyst looking at an outlier would check what is concentrated around it: who handles the claims, when the pattern started, which channel they come from. **Candidate fix:** a general instruction to do that whenever an answer finds an outlier. The risk is tuning to this incident; the test data has a different fraud pattern (early claims in a new sales channel), which will show whether the instruction generalizes.

### 2. Numbers worked out by the agent rather than by a query

Each finding carries the SQL behind it, and the eval runner checks that each key number appears in that query's result. 9% of key numbers in "what" answers and 32% in "why" answers don't. The ones looked at by hand came from another query the agent ran or from its own arithmetic; their values haven't been checked, and none of them can be traced:

- **Comparisons done mentally:** the query returns detailed rows (by period, shop and cause), and the agent states before-and-after averages, shares and changes it worked out itself.
- **Two figures, one query:** the agent helpfully reports the agreed metric (which includes the duplicate payments) and a corrected figure, but a finding holds only one query, so one of the two points nowhere.

**Candidate fix:** ask the agent to compute comparisons, shares and changes in SQL, and to put each figure in a finding whose query returns it.

### 3. An occasional unsupported second cause (2 of 48 answers)

In one Texas run the agent added "a few large fire and liability claims" as a second driver, which its own figures didn't support. In one Southeast run it added a volume rise that isn't in the answer key. Both appeared in only one of three runs, which is the kind of failure repeat runs exist to catch. **Candidate fix:** none yet. The rate is well inside the target, and the improvement round will show whether failure modes 1 and 2's fixes change it.

### 4. Repeated tool calls (found 2026-11-17, in every saved run on Meridian's data)

Read after the project was published, the saved transcripts show the agent re-running a call it had already made, with the same input, turn after turn: 181 of 517 tool calls (35%), in 45 of 90 questions. One held-out "why" question ran the same call 18 times, and a held-out "what" question the same query 15 times; the demo's expired-licence answer ran `SELECT DATE '2026-02-10' < DATE '2026-03-01'` 11 times. On policy questions, part of the cause was an instruction: every number had to come from a query, so the agent restated a clause's number with queries such as `SELECT 1200 AS additional_excess_aud`. No answer was wrong because of it, but each repeat cost a model turn. **Fix, in three measured rounds** (decision 17 in [decisions.md](decisions.md)): refusing repeats made it worse (111 calls instead of 71 on 13 routing questions: the agent changed refused queries trivially to run them). The final design hands back the earlier result, tells the agent code re-checks every finding's query, refuses queries that read no table, and asks for the report after three repeats. On all 16 routing questions: 15 of 16 right against 14, at 89 calls and US$1.25 against 77 and US$1.10, one run each. The agent still asks for repeats about as often; they no longer run.

### Not agent failures

- A run stalled overnight when the Mac went to sleep in the middle of an API call. It recovered after waking, but its 1,238 s is left out of the times above. Long runs now keep the Mac awake.
- The LLM grader's batch took longer than the runner's 20-minute wait. Its results were collected later by batch ID at no extra cost, and the summary was rebuilt.

## Improvement round 1: two instructions

Both main failure modes were addressed with general instructions in the agent's system prompt rather than with sub-agents, since the baseline showed no need for them:

- **Outliers:** when an answer finds an outlier (a repair shop, adjuster, region or sales channel far from its peers), look at what's concentrated around it (who handles its claims, when the pattern started, where its work comes from), even if the question only asks whether there is one, and report it as evidence for review rather than a verdict.
- **Traceable numbers:** every key number must appear in its finding's query result; work out comparisons, changes, shares and rates in SQL; two numbers from two queries go in two findings.

Measured on the same development cases (agent `0.1.0+8f6318acbf`, 2026-10-15):

| | Baseline | After |
| --- | --- | --- |
| "What" questions correct | 84/84 | 84/84 |
| "What" key numbers traceable | 91% | 99% (307/311) |
| "Why" questions passed | 41/48 runs (85%) | 16/16, one run each (95% range 81–100%) |
| Repair-shop steering found (two questions) | 1 of 6 runs | 2 of 2 |
| "Why" key numbers traceable | 68% | 94% (103/109) |
| Unsupported causes | 2 of 48 answers | 0 of 16 |
| Cost per question, "what" / "why" | $0.028 / $0.063 | $0.032 / $0.069 |
| Median time, "what" / "why" | 13 s / 29 s | 16 s / 30 s |

The repair-shop answer now names the adjuster behind most of RS-041's claims (37 of 79, averaging $6,820 against $4,853 for the rest), compares the same adjuster's claims at other shops, and proposes a targeted review. The LLM grader passed it but noted it still misses the shop's growing share of Chicago work since March.

**Caveats.** The "why" questions ran once each after the change, so this doesn't yet show consistency; the two unsupported causes in the baseline each appeared in only one of three runs. The outlier instruction is general, but it was written after seeing this data's fraud pattern; the test data's different fraud pattern (early claims in a new sales channel) will show whether it carries over.

## What the LLM grader adds

The code checks alone pass 30 of 33 "why" runs that have a cause to find. The LLM grader failed 4 more: two Chicago runs that named the shop but missed the steering, and the two runs with an unsupported second cause. Its self-checks passed in the same batch (the answer key passed and an empty answer failed).

**Checked against hand labels:** a person labeled all 56 "why" answers from the development runs, and the LLM grader agreed on all 56 (95% range 94–100%), including all 7 that the person failed (65–100%). The grader's verdict was visible in the labeling sheet, which can make agreement look higher than labeling blind would.

## Every run on the US data

The runs behind this page, with the smaller ones made while the agent was being built. Costs are API costs in US dollars.

| Run (US data; 2026-10-09 unless noted) | Passed | API cost | Median time |
| --- | --- | --- | --- |
| All 84 "what" questions (2026-10-14) | 84/84 (95% range 96–100%) | $2.35 | 13 s |
| Experiment 1: the 84 "what" questions without the semantic layer (2026-10-15) | 83/84 (94–100%) | $1.82 | 10 s |
| All 16 "why" questions, 3 runs each (2026-10-15) | 12/16 passed in every run (50–90%); 41/48 runs | $3.00 | 29 s |
| After improvement round 1: all 84 "what" questions (2026-10-15) | 84/84 (96–100%); 99% of key numbers traceable | $2.67 | 16 s |
| After improvement round 1: all 16 "why" questions, once each (2026-10-15) | 16/16 (81–100%); 94% of key numbers traceable | $1.11 | 30 s |
| 8 "what" questions, SQL only (no agreed metrics) | 7/8 (95% range 53–98%) | $0.20 | 15 s |
| Same 8, all tools | 8/8 (68–100%) | $0.23 | 15 s |
| 3 "why" incidents | 3/3 right cause (LLM grader) | $0.21 | 44 s |
| 5 "why" questions with nothing to find | 5/5, no cause invented (LLM grader) | $0.25 | 23 s |
| 11 safety cases | 11/11 (74–100%) | $0.17 | 4 s |
| 5 follow-ups (a question, then "now show the same for home" and the like) | 5/5 (57–100%) | $0.27 | 26 s per pair |

In the full 84-question run, **306 of 336 key numbers (91%) are confirmed by the SQL attached to them** (125 of 145 across the smaller runs). The rest are right numbers attached to the wrong query. Most come from the agent reporting both the agreed metric, which includes the duplicate payments, and a corrected figure, while each finding carries only one query; others are shares and changes it worked out itself. Every number should be traceable to the query that produced it. After the first improvement round (two instructions in the agent's prompt, above), 99% of key numbers in "what" answers and 94% in "why" answers trace to their query.

The 84 "what" questions come from 22 templates, so they're less varied than 84 real questions. The held-out test data is the real check.

These are small samples, so the ranges are wide. The one failure, in the first run: for claim frequency, the agent divided by the number of months a second time, so its answer was a third of the agreed definition. With the agreed metric available, it used the definition and got it right.
