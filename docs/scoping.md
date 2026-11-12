# Scoping: Business Insights Agent for Meridian General Insurance

> **Fictional engagement.** Meridian General Insurance, its people and its data are invented. This document scopes the work the way a real customer engagement would be scoped.
> Status: v1 scope frozen on 2026-10-04 for an unnamed US insurer, and revised on 2026-10-16: the customer is now Meridian General Insurance in Australia, and policy compliance is in scope ([design](meridian_design.md)). Access rules simplified on 2026-10-08, so every rule is enforced in code. · Plan: [DEV_PLAN.md](dev/DEV_PLAN.md)

## 1. Customer brief

**Who:** Meridian General Insurance, a mid-size Australian motor and home insurer headquartered in Sydney. It operates in all eight states and territories, grouped into four regions:
- NSW & ACT: New South Wales and the ACT
- VIC & TAS: Victoria and Tasmania
- QLD & NT: Queensland and the Northern Territory
- West & South: WA and SA

It had about 46,000 policies at the start of 2025. A home insurance partnership with a bank launched in January 2026 and grew the book to about 71,000 policies in force by September 2026.

**Situation:**
- **Claims data:** lands in a central warehouse every night. Dashboards show leaders *what* changed, such as a jump in claim costs, but not *why*. "Why" questions go to a small analytics team that has a backlog.
- **Claims handling rules:** live in a policy library of eight documents covering claims handling, motor cover, delegated authority, fraud, documentation, service levels and settlement. The library changes over time; the motor policy changed on 1 March 2026. Checking whether a claim was handled by the rules is a manual file review.

**Pain points:**
- Answers to "why" questions take days, so decisions are made late or on gut feel.
- Teams define metrics differently. One team calculates average claim cost from paid amounts, another from paid amounts plus reserves, so the same question gets different numbers.
- Data problems, such as a payment file loaded twice, are sometimes found only after they've skewed a report.
- File reviews against the policy library are slow, inconsistent, and easy to get wrong when a rule changed between the incident and the decision.

**What the customer asked for:** "Let our claims leaders get trustworthy answers to *what* and *why* questions in minutes, and check claims against our policies, with evidence they can verify, without giving anyone access they shouldn't have."

## 2. Users

| Role | What they need | Data access |
| --- | --- | --- |
| Head of Claims | Fast explanations of big movements in cost and loss ratio | Everything except personal data |
| Claims operations manager | Why claims are slow, where staff are stretched, and whether claims follow policy | Everything except personal data |
| Actuarial analyst | Reliable numbers that follow the agreed definitions | Everything except personal data |
| Fraud team lead | Outliers worth investigating: repair shops, adjusters, individual claims | Everything, including personal data |

Personal data means policyholder names and email addresses.

## 3. Agreed metric definitions

These become the agent's semantic layer, so every user gets the same number for the same question. Amounts are in Australian dollars (AUD).

| Metric | Definition |
| --- | --- |
| Claim count | Number of claims, counted by loss date |
| Claim frequency | Claims per 1,000 policies in force, per month |
| Average claim cost | Incurred amount (paid plus open reserves) ÷ claim count |
| Loss ratio | Incurred losses ÷ earned premium |
| Cycle time | Days from report date to close date, for closed claims only |
| Paid amount | Sum of claim payments, counted by payment date |

## 4. Top questions

These are the questions users ask most. They become the first test cases, and each "why" question has a known answer in the generated data.

| # | Question | Asked by | Type |
| --- | --- | --- | --- |
| 1 | What was the motor claim frequency by state in Q2 2026? | Actuarial analyst | What |
| 2 | What is our loss ratio by product over the last 12 months? | Head of Claims | What |
| 3 | How many open claims does each West & South adjuster have? | Claims operations manager | What |
| 4 | Why did the average claim cost in New South Wales jump in July 2026? | Head of Claims | Why |
| 5 | Is any repair shop an outlier on cost? | Fraud team lead | Why |
| 6 | Why did paid claims spike in early March 2026? | Head of Claims | Why (data quality) |
| 7 | Why are West & South claims taking longer to close since May 2026? | Claims operations manager | Why |
| 8 | Average claim cost rose in Q2 2026. Is that a real increase? | Actuarial analyst | Why |
| 9 | Why do the September 2026 numbers look so low? | Head of Claims | Why (data quality) |
| 10 | Were home storm claims in Queensland unusual in early 2026? | Claims operations manager | Why (control: nothing unusual) |
| 11 | What's our rule on drivers with an expired licence? Did it change this year? | Claims operations manager | Policy |
| 12 | Does claim GC-010 comply with policy? | Claims operations manager | Compliance |
| 13 | Which claims were settled above the approver's authority? | Head of Claims | Policy and data |

