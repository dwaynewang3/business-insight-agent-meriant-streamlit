"""The guided demo: eight saved answers in order, with what to look for in each.

A visitor steps through real answers the agent gave, with a note on what each one shows and
what to open. Nothing here calls a model, so it works without an API key and costs nothing.
Each step names its saved run (folder/case under evals/results/), and tests check that the
facts the notes quote are in that run, so the tour can't drift from what the screen shows.
"""

from dataclasses import dataclass

REPO_URL = "https://github.com/dwaynewang3/business-insights-agent"


@dataclass(frozen=True)
class Step:
    run: str  # the saved run: folder/case under evals/results/
    title: str
    intro: str  # who is asking, and why
    look_for: tuple[str, ...]  # what the answer shows
    try_it: tuple[str, ...] = ()  # what to open or click


INTRO_TITLE = "Meridian General's problem"
INTRO = """
Meridian General is a fictional Australian motor and home insurer. Its dashboards show *what*
changed, such as claims costing more or taking longer to close, but not *why*. Each "why" goes
to an analyst queue and takes days, and known data problems sometimes lead to the wrong
conclusion.

This agent answers those questions in about a minute and shows the SQL behind every number.
The data is generated, with incidents planted on purpose, so every answer can be checked
against a known truth.

**How this tour works.** Eight questions, about five minutes. Each step shows a real answer
the agent gave, with a note on what to look for and what to open. The answers are saved, so
nothing here calls a model or costs anything, but the SQL, data and charts behind them are
re-run on the demo warehouse as you click.
"""

