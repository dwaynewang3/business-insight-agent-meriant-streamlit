# Policy-Compliance Kit for the Insurance Claims Agent

This kit adds policy-compliance analysis to the DuckDB claims agent. It has
three parts:
- a mock company policy knowledge base;
- an architecture and build plan for retrieval-augmented generation (RAG);
- an eval set that can tell you whether the result works.

The insurer, Meridian General Insurance, is fictional.

## What's inside

```
policies/   8 policy documents (7 active + 1 superseded), 252 clauses in total
  POL-CLM-001  Claims handling procedure
  POL-MTR-002  Motor coverage and exclusions v6.0 (from 1 Mar 2026)
  POL-MTR-002  v5.3 SUPERSEDED (incidents before 1 Mar 2026)
  POL-AUT-003  Delegated authority and approval limits
  POL-FRD-004  Fraud indicators and referral triggers
  POL-DOC-005  Documentation and evidence requirements
  POL-SLA-006  Service levels and turnaround
  POL-STL-007  Settlement and excess calculation
docs/
  POLICY_KIT_README.md      This file: what's inside and how to hand it to Claude Code
  RAG_PLAN.md               Architecture decisions, retrieval SQL, tools, compliance workflow,
                            evaluation, and the step-by-step build order (§10)
  CLAIM_FACTS_CONTRACT.md   The 80 claim fields the compliance tool reads, derived columns,
                            business-day SQL, and assumptions about your current schema
eval/
  golden_claims.csv         27 test claims (20 non-compliant, 4 traps, 3 clean controls)
  expected_verdicts.jsonl   Expected verdict, findings and clause citations per claim
  retrieval_questions.jsonl 35 retrieval questions (version, exact-code, cross-reference, out-of-scope)
  routing_questions.jsonl   16 questions with the tools the agent should (and shouldn't) call
data/
  nsw_public_holidays_2025_2026.csv   For business-day maths
```

## Start here (Claude Code on your Mac)

1. Unzip into the root of your agent repo. The zip contains only `policies/`,
   `docs/`, `eval/` and `data/`, so it merges into existing folders without
   overwriting your README or code.
2. Open Claude Code in the repo and paste:

> I've added a policy-compliance kit (policies/, docs/, eval/, data/). Read docs/POLICY_KIT_README.md, docs/RAG_PLAN.md and docs/CLAIM_FACTS_CONTRACT.md fully. Then:
> (1) check the assumptions in CLAIM_FACTS_CONTRACT.md §3 against this repo and tell me which are wrong;
> (2) append the "CLAUDE.md block" from docs/POLICY_KIT_README.md to our CLAUDE.md (create it if missing);
> (3) do build step 0 from RAG_PLAN.md §10.
> Stop after step 0 and show me its "done when" check.

3. After that, give Claude Code one build step at a time, using the prompts
   in `RAG_PLAN.md` §10. Move on only when the step's "done when" check passes.

### CLAUDE.md block
```markdown
## Policy-compliance RAG (in progress)
- Plan: docs/RAG_PLAN.md (build order in §10). Data contract: docs/CLAIM_FACTS_CONTRACT.md.
- policies/*.md is the source of truth for policy text. data/policy_kb.duckdb is derived:
  rebuild it with the ingest command and never edit it by hand.
- Claim-side facts (dates, day counts, totals) are computed in SQL. Policy thresholds, limits,
  points and excess amounts come only from retrieved clauses. Never hard-code them.
- Every LLM call is logged to logs/llm_calls.jsonl. Every eval miss is appended to
  eval/failures.jsonl with a diagnosis (retrieval_miss / wrong_version / judge_error /
  validator_reject / data_issue).
- Do one build step at a time. Don't start the next until the current step's "done when" passes.
- eval/expected_verdicts.jsonl is the answer key. Never feed it, or the seeded-issue labels,
  to the agent or the judge.
```

## What was verified before handing this over

- **Policies:** all 104 cross-references between clauses resolve to real
  clauses, including in the superseded version.
- **Golden labels:** each claim was built from one clean base record with one
  designed deviation. An independent rules engine then re-checked all 27
  claims. Its breaches match the expected findings exactly. That check caught
  two of my own labelling mistakes, which I corrected.
- **SQL:** the business-day macro, the as-of version filter, vector ranking,
  RRF fusion and cross-reference expansion were run on DuckDB 1.5.6. Business
  days matched an independent Python calendar on 27 claims × 5 measures.
- **Not executed:** the BM25 (FTS extension) query. It's written from the
  DuckDB 1.5 docs, but extension downloads were blocked where I built this.
  Build step 3 has a check that catches problems with it (searching `D-04`
  must return exactly 3 clauses).
- **Not seen:** your codebase. Schema and stack assumptions are listed in
  `CLAIM_FACTS_CONTRACT.md` §3.
