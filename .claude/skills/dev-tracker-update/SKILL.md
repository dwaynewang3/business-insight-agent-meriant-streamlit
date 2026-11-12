---
name: dev-tracker-update
description: Record real progress on the Business Insights Agent in DEV_TRACKER.md, and keep DEV_PLAN.md in sync, without being asked. Use this proactively right after any of these happens in this project. A decision is settled (agent design, model, framework, architecture, data source, scope, or any item in the plan's Open decisions table). A meaningful piece of work is finished (a plan task, a tool, sub-agent, MCP server, data generator, eval run, UI, README, deploy). A blocker is hit or resolved. Do not use it for trivial fixes such as typos, spelling, indentation, formatting, lint or syntax errors, or for options that are still being discussed.
---

# Dev Tracker Update

This project keeps two files in `docs/dev/` with different jobs:

- **DEV_TRACKER.md** is the log of what happened: decisions, outcomes and blockers. The user reads it to trace progress, and others may read it too. It should read like a clean engineering log, where every line is a real outcome, decision or blocker.
- **DEV_PLAN.md** is the reference plan: scope, architecture, phases with task checklists, evals, budget and open decisions. It must always describe the current plan, so any decision that changes the plan has to change this file too.

Every event goes in the tracker. Change the plan only when an event changes the plan or completes one of its tasks.

## What to record

Record these three kinds of events and nothing else:

| Kind | Meaning | Examples |
| --- | --- | --- |
| Decision | A choice the user made or confirmed | Agent type: analytics investigation agent. UI: Streamlit. |
| Outcome | A meaningful piece of work that now works | Built the warehouse MCP server. Baseline eval: 41/55 pass, $9.80. |
| Blocker | Something that stops or materially slows progress, or the fix for it | The generator's hail incident is too faint for the agent to detect. |

## What not to record

Leave these out, even if they took effort:

- Small fixes: spelling, indentation, formatting, lint, syntax errors, renames, import fixes.
- Options still under discussion. Record a decision only after the user picks or confirms it. Until then it stays in the conversation, out of both files.
- Routine steps that are part of a larger outcome, like installing a package or creating a folder. Record the outcome they add up to.
- Bugs fixed during normal building. A bug belongs in the tracker only if it was a blocker.

When unsure, ask yourself whether the user would want to see this line a month from now, or when explaining the project to someone else. If not, skip it.

## Where each entry goes

Before editing, read DEV_TRACKER.md and the relevant parts of DEV_PLAN.md, so each entry fits the current state and doesn't duplicate an existing one.

- **Decision**
  - Tracker: add a row to the Decision Log with the date, the decision, the options considered, and the reason. Take the reason from the conversation. If none was given, write "—" rather than inventing one.
  - Tracker: update any Project Snapshot field the decision fills (agent name, pitch, model, stack, and so on), and tick any Open Question it answers.
  - Plan: if it settles a row in the Open decisions table, fill in that row's Decided column with the choice and the date.
  - Plan: if it changes the plan itself (scope, stack, architecture, phases, success criteria, budget), update the affected section so the plan stays accurate.
- **Outcome**
  - Plan: tick the matching task in that phase's checklist.
  - Tracker: move the matching Task Board item to Done, or add a Done row. Phase checklists live only in DEV_PLAN.md, so there's nothing to tick in the tracker.
  - Tracker: when every task in a plan phase is ticked, update "Current phase" in the Project Snapshot.
  - For eval runs, include both the score and the cost, as the plan requires.
- **Blocker**
  - Tracker: add a row to the Blockers table with status Open. When the blocker is resolved, update that same row's status and resolution. Don't add a second row.
  - Plan: if the fix changes the plan, for example a task is dropped, added or reordered, update that section.
- **All three:** add one bullet under today's date in the tracker's Dev Log. Newest date goes first, and you create today's heading if it is missing.

## Style

- Write one line per entry. State the result, not the process: "Built the warehouse MCP server", not "Worked on the server and tried a few things".
- Use absolute dates (YYYY-MM-DD).
- Leave out code snippets and stack traces. Include a file path only if it helps someone find the work.
- In the tracker, change only the sections listed above.
- In the plan, change only task checkboxes, the Open decisions table, and sections a decision directly changes. Leave the rest of its wording as it is.

## After updating

Tell the user in one short line what you recorded and which files changed, for example: "Logged in DEV_TRACKER.md and DEV_PLAN.md: decision, UI is Streamlit." This lets them catch anything that shouldn't be there.
