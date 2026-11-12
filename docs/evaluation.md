# Evaluation

How the agent is tested: the cases, the graders and the commands. The results are in the [README](../README.md#final-results-held-out-test-data-2026-10-19), [results.md](results.md) (the earlier runs) and [compliance_results.md](compliance_results.md).

## Cases

The agent is tested on questions with known answers, in [evals/cases/](../evals/cases/). Run `make cases` to read them all.

- **84 "what" questions**, such as "What was the motor claim frequency by state in Q2 2026?" They're generated from 22 templates. Each one has reference SQL written by hand, and the agent's answer must match its result. Where a question can fairly be read two ways, such as "the last 12 months" while the latest month is incomplete, every fair reading is accepted.
- **16 "why" questions.** Eleven have a known cause in the data, such as the East Coast Low or the repair shop. Five have nothing to find: a normal seasonal pattern, ordinary noise, or a question that assumes something that didn't happen. The agent passes those only if it doesn't invent a cause.
- **14 safety cases**: attempts to change data or a recorded compliance verdict, read files or see personal data without access, instructions hidden in a claim note and in a claim file's handler notes, a user pressing the agent to confirm a claim complies, and a question too vague to answer.
- **5 follow-ups**: a question, then one that depends on it, such as "and for the first half of 2026?"
- **Policies and compliance:** 27 claim files with expected verdicts and findings (18 for development, 9 held out), retrieval questions with the clauses each should find, and 16 routing questions that check the agent picks data, policy or compliance tools.
- **Held-out test set** ([evals/cases/test/](../evals/cases/test/)): 22 "what" and 7 "why" questions on separate test data, written before any run.

Tests run every reference query against the warehouse and check it against the semantic layer, so a wrong reference answer can't go unnoticed.

## Running the evals

These call Claude, so they need `ANTHROPIC_API_KEY` in `.env`. The costs are estimates from the last runs on the current data: about US$0.06 a "what" question and US$0.11 a "why" question.

```bash
make eval SUBSET=smoke                                       # 8 "what" questions, about $0.50
make eval SUBSET=all                                         # all 84 "what" questions, about $5
make eval KIND=why SUBSET=all REPEATS=3                      # every "why" case 3 times, about $5.50
uv run python -m evals.run_evals --kind why --subset why_smoke   # 3 "why" incidents, about $0.35
uv run python -m evals.run_evals --kind safety                   # 14 safety cases, about $0.60
uv run python -m evals.run_evals --suite test --kind why        # the held-out "why" set (make test-data first)
uv run python -m evals.retrieval                                 # policy search recall, free
uv run python -m evals.routing_eval --max-cost 1.50              # 16 routing questions, about $1.10
uv run python -m evals.compliance_eval --variant full --split dev --batch --max-cost 1.00
```

Every runner checks its grader before the first paid call, stops at `--max-cost`, and respects the spend ledger's limit.

## Graders

The "what" grader never trusts numbers in the answer text. It re-runs the SQL the agent says produced the answer, and compares that result with the reference query's result. Column names and order don't matter, and state names or codes, percentages or fractions are all accepted. Before any paid call, the runner checks that the grader passes each case's reference answers and fails an empty one.

The "why" code checks require the answer key's evidence to be named, such as the storm's ID or the reload batch. Whether the explanation is right, and free of invented causes, is judged by an LLM grader (Claude Opus 5.5 through the Batch API) that runs after each "why" run; its verdicts go into the run's summary, but never overrule a failed code check. Checked against 56 answers labeled by hand, it agreed on all 56, including all 7 failures. The safety grader reads every tool result in the conversation, not just the final answer, so a name that reached the model counts as a leak even if the answer leaves it out.

Every answer's key numbers are also checked against the result of the SQL attached to them, because every number should be traceable to the query that produced it. A number matches if it's a fair rounding of a value in that result, or of a column's total or average. This is reported as its own count, apart from pass or fail.

## Saved runs

Each run saves every case's report, grade, tool calls, cost and full conversation in `evals/results/`, with a summary that gives the pass count and its 95% range. A stopped run can be finished with `--resume <folder>`, and `--summarize <folder>` rebuilds a summary without running anything. The UI's **Saved runs** mode shows any of them.
