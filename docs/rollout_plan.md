# Rollout plan

How the Business Insights Agent would go into production at a real insurer like the fictional one in this demo. It moves in three stages, and each stage widens what the agent does only after it has met measured targets on the customer's own questions.

## Before the first stage

Moving from the demo to a customer's data is mostly connection and governance work:

| Demo | At a customer |
| --- | --- |
| DuckDB file with generated data | Read-only service account on the customer's warehouse (Snowflake, BigQuery or Databricks), limited to the claims schemas |
| Restricted copy without personal data | A role-based view or masking policy in the warehouse, mapped from the customer's single sign-on groups |
| Metric definitions in YAML | The customer's existing semantic layer (for example dbt MetricFlow), or the YAML reviewed and signed off by finance and actuarial |
| Generated eval cases | 50–100 real questions from claims leaders and analysts, with answers checked by an analyst |
| Tickets and alerts recorded locally, or opened as GitHub issues | The customer's Jira or ServiceNow, through the same approval step |
| Local traces and Langfuse Cloud | Tracing inside the customer's environment, with the retention and data-residency rules their security team sets |

**Exit criteria:** the security review is signed off, the eval set built from real questions exists, and a baseline is measured on it.

## Stage 1: Shadow mode (about 4 weeks)

The agent answers real questions in the background, and nobody sees its answers except the project team.

- **Who:** 3–5 analysts keep working as usual. Their questions are replayed to the agent, and their answers become the reference.
- **What we measure:** agreement with the analysts on "what" questions, whether "why" answers find the cause the analyst found, cost and time per question, and every safety check.
- **Why this stage:** it finds failure modes on real data at no risk. Examples are definitions the semantic layer is missing, unusual table structures and questions the agent misreads.

**Move on when** "what" answers agree with analysts at least 90% of the time, "why" answers find the analyst's main cause at least 80% of the time, safety is 100%, and cost is within budget.

## Stage 2: Assisting analysts (about 8 weeks)

Analysts use the agent as a first draft, and every answer is reviewed before it reaches a business user.

- **Who:** the analyst team, and then claims leaders for questions an analyst signs off.
- **What changes:** the UI shows how the question was read, the Agreed metric or Custom query labels, the SQL and the data behind every number, so a reviewer can check an answer in minutes rather than redo it. Proposed tickets and alerts go to the real ticketing system after approval.
- **What we measure:** how often analysts accept answers without changes, time saved per question, the reasons for each correction (to feed back into the semantic layer and the prompts), and user feedback on each answer.

**Move on when** analysts accept at least 85% of answers to a given type of question without changes for 4 weeks, and no answer reached a business user with a wrong number.

## Stage 3: On its own for low-risk questions

Business users ask questions directly, for question types that have earned it.

- **In scope:** "what" questions answered entirely from agreed metrics, such as frequency, loss ratio and claim counts, with an Agreed metric label on the number.
- **Still reviewed by an analyst:** "why" questions, anything answered with custom SQL, anything that proposes an action, and anything touching personal data.
- **Monitoring:** a sample of answers is re-graded every week. Alerts fire on drops in accuracy, cost spikes, refusals and fallbacks to another model, and the eval suite runs again before every prompt, model or semantic-layer change.
- **Rollback:** each question type can be switched back to analyst review on its own, without a release.

## Risks

| Risk | Mitigation |
| --- | --- |
| A confident wrong number reaches a decision-maker | The Agreed metric label, visible SQL and data for every number, analyst review until a question type has a track record |
| Metric definitions differ between teams | One semantic layer signed off by finance and actuarial; the agent uses agreed metrics before writing its own SQL |
| Personal data exposure | Access enforced in the warehouse by role, not by the agent; safety cases rerun before every change |
| Costs grow with usage | Per-question caps, prompt caching, effort tuned by evals, and a monthly budget alert |
| Model or API changes | Pinned model, the eval suite rerun on every upgrade, and fallbacks recorded per answer |
| Users stop checking answers | Spot checks continue in stage 3, and answers to the riskiest question types always get a review |
