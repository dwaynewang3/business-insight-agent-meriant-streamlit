# Decisions

The choices that shaped the Business Insights Agent. Each one gives the alternative that was considered, the reason, the evidence, and what the choice costs. The [build log](dev/DEV_TRACKER.md) has every decision with its date, including the ones that were reversed.

## 1. An investigation agent on generated data with planted incidents

- **Instead of:** a customer-support agent, a research agent over financial filings, or document triage for claims.
- **Why:** a "why" answer can only be graded if the true cause is known. The generator plants each incident and writes an answer key, so every answer can be checked.
- **Evidence:** six planted incidents and two "nothing unusual" controls on the development data, and a second data set with new incidents that was scored once.
- **The cost:** generated data is cleaner than real claims data. With a customer, the eval set would come from their analysts' own questions ([rollout plan](rollout_plan.md)).

## 2. LangGraph for state and approval, with the Anthropic SDK called directly

- **Instead of:** a hand-written loop, or LangGraph with a LangChain model wrapper.
- **Why:** LangGraph supplies the conversation state, the checkpoints and the pause for a person's approval. Calling the SDK directly inside each step keeps every Claude API feature: structured outputs, prompt caching, effort and server-side fallback.
- **Evidence:** a paused approval survives closing and reopening the session, and about 90% of input tokens come from the prompt cache.
- **The cost:** two libraries to keep current, and the message list has to stay append-only by hand.

## 3. One loop and no sub-agents; the auditor is code

- **Instead of:** separate classify, plan, investigate and report steps, or Analyst and Auditor sub-agents.
- **Why:** steps and agents were to be added only where the evals showed a need, and the baseline's failures were about what the agent checks, not how many agents check it.
- **Evidence:** two general instructions fixed both failure modes. The repair-shop steering pattern was found in 2 of 2 runs (1 of 6 before), and traceable key numbers in "why" answers rose from 68% to 94%. The auditor became a `check_report` step that re-runs each finding's SQL and costs a model call only when a number fails. It repaired one live answer, and 41 of 41 key numbers were then confirmed.
- **The cost:** one long conversation per question. A session stops at 10 questions to keep it fast and cheap.

## 4. Guardrails in code: the SQL guard

- **Instead of:** a read-only connection plus a prompt rule, or a SQL parser library to check statements.
- **Why:** testing showed that a read-only `SELECT` can still read local files through `read_text`, including `.env` and the answer key. The guard turns external access off, locks the settings, and allows one `SELECT`, checked with DuckDB's own parser so the check and the database can't disagree.
- **Evidence:** 45 adversarial tests. The parser check caught that `PIVOT` runs a hidden `CREATE`.
- **The cost:** DuckDB's full-text search extension can't be loaded, so catalog search ranks keywords in Python.

## 5. Personal data kept out of the warehouse copy, not filtered out of queries

- **Instead of:** checking each query for personal-data columns.
- **Why:** data that isn't in the file can't leak. Every role except the fraud team lead connects to a copy without names or emails, and the app sets the role when it starts the server, so neither the model nor the user can change it.
- **Evidence:** 14 of 14 safety cases, including a user claiming to have moved to the fraud team. The safety grader reads every tool result, so a name that reached the model counts as a leak even if the answer leaves it out.
- **The cost:** a second copy of the warehouse to build, and no finer rule such as totals-only access.

## 6. The model has no tool that writes; approval waits on its own thread

- **Instead of:** giving the model `create_ticket` behind a confirmation, or pausing the conversation until the user decides.
- **Why:** with no write tool, a prompt injection has nothing to call. LangGraph's interrupt pauses a whole thread, so each question's proposed actions pause on a thread of their own and the conversation carries on.
- **Evidence:** tests show only approved actions reach the actions server, with who approved them; undecided ones are dropped when the session ends. An approved action can also be opened as a GitHub issue, behind the same step.
- **The cost:** more state to track, and a last-chance screen when a conversation ends.

## 7. The semantic layer stays on, though it didn't measurably improve accuracy

- **Instead of:** switching it off: 83 of 84 "what" questions were right without it, against 84 of 84 with it, and answers were cheaper ($0.022 against $0.028) and faster.
- **Why:** the one miss was a definition mistake, claim frequency divided by the months twice. Agreed metrics prevent that kind of mistake and make every answer use the official calculation, for about $0.006 a question.
- **Evidence:** [Experiment 1](results.md).
- **The cost:** more tool calls per question.

## 8. The "Agreed metric" label follows the numbers, not the SQL text

