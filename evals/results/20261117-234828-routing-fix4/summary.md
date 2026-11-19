# Routing eval (16 questions, 1 run(s))

- Run 1: **15/16** (target 14/16)

Cost $1.25.

| Question | Run | Result | Tools | Reason |
| --- | --- | --- | --- | --- |
| T-01 | 1 | pass | get_metric, check_data_quality, run_sql, run_sql, run_sql |  |
| T-02 | 1 | pass | search_policies, get_policy_clause, get_policy_clause, get_policy_clause, search_policies, get_policy_clause, search_policies |  |
| T-03 | 1 | pass | check_claim_compliance, run_sql, get_policy_clause, run_sql, run_sql, run_sql, run_sql |  |
| T-04 | 1 | pass | search_policies, run_sql, run_sql, run_sql |  |
| T-05 | 1 | pass | get_policy_clause, get_policy_clause, get_policy_clause |  |
| T-06 | 1 | pass | check_claim_compliance, get_policy_clause, run_sql, run_sql |  |
| T-07 | 1 | pass | run_sql, run_sql |  |
| T-08 | 1 | pass | search_policies, run_sql, run_sql, run_sql, run_sql, get_policy_clause, run_sql, run_sql, run_sql, run_sql |  |
| T-09 | 1 | pass | search_policies, run_sql |  |
| T-10 | 1 | pass | check_claim_compliance, run_sql, run_sql, run_sql, run_sql, run_sql |  |
| T-11 | 1 | fail | search_policies, get_policy_clause, run_sql, run_sql | called forbidden run_sql |
| T-12 | 1 | pass | query_metric, check_data_quality, run_sql, run_sql, run_sql, run_sql, run_sql, run_sql, query_metric, run_sql, run_sql, run_sql, run_sql, run_sql, run_sql |  |
| T-13 | 1 | pass | check_claim_compliance, check_claim_compliance, run_sql, run_sql, get_policy_clause, run_sql |  |
| T-14 | 1 | pass | get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause, get_policy_clause |  |
| T-15 | 1 | pass | (none) |  |
| T-16 | 1 | pass | run_sql, search_policies, check_claim_compliance, run_sql, run_sql, get_policy_clause, run_sql |  |