## 5. Success criteria

| Area | Target |
| --- | --- |
| "What" questions | ≥ 90% correct on held-out test data |
| "Why" investigations | Finds ≥ 80% of the real causes, with ≤ 1 unsupported cause per answer on average |
| Data quality | Flags both data problems: the duplicate payments and the incomplete latest month |
| Policy answers | Every policy statement cites a clause in force on the relevant date |
| Compliance reviews | On the 27 claim files: ≥ 23/27 overall verdicts right, ≥ 20/22 required findings detected, all 7 compliant files judged compliant, no invented citations |
| Safety | 100%: never changes data, never reads files outside the warehouse, never shows personal data to roles that can't see it, and ignores instructions hidden in the data |
| Speed and cost | Median ≤ 30 s for "what" and ≤ 2 min for "why"; ≤ US$0.50 of API cost per "why" question |
| Trust | Every number in an answer links to the SQL that produced it |

## 6. Constraints

- **Budget:** at most A$50 of API spend for the whole project, about US$34.60 (the Claude API bills in US dollars); it was US$200 until 2026-10-18. The agent runs on Claude Sonnet 5.5.
- **Data:** no real data. A seeded script generates the warehouse and plants known incidents in it. The policy library and the 27 claim files are fictional too.
- **Access:** read-only. The agent never changes data, and actions such as tickets need a human's approval.
- **Privacy:** personal data (names and emails) is visible only to the fraud team role.
- **Delivery:** the demo runs locally. The code will be on GitHub, and a detailed README will be written before it's public.
- **Timeline:** no fixed deadline.

## 7. Scope for v1

**In scope**
- Answers to "what" and "why" questions over claims, payments, policies, adjusters, repair shops and weather data
- Evidence for every finding: the SQL, the key numbers and charts
- Data-quality checks before any conclusion is drawn
- Role-based access to personal data
- Proposed tickets and alerts that run only after a human approves them
- Policy answers with clause citations, using the version in force on the relevant date (motor claims)
- Compliance review of a claim file against the policy library, and questions about batch review results
- An evaluation suite with known answers

**Out of scope**
- Connecting to real systems or real data
- Changing any data
- Home insurance policies (the policy library covers claims handling and motor cover)
- Scheduled monitoring and automatic alerts
- Slack, Jira or email integrations
- A hosted online version

## 8. Assumptions

In a real engagement, each of these would be confirmed with the customer before building.

| Area | Assumption for the demo | What we'd confirm with a real customer |
| --- | --- | --- |
| Metric definitions | The definitions in section 3 are official | Which team owns each definition |
| Policy library | The eight documents are complete and current, and each change has an effective date | Who owns each policy, how changes are published, and which version applies to claims in flight |
| Personal data | Only the fraud team sees names and emails | Legal and compliance sign-off on the access rules, and whether some roles should see only totals and averages |
| Data freshness | The warehouse updates nightly, and the latest month is incomplete | The load schedule, and how late claims usually arrive |
| Actions | A claims manager approves tickets and alerts | Who owns data-quality tickets and file-review referrals |
| Usage | A few dozen questions a day | Expected volume and peak times, for cost planning |
| Test cases | Written from the answer keys the data generator and the policy kit provide, so every correct answer is known | Which real questions and past file reviews to test on, and who signs off on each correct answer. In shadow mode, the analysts' scores of the agent's answers become new test cases. |

## 9. Rollout

This is how a real deployment would go:

1. **Shadow mode:** the agent answers questions alongside the analysts, who compare and score its answers.
2. **Assist:** analysts start from the agent's draft findings and approve them before sharing.
3. **Self-serve for low-risk questions:** leaders ask "what" questions directly. "Why" answers and compliance verdicts keep an analyst review until their accuracy is proven.

The full rollout plan is in [rollout_plan.md](rollout_plan.md).

## 10. Sign-off

The v1 scope was frozen on 2026-10-04 and revised on 2026-10-16 (Australian market and policy compliance). After the revision, new ideas go to the plan's parking lot unless they fix a problem.
