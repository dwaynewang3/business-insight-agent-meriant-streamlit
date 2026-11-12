# Claim Facts Contract

The compliance tool reads **one row per claim** from a view called
`claim_facts`. This file defines that row. `eval/golden_claims.csv` already has
exactly this shape. Your existing mock tables need mapping onto it (step 1 of
the build order in `RAG_PLAN.md`).

## 1. Design rule: claim-side facts in SQL, policy-side rules from RAG

| Computed in SQL (`claim_facts_derived`) | Never computed in SQL — must come from retrieved clauses |
|---|---|
| Day and business-day differences between dates | Authority limits per level (POL-AUT-003 2.1) |
| Sums of payments | Fraud indicator points and the score (POL-FRD-004 2.x, 7.1) |
| Repair cost as % of vehicle value | Excess amounts and waivers (POL-STL-007 3.x) |
| Policy version dates (`coverage_as_of`, `procedure_as_of`) | Thresholds: BAC limits, 30/90-day windows, 75% total loss, etc. |
| | Which documents are required (POL-DOC-005 Appendix A) |

Why the split matters:
- The LLM never does date arithmetic, which is where models make silent
  mistakes.
- Every policy number has exactly one source of truth: the policy text. If
  you hard-code AUD 50,000 in SQL, the knowledge base and the code can drift
  apart, and the RAG path is never really tested.

## 2. Conventions

- Dates are ISO `YYYY-MM-DD`. Booleans are `true`/`false`.
- **Blank means not applicable or not recorded.** For example, a blank
  `bac_reading` means no breath test was done, not a reading of zero.
- Lists are semicolon-separated (`RS-01;HC-01`).
- Amounts are AUD, GST-inclusive, with no thousands separators.
- Clause references inside data use `DOC-ID:clause`, e.g. `POL-MTR-002:3.4`,
  with an optional paragraph, e.g. `POL-CLM-001:2.3(a)`.

## 3. Schema assumptions (unverified — check these against your repo)

This plan was written without access to your codebase. It assumes:

1. Your agent is written in Python and calls Claude through the Anthropic SDK
   using tool use, with one existing SQL tool (called `run_sql` below).
2. The mock database is a single DuckDB file containing a claims table with,
   at minimum, `claim_id`, `policy_id`, claim type, incident date, lodgement
   date, claimed amount, a status or decision, and a settled or paid amount.
3. Most fields below **do not exist yet** in your mock data. The "Tier"
   column shows what to add first:
   - **T1**: fields needed for the six highest-value checks (cover,
     notification, exclusions, authority, fraud, settlement).
   - **T2**: fields needed for triage, assessment, documentation and service
     levels.
4. Golden claims live in their own table (`golden_claim_facts`) and don't mix
   with your analytics data. The `claim_facts` view is the union of your
   mapped claims and the golden claims.

If any of these assumptions is wrong, tell Claude Code and adapt step 1 of the
build order. Nothing else in the plan depends on your table names.

## 4. Field dictionary

### Policy and claimant
| Field | Type / values | Meaning | Used by (check → clauses) | Tier |
|---|---|---|---|---|
| claim_id | VARCHAR | Claim reference | all | T1 |
| policy_id | VARCHAR | Policy number | joins | T1 |
| claim_type | motor / home / liability / travel | Selects applicable documents (`applies_to_claim_types`) | retrieval filter | T1 |
| product_tier | COMP / TPFT / TPPD | Motor product | cover → MTR-002 1.1–1.3; settlement → STL-007 3.1 | T1 |
| declared_use | PRIVATE / BUSINESS | Use declared on the schedule | exclusions → MTR-002 3.7 | T1 |
| endorsements | list: RS-01, HC-01 | Endorsements on the policy | exclusions → MTR-002 3.7; benefits → MTR-002 4.2 | T1 |
| policy_inception_date | DATE | Start of the current period of cover | cover → CLM-001 2.4, 2.5; fraud → T-01 | T1 |
| policy_expiry_date | DATE | End of the current period of cover | cover → CLM-001 2.4; fraud → T-03 | T1 |
| continuous_renewal | BOOLEAN | Period renews a prior Meridian policy | cover → CLM-001 2.5 | T1 |
| renewal_lapse_days | INTEGER | Gap between prior expiry and this inception | cover → CLM-001 2.5 | T1 |
| premium_status_at_incident | PAID / LAPSED | Premium status at the incident date | cover → CLM-001 7.2(d) | T1 |
| sum_insured_basis | MARKET / AGREED | Settlement basis | settlement → STL-007 2.1–2.3 | T1 |
| sum_insured | DECIMAL | Vehicle value: market value at incident (MARKET) or agreed value (AGREED). Mock simplification. | settlement → STL-007 2.1, 4.1 | T1 |
| basic_excess | DECIMAL | Basic excess on the schedule | settlement → STL-007 3.1 | T1 |
| claimant_gst_registered | BOOLEAN | Claimant registered for GST | settlement → STL-007 4.4; documentation | T2 |
| claimant_itc_pct | DECIMAL 0–100 | Input tax credit entitlement % | settlement → STL-007 4.4 | T2 |
| vulnerable_customer | BOOLEAN | Vulnerability flag | service_levels → SLA-006 7.1 | T2 |