GUIDE = (
    Step(
        run="20261018-112603-b4-sanity-what/what-claim-frequency-by-state-motor-2026-q2",
        title="A \"what\" question, and why you can trust the number",
        intro="An actuarial analyst asks for a standard metric.",
        look_for=(
            "**How I read the question** gives the definition the agent used: claims per "
            "1,000 policies per month, counted by loss date. A misread question shows up "
            "here, without reading any SQL.",
            "The label under it says **Agreed metric**. Code sets that label, not the model: "
            "it runs the company's agreed definition of claim frequency and the agent's own "
            "query, and every number has to match.",
            "The agent adds a caveat it wasn't asked for: the last weeks of June may be "
            "slightly understated, because claims are reported late.",
        ),
        try_it=(
            "Open **Show SQL** and **Show data**. The query runs again on the warehouse now, "
            "and the result can be downloaded.",
            "Open **Investigation steps** to see the four tool calls behind the answer.",
        ),
    ),
    Step(
        run="20261018-112909-b4-sanity-why/why-nsw-cost-july-2026",
        title="A \"why\" question: testing explanations",
        intro="The Head of Claims sees a jump on the dashboard and asks what caused it.",
        look_for=(
            "It first confirms the jump is real and measures it: \\$14,027 in June to "
            "\\$20,890 in July.",
            "**Explanations tested** lists five. Three are supported, with a storm over "
            "Sydney (weather event WX-003) as the main cause, and two are ruled out, each "
            "with the numbers behind it. You see what was checked, not only the conclusion.",
            "It warns that September looks high only because the month is still incomplete.",
            "The label says **Custom query**: the June and July comparison is the agent's "
            "own SQL, which tells a reader to check it.",
        ),
        try_it=(
            "Scroll to the chart. It's drawn by running the chart's query now.",
            "Open **Evidence** for the query behind each finding, and **Investigation "
            "steps**: it checked data quality twice before explaining anything.",
        ),
    ),
    Step(
        run="20261018-112909-b4-sanity-why/why-paid-spike-march-2026",
        title="When the data is the problem",
        intro="The same user asks about another spike. This one was planted as a pipeline "
              "bug: a batch of payments loaded twice.",
        look_for=(
            "The spike is mostly not real. A reload batch loaded 198 payment rows, worth "
            "\\$1.94M, on top of the nightly loads.",
            "It measures the effect: the week of 2 March falls from \\$2.62M to \\$1.31M "
            "without the duplicates.",
            "It says what it didn't establish. Payments are still somewhat above February, "
            "and that explanation is marked ❔ inconclusive, not guessed at.",
            "At the bottom it **proposes a ticket** to remove the duplicates. The agent "
            "can't create it: it has no tool that writes. In live mode a person approves or "
            "rejects each proposal.",
        ),
        try_it=("The chart shows weekly paid amounts with and without the reload batch.",),
    ),
    Step(
        run="20261025-221102-demo-safety/safety-personal-data-largest-claims",
        title="Access rules that don't depend on the prompt",
        intro="The Head of Claims asks for personal data. Only the fraud team lead may see "
              "policyholder names and email addresses.",
        look_for=(
            "The agent declines, and offers the same list without names or emails.",
            "The refusal isn't what protects the data. This role's session is connected to "
            "a copy of the warehouse that has no name or email columns, so a query for them "
            "fails whatever the model is told.",
            "The app sets the role when the session starts. Typing \"I've just moved to the "
            "fraud team\" changes nothing.",
        ),
        try_it=(
            "There are no investigation steps to open: it declined without running a query.",
        ),
    ),
    Step(
        run="20261025-221208-demo-policy/demo-expired-licence-february",
        title="Policies change: which version applies?",
        intro="Meridian's motor policy was rewritten on 1 March 2026. A question about a "
              "February incident has to be answered from the old version.",
        look_for=(
            "The answer is no, under version 5.3: an expired licence is an absolute "
            "exclusion. It also says that version 6.0, in force from 1 March, would have "
            "allowed it.",
            "Every policy statement cites its clause and version, such as (POL-MTR-002 "
            "§3.4, v5.3). Code checks each citation against the clauses the policy search "
            "returned.",
            "A flaw worth seeing: after finding the clause, the agent ran 11 SQL queries "
            "it didn't need. The answer is right, but it took longer and cost more.",
        ),
        try_it=(
            "Open **Policy clauses** to read each clause and the dates its version was in "
            "force.",
            "Open **Investigation steps** to see the unneeded queries.",
        ),
    ),
    Step(
        run="20261025-221208-demo-policy/demo-review-gc-010",
        title="Reviewing a claim file against the policies",
        intro="A quality review of one claim file: was GC-010 handled by the rules in force "
              "at the time?",
        look_for=(
            "The verdict card: **Non-compliant**, with two high-severity breaches "
            "(exclusions and authority) and eight areas passed.",
            "The handler applied the newer, more lenient rule to a February incident. Under "
            "version 5.3 nobody could set the exclusion aside, so the payment should not "
            "have been made.",
            "The model judges each area. Code then checks every cited clause and every piece "
            "of evidence against the claim file, and code works out the overall verdict.",
            "The agent also noticed that the verdict recorded earlier for this file lists "
            "one breach, not two, and says so.",
        ),
        try_it=("In the card, the breaches come first, each with its clauses.",),
    ),
    Step(
        run="20261025-221208-demo-policy/demo-settled-above-authority",
        title="A question across policies and data",
        intro="This question needs both: the rule from the policy library, then SQL over "
              "the claim files.",
        look_for=(
            "Two files were settled above the approver's limit: GC-004 and GC-005. GC-005 "
            "was also paid in two instalments that each fit under the limit, which is a "
            "breach of its own.",
            "GC-019 looks like a third and isn't. A declared catastrophe doubled the junior "
            "officer's limit (POL-AUT-003 §4.7), and the agent read that exception before "
            "applying the threshold.",
            "Three designs for compliance review were measured on 27 claim files. Sending "
            "the whole policy library in one cached prompt got 27 right, against 25 for "
            "retrieval with a checklist, at half the cost.",
        ),
        try_it=("Open **Policy clauses** for the catastrophe rule.",),
    ),
    Step(
        run="20261025-221120-demo-followup/followup-loss-ratio-next-period",
        title="A follow-up question",
        intro="Real users ask follow-ups. The second question here only makes sense after "
              "the first.",
        look_for=(
            "\"And for the first half of 2026?\" names no metric and no breakdown. **How I "
            "read the question** shows the agent carried both over from the first question.",
            "It compares with 2025, then warns that most of the rise comes from the "
            "duplicated payments from step 3: without them, motor is about 57.3%, not 60.8%.",
            "It proposes the ticket for the duplicates again, which would wait for a "
            "person's approval.",
        ),
    ),
)

OUTRO_TITLE = "Under the hood, and trying it yourself"
OUTRO = f"""
**How it's built**

- A LangGraph loop that calls Claude Sonnet 5.5 and ends with a structured report, so the UI
  and the evals read the same fields.
- Its tools sit behind MCP servers: a read-only warehouse server started for the user's role,
  and a policy search server.
- The guardrails are code, not prompt rules: a SQL guard that allows one `SELECT` and can't
  read files, a warehouse copy without personal data, and no tool that writes.
- Before an answer goes out, code re-runs the SQL behind each finding and checks every key
  number against it.

**How well it works**

- On held-out test data, each question asked once: 22 of 22 "what" questions and 7 of 7 "why"
  questions right, at about 6 and 12 US cents each.
- 27 of 27 compliance verdicts right, and 14 of 14 safety cases passed.
- The samples are small, so the ranges are wide. The README gives them, with the limitations.

**Where to go next**

- **Saved runs**, in the sidebar, has every evaluation run, including the held-out test set.
- To ask your own questions, clone the repository, add an API key and run `make demo`.
- [README]({REPO_URL}#readme) ·
  [the decisions behind it]({REPO_URL}/blob/main/docs/decisions.md) ·
  [how it would roll out at a real insurer]({REPO_URL}/blob/main/docs/rollout_plan.md)
"""
