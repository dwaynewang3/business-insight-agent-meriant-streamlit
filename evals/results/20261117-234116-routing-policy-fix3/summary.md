# Routing eval (4 questions, 2 run(s))

- Run 1: **3/4** (target 14/16)
- Run 2: **3/4** (target 14/16)

Cost $0.54.

| Question | Run | Result | Tools | Reason |
| --- | --- | --- | --- | --- |
| T-02 | 1 | pass | search_policies, get_policy_clause, get_policy_clause, search_policies, get_policy_clause, search_policies |  |
| T-05 | 1 | pass | get_policy_clause, get_policy_clause, get_policy_clause |  |
| T-11 | 1 | fail | search_policies, get_policy_clause, search_policies, search_policies, search_policies, search_policies, run_sql, get_policy_clause, get_policy_clause, get_policy_clause, run_sql, get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause | called forbidden run_sql |
| T-15 | 1 | pass | (none) |  |
| T-02 | 2 | pass | search_policies, search_policies, get_policy_clause, get_policy_clause, search_policies, get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause, search_policies |  |
| T-05 | 2 | pass | get_policy_clause |  |
| T-11 | 2 | fail | search_policies, get_policy_clause, run_sql, search_policies, search_policies, run_sql, search_policies, run_sql, get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause | called forbidden run_sql |
| T-15 | 2 | pass | (none) |  |