### Incident
| Field | Type / values | Meaning | Used by | Tier |
|---|---|---|---|---|
| peril | COLLISION / THEFT / FIRE / STORM / HAIL / FLOOD / MALICIOUS_DAMAGE / GLASS | Cause of loss | cover; documentation → DOC-005 §4 | T1 |
| incident_date | DATE | Date of loss | notification; cover; **coverage version selection** | T1 |
| incident_in_australia | BOOLEAN | | cover → MTR-002 3.16 | T1 |
| catastrophe_event_id | VARCHAR (blank if none) | Declared catastrophe event | authority → AUT-003 4.7; service_levels → SLA-006 6.1; documentation → DOC-005 4.4; settlement → STL-007 3.6 | T1 |
| vehicle_use_at_incident | PRIVATE / BUSINESS / RIDESHARE / GOODS_FOR_HIRE / HIRED_OUT | Actual use at the time | exclusions → MTR-002 3.7 | T1 |
| injury_involved | BOOLEAN | Any person injured | triage → CLM-001 3.2, 3.4; documentation → DOC-005 4.1, 5.1 | T2 |
| total_loss | BOOLEAN | Settled as a total loss | authority → AUT-003 4.1; settlement → STL-007 2.1; documentation → DOC-005 3.6 | T1 |
| insured_at_fault | BOOLEAN | | settlement → STL-007 3.2, 6.1; cover → MTR-002 1.3 | T1 |
| liability_position | CLEAR / DISPUTED / NA | | triage → CLM-001 3.2 | T2 |
| third_party_involved | BOOLEAN | Another party involved | triage (fast-track test); documentation → DOC-005 3.5 | T2 |
| third_party_identified | BOOLEAN | At-fault party's name, address and registration provided | settlement → STL-007 3.2, 6.1; cover → MTR-002 1.3 | T1 |
| police_event_number | VARCHAR (blank if none) | | cover → MTR-002 2.5; documentation → DOC-005 4.1–4.3 | T2 |

### Driver (all blank when `driver_in_control` is false)
| Field | Type / values | Meaning | Used by | Tier |
|---|---|---|---|---|
| driver_in_control | BOOLEAN | A driver was in control (false for parked-vehicle events such as hail or vandalism) | exclusions; settlement; documentation | T1 |
| driver_is_policyholder | BOOLEAN | | exclusions → MTR-002 6.3 | T1 |
| driver_listed | Y / N / NA | NA = the policy doesn't name drivers | exclusions → MTR-002 3.5 | T1 |
| driver_age | INTEGER | Age at incident | settlement → STL-007 3.4(a) | T1 |
| licence_type | FULL / PROVISIONAL / LEARNER | | exclusions → MTR-002 3.2; settlement → STL-007 3.5 | T1 |
| full_licence_years | INTEGER | Years full licence held (0 for learner/provisional) | settlement → STL-007 3.4(b) | T1 |
| licence_status | VALID / EXPIRED / SUSPENDED / CANCELLED | At the incident date | exclusions → MTR-002 3.4 | T1 |
| licence_expired_days | INTEGER | Days expired at incident (0 if valid) | exclusions → MTR-002 3.4 rebuttal | T1 |
| licence_renewed_days_after_incident | INTEGER (blank if not renewed) | | exclusions → MTR-002 3.4 rebuttal | T1 |
| bac_reading | DECIMAL g/100mL (blank if not tested) | | exclusions → MTR-002 3.2; documentation → DOC-005 4.1(c) | T1 |
| drug_test_result | NEGATIVE / POSITIVE / NOT_TESTED | | exclusions → MTR-002 3.3 | T1 |
| registration_status | CURRENT / EXPIRED | | exclusions → MTR-002 3.14, 3.15 | T1 |
| registration_expired_days | INTEGER | | exclusions → MTR-002 3.15 | T1 |

