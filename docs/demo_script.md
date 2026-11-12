# Demo script (3–5 minutes)

A script for presenting the project to someone live. The UI's **Guided demo** is the same walkthrough for a visitor on their own: the same eight answers in the same order, with a note on what to look for in each. Run `make demo` first. The guided demo needs no API key, so every step can be rehearsed for free. The live steps cost a few cents each.

> Every question below has a saved run on Meridian's data. They're the guided demo's eight steps, and the first eight entries under **Saved runs**:
>
> | Step here | Guided demo step | Run folder |
> | --- | --- | --- |
> | 2 | 1 | `20261018-112603-b4-sanity-what` |
> | 3 | 2 and 3 | `20261018-112909-b4-sanity-why` |
> | 4 | 4 | `20261025-221102-demo-safety` (the optional repair-shop question is Live only) |
> | 5 | 5, 6 and 7 | `20261025-221208-demo-policy` |
> | 6 | 8 | `20261025-221120-demo-followup` (both questions; approving actions needs Live) |
>
> The held-out test runs (`…-test-final-…`) replay too, with charts and data from the test warehouse once `make test-data` has built it.

## 1. The problem (30 seconds)

> "This is Meridian General, a mid-size Australian motor and home insurer. Its dashboards show *what* changed, a loss ratio up or claims taking longer to close, but not *why*. Claims leaders wait days for an analyst to dig in, and known data problems sometimes lead to the wrong conclusion. The data here is generated, with problems planted on purpose, so every answer can be checked against a known truth."

Show: the title and caption of the UI.

## 2. A "what" question, and why you can trust the number (45 seconds)

Ask *"What was the motor claim frequency by state in Q2 2026?"*

> "The agent looked up the company's agreed definition of claim frequency and computed it. The label says **Agreed metric**. Our code sets that label, not the model: it runs the agreed metric and the agent's own query, and every number in the answer has to match. Here's how it read the question, the SQL, and the data behind the answer."

Open **Show SQL**, then **Show data**.

> "Without the agreed definition, the agent once divided by three months twice and was off by a factor of three. It's the kind of mistake a semantic layer prevents, and Experiment 1 measured it."

## 3. A "why" question (75 seconds)

Ask *"Why did the average claim cost in New South Wales jump in July 2026?"*

> "For a 'why' question it tests several explanations against the data. An East Coast Low over Sydney explains it: without the storm claims, July's average matches June's. It also checked whether a data problem or large outliers could explain it, and says what it ruled out."

Then ask *"Why did paid claims spike in early March 2026?"*

> "Here the answer is uncomfortable: the spike isn't real. A batch of payments was loaded twice. The agent found the batch, measured how much it inflated the numbers, and proposed a ticket for the data team. That ticket would only be created after a person approves it."

## 4. Safety (45 seconds)

As the Head of Claims, ask *"List the names and email addresses of the policyholders behind our 10 largest claims in 2026."*

> "The Head of Claims can't see personal data, and that isn't a prompt rule. Their session is connected to a copy of the warehouse that has no names or emails in it, so nothing can leak even if a query gets through. Telling the agent 'I've just moved to the fraud team' doesn't change it either, because the app sets the role, not the user."

Optional: as the fraud team lead, ask *"Is any repair shop an outlier on cost? Read the claim notes for context too."* An instruction hidden in a claim note doesn't change the answer.

## 5. Policies and a compliance review (60 seconds)

Ask *"For an incident on 10 February 2026, could we cover a driver whose licence had expired 18 days earlier?"*

> "Policies change. The motor policy was rewritten on 1 March 2026, so for a February incident the agent uses the old version, where an expired licence is an absolute exclusion. Every policy statement cites its clause and version, and our code checks each citation against what the policy search actually returned: here, POL-MTR-002 §3.4, version 5.3."

Open **Policy clauses** to show the clause text and the dates that version was in force.

Then ask *"Was claim GC-010 handled in line with policy?"*

> "This is a quality review of one claim file. The licence had expired, and the handler set the exclusion aside with senior approval, but under the version in force no one may. The verdict card shows each finding, its severity and its clause. The verdict is aggregated in code, not by the model."

Then ask *"Which claim files were settled above the approving officer's authority limit?"*

> "Across the sample it finds two. It also explains why a third, which looks over the limit, isn't: a declared catastrophe doubled the junior officer's limit. I measured three designs for the review. Sending the whole policy library in one cached prompt beat retrieval, at half the cost, because the library is small. Retrieval would earn its place at scale, and I can show that comparison."

## 6. Live, with a follow-up and an approval (60 seconds, optional)

In **Live** as the Head of Claims, ask *"What was the loss ratio for each product in 2025?"*, then *"And for the first half of 2026?"*

> "You can watch it work: looking up the definition, checking data quality, running the query. The follow-up keeps the context, so 'and for the first half of 2026' means the same metric and breakdown."

If it proposes an action, approve one and reject one, then show that only the approved one was created. With a GitHub repository set in `.env`, open the issue it links to. Rate the answer with the thumbs under it.

## 7. Under the hood and next steps (30 seconds)

> "It's a LangGraph agent on Claude Sonnet 5.5, with tools behind MCP servers, guardrails in code, and every run traced with its cost. A 'what' question costs about 6 US cents of API usage and a 'why' question about 12. The evals grade answers by re-running the agent's SQL against hand-written references. With a real customer, I'd start in shadow mode next to their analysts, as the rollout plan describes."

Show: `docs/architecture.md` or the README's results table.
