---
name: dev-session-start
description: Catch up on the Business Insights Agent's progress and plan before any new work. Use this at the start of a session whenever the user says "start development", "continue development", "let's keep building", "resume", "pick up where we left off", "what's next", or otherwise begins a work session on the agent in this project. Run it first, before writing code or making plans.
---

# Dev Session Start

Each new session starts with no memory of earlier work. Two files in `docs/dev/` hold what you need:

- **DEV_TRACKER.md** records what has been decided, built and blocked so far.
- **DEV_PLAN.md** is the plan: scope, architecture, phases with task checklists, evals, budget, Claude API notes and open decisions.

Reading both first keeps you from redoing finished work, contradicting earlier decisions, missing an open blocker or drifting from the plan.

## Steps

1. Read `docs/dev/DEV_TRACKER.md` in full. If it doesn't exist, tell the user and offer to create one. Don't carry on based on guesses.
2. Read `docs/dev/DEV_PLAN.md` in full. If it doesn't exist, say so and work from the tracker alone.
3. Take a quick look at the project's actual state. List the top-level files, and if it's a git repo, check `git status` and the last few commits. You are only checking whether the tracker and plan have fallen behind, for example the code for an MCP server exists but its plan task isn't ticked. Don't read the whole codebase.
4. Give the user a short catch-up brief:

   - **Where we are:** the current phase, and the agent in one line.
   - **Recently done:** the last 2–3 outcomes from the Dev Log.
   - **Key decisions:** the decisions that shape the next work, such as model, stack and scope.
   - **Open blockers:** any Blockers with status Open, or "None".
   - **Open decisions:** any rows in the plan's Open decisions table that the current phase depends on and that aren't decided yet, or "None".
   - **Suggested next step:** the first unchecked task in the current phase of DEV_PLAN.md, with a one-line reason. If an open blocker or open decision stands in its way, suggest handling that first.

   Point out anything that is out of date and offer to fix it:
   - work that step 3 found but the tracker or plan doesn't mention
   - places where the two files disagree, for example a decision logged in the tracker but still undecided in the plan
5. Ask whether to go ahead with the suggested next step or work on something else, then start.

Keep the brief to about 12 lines. Summarize what matters for today's work rather than repeating the files.

When the work involves code that calls Claude, follow the plan's Claude API notes and use the claude-api skill for current SDK usage. Those rules change over time.

As work happens during the session, use the dev-tracker-update skill to log decisions, outcomes and blockers and to keep the plan in sync.