### Handling
| Field | Type / values | Meaning | Used by | Tier |
|---|---|---|---|---|
| fnol_date | DATE | First notification of loss | notification → CLM-001 2.1–2.3 | T1 |
| lodgement_date | DATE | Claim record created | service_levels | T2 |
| ack_date | DATE | Written acknowledgement sent | service_levels → CLM-001 6.1 | T2 |
| triage_date | DATE | | service_levels → CLM-001 3.1; assessment → CLM-001 4.2 | T2 |
| handling_track | FAST / STANDARD / COMPLEX / SIU | Track assigned | triage → CLM-001 3.2; service_levels → SLA-006 3.1, 3.2 | T2 |
| claimed_amount | DECIMAL | Claimant's amount at triage | triage; authority (denials) → AUT-003 2.3; documentation → DOC-005 §6; fraud → FRD-004 5.1(e) | T1 |
| assessment_type | NONE / DESKTOP / FIELD / INDEPENDENT | | assessment → CLM-001 4.1–4.3 | T2 |
| assessment_date | DATE | Assessment report received | assessment → CLM-001 4.2, 4.5 | T2 |
| assessed_amount | DECIMAL | Assessor's repair cost estimate | assessment → CLM-001 4.4; settlement → STL-007 2.1 | T2 |
| documents_on_file | list of DOC-005 Appendix A codes | | documentation → DOC-005 | T2 |
| docs_complete_date | DATE | Last required document received | service_levels → SLA-006 3.1 | T2 |
| max_contact_gap_bd | INTEGER | Longest gap, in business days, between outbound contacts while open. In a real system this comes from a contacts table. | service_levels → CLM-001 6.2, SLA-006 7.1 | T2 |

### Fraud
| Field | Type / values | Meaning | Used by | Tier |
|---|---|---|---|---|
| fraud_indicators | list of FRD-004 codes | Indicators recorded | fraud → FRD-004 §2, 5.1, 7.1 | T1 |
| fraud_score_recorded | INTEGER | Score recorded by the handler (may be wrong; the judge recomputes it from the retrieved points table) | fraud; triage; authority → AUT-003 3.1(e) | T1 |
| siu_referred | BOOLEAN | | fraud → FRD-004 3.2, 5.1 | T1 |
| siu_outcome | SIU-C / SIU-R / SIU-D / SIU-W / SIU-I (blank) | | fraud → FRD-004 3.3, 6.2 | T1 |
| enhanced_verification_done | BOOLEAN | | fraud → FRD-004 4.1 | T1 |

### Decision and authority
| Field | Type / values | Meaning | Used by | Tier |
|---|---|---|---|---|
| decision | ACCEPT / PARTIAL / DENY / PENDING | | all | T1 |
| decision_reason_clause | clause ID (denials) | Clause relied on | cover; service_levels → CLM-001 6.3 | T2 |
| decision_date | DATE | | service_levels; **procedure version selection** | T1 |
| decision_comm_date | DATE | Decision letter sent | service_levels → CLM-001 6.3 | T2 |
| approver_level | L1–L6 | Officer who approved the decision | authority → AUT-003 2.1–2.3 | T1 |
| second_approver_level | L1–L6 (blank) | | authority → AUT-003 3.1; CLM-001 7.4 | T1 |
| exception_applied | clause ID, e.g. `POL-CLM-001:2.3(a)` | Late-notification exception relied on | notification → CLM-001 2.3 | T1 |
| exclusion_override | clause ID of the exclusion set aside | | exclusions; authority → AUT-003 4.3 | T1 |
| total_loss_declared_by_level | L1–L6 (blank) | | authority → AUT-003 4.1 | T1 |

### Settlement and payment
| Field | Type / values | Meaning | Used by | Tier |
|---|---|---|---|---|
| gross_settlement | DECIMAL | Before excess and ITC | settlement | T1 |
| excess_applied | DECIMAL | Total excess deducted | settlement → STL-007 3.x | T1 |
| gst_itc_deduction | DECIMAL | | settlement → STL-007 4.4 | T2 |
| net_paid | DECIMAL | | settlement | T1 |
| total_incurred | DECIMAL | Paid plus outstanding reserve (= net_paid for closed claims) | authority → AUT-003 2.1, 2.2, 3.1(a) | T1 |
| payment_count | INTEGER | | authority → AUT-003 2.2 | T1 |
| payment_amounts | list of amounts | | authority → AUT-003 2.2 | T1 |
| offer_accepted_date | DATE | | service_levels → CLM-001 8.1 | T2 |
| payment_date | DATE | Last payment | service_levels → CLM-001 8.1 | T2 |
| recovery_status | NONE / INITIATED / RECOVERED / WRITTEN_OFF | | settlement → STL-007 6.1 | T2 |

### Narrative
| Field | Type | Meaning | Used by | Tier |
|---|---|---|---|---|
| incident_description | TEXT | What happened | judge context (e.g. C-02, T-05, peril) | T1 |
| handler_notes | TEXT | File notes: approvals, exceptions, contact log | judge context | T1 |

## 5. Derived view

`claim_facts_derived` adds these columns to `claim_facts`. All are claim-side
arithmetic.