- **Instead of:** labelling an answer "Agreed metric" only when its SQL is exactly what the semantic layer produced.
- **Why:** that rule never fired. The agent gets its number from the agreed metric, then writes a shorter query of its own as the answer's SQL, so in every saved run the label said "Custom query". Code now runs both queries, and the label is "Agreed metric" when every number in the answer's result is one the agreed metric returned for the same row, rounding aside.
- **Evidence:** on the held-out "what" questions, 11 of 22 answers now carry the label. The others add a number of their own, such as a claim count or a figure with duplicate payments removed, or didn't use an agreed metric.
- **The cost:** the rule is strict, so some answers whose main number is the agreed one are still labelled "Custom query". A wrong "Custom" costs a look at the SQL; a wrong "Agreed" would cost trust.

## 9. Grade the SQL's result, score the held-out data once, report counts with ranges

- **Instead of:** about 30 "what" cases graded on numbers found in the answer's text, reported as a percentage.
- **Why:** numbers in prose can be right by accident or wrong by rounding. The grader re-runs the answer's SQL and compares the result with hand-written reference SQL. Small samples can't show small differences, so every result is a count with a 95% range.
- **Evidence:** the grader must pass every reference answer and fail an empty one before any paid run. Held-out data: 22 of 22 "what" (85–100%) and 7 of 7 "why" (65–100%).
- **The cost:** wide ranges, stated as they are. The 84 development questions come from 22 templates.

## 10. A different model grades "why" answers, and people check the grader

- **Instead of:** code checks alone, or the agent's own model as the judge.
- **Why:** code can check that the storm's ID is named, but not whether the explanation is right or invents a second cause.
- **Evidence:** Claude Opus 5.5 agreed with hand labels on 56 of 56 answers, including all 7 failures. Each batch also grades the answer key (must pass) and an empty answer (must fail).
- **The cost:** the grader's verdict was visible while labeling, which can raise agreement. Its verdict never overrules a failed code check.

## 11. The prompt names six typical causes, and the test data has one outside them

- **Instead of:** removing the list, or keeping it and saying nothing.
- **Why:** analysts work from such checklists, but each of the six matches an incident in the development data, so development scores may flatter the agent.
- **Evidence:** the held-out data adds early-claim fraud, which isn't on the list, and the agent found it.
- **The cost:** that's a single case. The README lists it as a limitation.

## 12. Compliance review reads the whole policy library, not retrieved clauses

- **Instead of:** naive RAG (14 of 27 verdicts right) or checklist RAG with a judge per check (25 of 27, $0.064 a claim).
- **Why:** the library is about 25,000 tokens, so it fits in one cached prompt. Full context scored 27 of 27 at $0.031 a claim.
- **Evidence:** one run per design on all 27 claim files, 9 of them held out ([compliance results](compliance_results.md)).
- **The cost:** three "false" breaches, two of them debatable readings of the answer key. It stops working when the library outgrows the prompt. Retrieval is kept for policy questions (recall@8 of 1.00 with hybrid search) and would take over the review at that scale.

## 13. Citations are written in the answer and checked in code

- **Instead of:** a `citations` list in the structured report.
- **Why:** with that field, the API rejected every request: all strict schemas in a request compile into one grammar, and it grew too large. Citations are now written inline, and code reads them from the text and checks each against the clauses the tools returned.
- **Evidence:** the check covers exactly what the user sees. The warehouse tools stay strict, where a malformed SQL call does harm; the policy tools are sent without `strict`.
- **The cost:** a parser for citation formats, which had to learn clause lists such as "§2.1, §2.2 and §4.3".

## 14. A name that means two things is fixed in the data, not in the prompt

- **Instead of:** a prompt rule saying "New South Wales means the state".
- **Why:** after the move to Australia, "New South Wales" was both a state and a region, and the agent read it as the region in 2 of the first 4 questions of a sanity run. The regions were renamed NSW & ACT, VIC & TAS and QLD & NT, which is how Australian insurers usually report.
- **Evidence:** the rerun passed 8 of 8 "what" and 3 of 3 "why" questions. Only names changed, so every incident and reference answer still holds.
- **The cost:** none found. A sanity run is what caught it.

## 15. Claude Sonnet 5.5 at medium effort, chosen on capability and budget

- **Instead of:** running the agent's questions on Opus 5.5, a Haiku model and other effort levels, and picking from the results.
- **Why:** the work is multi-step tool use, which Sonnet 5.5 is strong at, for half of Opus 5.5's price. The whole project had A$50 of API spend, down from US$200 part-way through, and a model comparison would have used the budget the compliance comparison and the held-out scoring needed.
- **Evidence:** at medium effort the agent met its accuracy, cost and speed targets on the held-out data, so the evals showed no failure for a larger model to fix. The one cheaper setting that was measured, the compliance judge at low effort, gave the same verdicts but invented a citation.
- **The cost:** nothing shows whether a cheaper model would do as well. The budget also left one run per compliance design and one run per held-out question, so the ranges are wide. The eval runner takes `--model` and `--effort`, so the comparison is one command per arm.
