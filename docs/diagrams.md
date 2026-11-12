# Architecture diagrams

As of 2026-10-19. The same diagrams, with the tools, results and guardrails around them, are in [architecture_overview.html](architecture_overview.html) (open it in a browser). The design and its reasons are in [architecture.md](architecture.md).

## How a question flows

The app fixes the user's role and starts the MCP servers for it. The LangGraph loop calls Claude until it writes a structured report. Nothing the model calls can write to data; actions wait for a person. Every role except the fraud team lead is connected to the copy without personal data.

```mermaid
flowchart LR
  U["User<br/>Streamlit UI · CLI"] -->|"question + role"| G
  subgraph AG ["Agent · agent/graph.py"]
    direction TB
    G["LangGraph loop<br/>Claude Sonnet 5.5, medium effort"] --> R["Structured report<br/>answer · SQL · findings · hypotheses<br/>data issues · charts · proposed actions"]
  end
  G -->|MCP| W["Warehouse server<br/>one per role"]
  G -->|MCP| P["Policies server<br/>read-only"]
  G -->|"agent-side tool"| C["Compliance review<br/>check_claim_compliance"]
  W --> SG{{"SQL guard<br/>one SELECT · read-only"}}
  SG --> DW[("dev.duckdb<br/>full copy")]
  SG --> DR[("dev_restricted.duckdb<br/>no names or emails")]
  P --> KB[("policies.duckdb<br/>252 clauses · 8 policies")]
  C --> DR
  C --> KB
  C -->|"judge call"| J["Claude<br/>structured output"]
  R -->|"proposed tickets, alerts"| A{"Person approves?"}
  A -->|"approved only"| X["Actions server<br/>create_ticket · create_alert<br/>optionally a GitHub issue"]
  G -.-> L["Spend ledger · local traces · Langfuse"]
```

## A compliance review

The agent uses full context: the whole policy library fits in one cached prompt. Code, not the model, checks every finding and sets the verdict. The checklist design (v1) instead retrieves clauses per area and makes ten judge calls, with one retry when validation fails. Results: [compliance_results.md](compliance_results.md).

```mermaid
flowchart LR
  F["Claim file<br/>claim_files_derived<br/>96 facts, business days in SQL"] --> D["Dates<br/>incident date: cover, settlement<br/>decision date: procedures"]
  D --> M["Judge prompt<br/>cached: rules + whole library<br/>then the claim's facts"]
  M --> J["Judge call<br/>Sonnet 5.5, structured output<br/>reasoning before status"]
  J --> V{"Checks in code"}
  V -->|"clause supplied? version in force?<br/>evidence matches the file?<br/>breach has clause and severity?"| AGG["Verdict in code<br/>any breach: non-compliant<br/>any to review: needs review<br/>else compliant"]
  AGG --> OUT["Verdict card in the UI<br/>compliance_results · compliance_findings"]
```

## Data and evaluation

The agent never sees an answer key. The test data was generated once, after all development, and each of its questions was asked once.

```mermaid
flowchart LR
  S1["scenarios/dev.yaml<br/>seed 20251004"] --> GEN["Seeded generator<br/>data/generator"]
  S2["scenarios/test.yaml<br/>seed 20261019, new incidents"] --> GEN
  GEN --> DEV[("dev.duckdb + answer key")]
  GEN --> TEST[("test.duckdb + answer key")]
  K["Policy kit<br/>8 policies · 27 claim files"] --> KB[("policies.duckdb")]
  K --> DEV
  DEV --> E1["run_evals --suite dev<br/>what · why · safety · follow-up"]
  TEST --> E2["run_evals --suite test<br/>scored once"]
  DEV --> E3["compliance_eval<br/>18 dev + 9 held-out files"]
  KB --> E4["retrieval eval · routing eval"]
  E1 & E2 --> GR["Graders<br/>re-run the agent's SQL · Opus LLM grader (batch)<br/>key numbers traced to their query"]
  E3 --> GC["Compliance grader<br/>match by clause and version"]
```