| Column | Definition |
|---|---|
| days_incident_to_fnol | `fnol_date - incident_date` |
| days_inception_to_incident | `incident_date - policy_inception_date` |
| bd_lodgement_to_ack | `bd_between(lodgement_date, ack_date)` |
| bd_lodgement_to_triage | `bd_between(lodgement_date, triage_date)` |
| bd_lodgement_to_decision | `bd_between(lodgement_date, decision_date)` |
| bd_docs_complete_to_decision | `bd_between(docs_complete_date, decision_date)` |
| bd_decision_to_comm | `bd_between(decision_date, decision_comm_date)` |
| bd_acceptance_to_payment | `bd_between(offer_accepted_date, payment_date)` |
| bd_triage_to_assessment | `bd_between(triage_date, assessment_date)` |
| days_assessment_to_decision | `decision_date - assessment_date` |
| decided_within_4_months | `decision_date <= lodgement_date + INTERVAL 4 MONTH` |
| repair_cost_pct_of_value | `round(100.0 * assessed_amount / sum_insured, 1)` |
| payments_total | sum of `payment_amounts` |
| coverage_as_of | `incident_date` (selects coverage and settlement documents) |
| procedure_as_of | `coalesce(decision_date, current_date)` (selects procedural documents) |

Business days (POL-SLA-006 2.1–2.2: the day of the event is day 0; count
Mon–Fri excluding NSW public holidays; the Bank Holiday is not excluded):

```sql
CREATE TABLE nsw_public_holidays AS
  SELECT * FROM read_csv('data/nsw_public_holidays_2025_2026.csv');

CREATE OR REPLACE MACRO bd_between(a, b) AS (
  CASE WHEN a IS NULL OR b IS NULL THEN NULL ELSE (
    SELECT count(*)
    FROM generate_series(CAST(a AS TIMESTAMP) + INTERVAL 1 DAY,
                         CAST(b AS TIMESTAMP), INTERVAL 1 DAY) AS t(d)
    WHERE isodow(d) <= 5
      AND CAST(d AS DATE) NOT IN (SELECT holiday_date FROM nsw_public_holidays
                                  WHERE excluded_from_business_days)
  ) END
);
```

Acceptance values from the golden set (use these as tests):

| claim_id | days_incident_to_fnol | bd_lodgement_to_ack | max_contact_gap_bd | Note |
|---|---|---|---|---|
| GC-002 | 104 | 1 | 3 | Late notification |
| GC-003 | 120 | 1 | 3 | Late, but valid exception |
| GC-018 | 1 | 5 | 23 | Late acknowledgement and long gap |

## 6. Which fields each check needs

| Check | What it verifies | Primary clauses | Key fields |
|---|---|---|---|
| cover | Policy in force, waiting period, tier covers the peril, coverage conditions | CLM-001 2.4, 2.5, 7.2; MTR-002 1.1–1.3, 2.5, 3.16 | product_tier, peril, policy dates, continuous_renewal, premium status, police_event_number |
| notification | Notified within 30/90 days; exceptions properly approved | CLM-001 2.1–2.3; AUT-003 3.1(f) | incident_date, fnol_date, exception_applied, approver levels |
| exclusions | Driver, vehicle and use exclusions; rebuttals | MTR-002 §3, 6.1, 6.3; AUT-003 4.3 | driver fields, use, endorsements, exclusion_override, approvers, coverage_as_of |
| triage | Correct handling track | CLM-001 3.2–3.4; FRD-004 7.3 | handling_track, claimed_amount, injury, liability, third party, total_loss, fraud fields |
| assessment | Assessment type and timing | CLM-001 4.1–4.5 | assessment fields, derived day counts |
| authority | Approver limits, dual approval, role rules | AUT-003 2.1–2.3, 3.1, 4.1, 4.7; CLM-001 7.4 | approver levels, decision, total_incurred, claimed_amount, payments, catastrophe_event_id |
| fraud | Score, band, referral, verification | FRD-004 §2, 3.2, 3.3, 4.1, 5.1, 7.1 | fraud_indicators, fraud_score_recorded, siu fields, decision |
| documentation | Required documents on file | DOC-005 1.3, §2–6, Appendix A | documents_on_file, peril, injury, claimed_amount, total_loss, decision |
| service_levels | Timeframes | CLM-001 3.1, 6.1–6.3, 8.1; SLA-006 §3, 6.1, 7.1 | derived business-day columns, max_contact_gap_bd, vulnerable_customer |
| settlement | Excess, ITC, total-loss basis, recovery | STL-007 2.1, 3.1–3.6, 4.4, 6.1; MTR-002 3.6 | settlement amounts, driver age and licence, fault, GST fields, sum_insured |

A check whose key fields are all blank for a claim returns `NOT_ASSESSED`.
That is not `NEEDS_REVIEW`: a missing field in the mock data is not a
compliance problem.
