# Using the warehouse from Claude Code

The warehouse MCP server works from any MCP client, not only from this project's agent. This folder shows it in Claude Code, with the agent's investigation playbook packaged as an Agent Skill.

## Set up

From the project root, after `uv sync` and `make data`:

```bash
cp claude_code/mcp.json .mcp.json                       # registers the claims-warehouse server
mkdir -p .claude/skills
cp -r claude_code/skills/investigate-claims .claude/skills/
```

Start Claude Code in the project root and approve the `claims-warehouse` server when asked. Then ask a question such as "Why did the average claim cost in New South Wales jump in July 2026?". The skill guides the investigation, and the server's six read-only tools do the querying.

## Tried

- The test suite starts the server with `mcp.json`'s exact command, checks it offers the six tools, and checks the skill names only tools the server has ([tests/test_claude_code.py](../tests/test_claude_code.py)).
- In Claude Code 2.1.289 (2026-11-10, a headless `claude -p` run on Sonnet 5.5), the question above loaded the `investigate-claims` skill and used five of the six tools in 13 turns and 33 seconds. It reached the agent's own answer: the East Coast Low (WX-003), with the average rising from $14,027 to $20,890 and back to $14,016 without the storm claims.

## Choosing the role

The role is set when the server starts, in `.mcp.json` (`--role head_of_claims`). Every role except `fraud_team_lead` uses the warehouse copy without personal data, so a Claude Code user can't reach names or emails by asking, whatever the prompt says.

## What's the same, and what isn't

The tools, the SQL guard, the restricted warehouse copy and the agreed metric definitions are exactly the ones the agent uses. What Claude Code doesn't get is the agent's structured report, its per-question caps on cost and tool calls, its approval step for tickets and alerts, and its tracing. Those live in the agent's graph, not in the server.
