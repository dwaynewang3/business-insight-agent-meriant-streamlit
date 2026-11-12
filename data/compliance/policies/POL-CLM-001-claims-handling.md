---
doc_id: POL-CLM-001
title: Claims Handling Procedure
policy_family: claims_operations
version: 4.2
effective_from: 2026-01-01
effective_to: null
version_basis: action_date
review_date: 2027-01-01
owner: Head of Claims Operations
applies_to_claim_types: [motor, home, liability, travel]
status: active
supersedes: POL-CLM-001 v4.1
---

# POL-CLM-001 — Claims Handling Procedure

## 1. Purpose and Scope

### 1.1 Purpose
This procedure defines the mandatory end-to-end handling steps for all claims
lodged with Meridian General Insurance. It applies from first notification of
loss (FNOL) through to closure or denial.

### 1.2 Scope
This procedure applies to all claim types. Where a product-specific policy
(for example POL-MTR-002 for motor) states a different rule, the
product-specific rule prevails for that claim type only. All other clauses of
this procedure continue to apply.

### 1.3 Definitions
- **FNOL**: First notification of loss — the first contact in which a claimant
  reports an incident, whether or not a claim number is issued.
- **Lodgement date**: The date the claim record is created in the claims
  system. This may differ from the FNOL date.
- **Incident date**: The date the insured event occurred.
- **Business day**: Monday to Friday excluding NSW public holidays.
- **Material change**: Any amendment to claim value exceeding 20% of the
  previously recorded reserve, or any change to liability position.
- **Estimated value**: The claimed amount at triage, replaced by the assessed
  amount once an assessment report is received.
- **Docs-complete date**: The date on which the last document required under
  POL-DOC-005 for the decision was received.

---

## 2. Notification and Lodgement

### 2.1 Notification window
A claim must be notified to the insurer within **30 calendar days** of the
incident date. Claims notified between 31 and 90 days may still be accepted
where the claimant provides a reasonable explanation for the delay and the
delay has not prejudiced the insurer's ability to assess the claim.

### 2.2 Late notification beyond 90 days
A claim notified more than **90 calendar days** after the incident date must be
declined unless approved under clause 2.3.

### 2.3 Late notification exception
Late notification beyond 90 days may be accepted where **any** of the following
applies, and the exception is recorded against the claim with the approver's
identity:
- (a) The claimant was hospitalised or medically incapacitated for a
  continuous period covering the notification window.
- (b) The claim arises from a declared catastrophe event, in which case the
  notification window extends to 12 months from the incident date.
- (c) The claimant is a minor or under legal guardianship at the time of the
  incident.
- (d) A third party made a written demand or commenced recovery action against
  the insured after the notification window, and the insured notified within
  30 days of receiving the demand or being served.

Exceptions under 2.3 require approval at Level 3 or above per POL-AUT-003.

### 2.4 Cover-in-force check
At lodgement the handler must confirm the incident date falls on or after the
policy inception date and on or before the policy expiry date. A claim with an
incident date outside the period of cover must be declined under clause 7.2(a).

### 2.5 Waiting period
No claim may be admitted where the incident date falls within **72 hours** of
the policy inception date, except where the policy is a continuous renewal of a
prior Meridian policy with no lapse exceeding 14 days.

---

## 3. Triage and Segmentation

### 3.1 Triage within one business day
Every lodged claim must be triaged within **1 business day** of lodgement and
assigned a handling track under clause 3.2.

### 3.2 Handling tracks
Tracks are tested in the order shown. The first track whose criteria are met
is assigned.

| Order | Track | Criteria | Handling |
|---|---|---|---|
| 1 | Special Investigation (SIU) | Fraud score ≥ 60 under POL-FRD-004 clause 3.2, or any mandatory referral trigger under POL-FRD-004 clause 5.1 | Referred to SIU; standard handling paused |
| 2 | Complex | Estimated value > AUD 50,000, OR any bodily injury, OR disputed liability, OR total loss | Mandatory field assessment; senior handler assignment |
| 3 | Fast-track | Estimated value ≤ AUD 5,000, no third party involved, liability clear, no injury | Desktop handling; no field assessor |
| 4 | Standard | All other claims | Desktop or field assessment at handler discretion |

### 3.3 Re-triage on material change
Where a claim's estimated value changes such that it crosses a track boundary
in clause 3.2, the claim must be re-triaged within 2 business days and
reassigned. A claim may not remain on fast-track once its reserve exceeds
AUD 5,000.

### 3.4 Injury claims
Any claim involving bodily injury, regardless of value, must be handled on the
Complex track. Fast-track handling of an injury claim is a procedural breach
and must be escalated to the Claims Manager.

---

## 4. Assessment

### 4.1 Assessment requirement
An assessment is required for all claims except fast-track claims where
photographic evidence is sufficient to establish quantum. An independent
external assessment (clause 4.3) counts as a field assessment.

### 4.2 Assessor allocation timeframe
Where a field assessment is required, an assessor must be allocated within
**3 business days** of triage, and the assessment completed within **10
business days** of allocation.

### 4.3 Independent assessment threshold
Claims with an estimated value exceeding **AUD 100,000** require an independent
external assessor. An internal assessor may not sign off quantum above this
threshold.

### 4.4 Second assessment
A second independent assessment is required where:
- (a) the claimant formally disputes the first assessment in writing; or
- (b) the variance between the claimant's quantum and the assessor's quantum
  exceeds **30%** or AUD 20,000, whichever is greater; or
- (c) the first assessor has a recorded conflict of interest.

### 4.5 Assessment validity
An assessment older than **90 calendar days** at the time of settlement
decision must be refreshed. Settlement on a stale assessment is a procedural
breach.

---

## 5. Reserving

### 5.1 Initial reserve
An initial reserve must be set within **2 business days** of triage. Where
quantum is unknown, a case reserve of AUD 5,000 (motor), AUD 15,000 (home) or
AUD 25,000 (liability) must be applied as a placeholder.

### 5.2 Reserve review cadence
Reserves must be reviewed at minimum every **30 calendar days** while the claim
remains open, and immediately upon receipt of an assessment report.

### 5.3 Reserve adequacy
A reserve that is more than 25% below the final settled amount at closure is
flagged as a reserving variance and reported in the monthly claims
reconciliation.

---

## 6. Communication Obligations

### 6.1 Acknowledgement
The claimant must receive written acknowledgement of their claim within
**2 business days** of lodgement, including the claim number and the name of
the assigned handler.

### 6.2 Status updates
While a claim is open, the claimant must receive a status update at least every
**20 business days**. A period exceeding 20 business days with no outbound
contact is a service breach recorded against the handler.

### 6.3 Decision communication
A decision to accept, partially accept or deny must be communicated in writing
within **5 business days** of the decision being made, with reasons and the
clause relied upon.

---

## 7. Decision

### 7.1 Decision authority
All accept, deny and settle decisions must be made within the delegated
authority of the deciding officer as set out in POL-AUT-003. A decision made
outside delegated authority is void and must be re-made by an appropriately
authorised officer.

### 7.2 Mandatory denial grounds
A claim must be denied where:
- (a) the incident date falls outside the period of cover (clause 2.4);
- (b) the claim is notified beyond 90 days with no clause 2.3 exception;
- (c) an absolute exclusion applies under the relevant product policy;
- (d) premium was unpaid and the policy was in lapse at the incident date;
- (e) fraud is substantiated per POL-FRD-004 section 6.

### 7.3 Partial acceptance
Where part of a claim is covered and part is excluded, the covered portion must
be settled within normal timeframes. A disputed component may not be used to
delay payment of an undisputed component beyond **10 business days**.

### 7.4 Denial review
Every denial with a claimed value above **AUD 25,000** must be peer-reviewed by
a second officer at Level 3 or above before being communicated.

---

## 8. Payment and Closure

### 8.1 Payment timeframe
Approved settlements must be paid within **10 business days** of the claimant
accepting the settlement offer.

### 8.2 Closure criteria
A claim may be closed when payment has been made and acknowledged, the claim
has been denied and the review period has expired, or the claimant has
withdrawn in writing.

### 8.3 Review period
A denied claimant has **30 calendar days** from the date of the denial letter
to request internal review. The claim may not be closed during this period.

### 8.4 Reopening
A closed claim may be reopened within **12 months** of closure where new
material evidence is produced. Reopening beyond 12 months requires Level 4
approval.

---

## 9. Record Keeping

### 9.1 File note obligation
Every substantive action, decision or claimant contact must be recorded as a
file note on the same business day it occurs.

### 9.2 Retention
Claim files must be retained for **7 years** from closure, or 7 years from the
date a minor claimant attains majority, whichever is later.

---

## 10. Escalation and Breach

### 10.1 Breach recording
Any breach of a mandatory timeframe in this procedure must be recorded as a
procedural exception with a reason code.

### 10.2 Escalation thresholds
- Three or more timeframe breaches on a single claim escalate to Claims Manager.
- Any breach on a claim above AUD 100,000 escalates immediately to Head of
  Claims Operations.

### 10.3 Complaints
A claimant expression of dissatisfaction must be logged as a complaint and
acknowledged within 1 business day, with substantive response within
**30 calendar days**.
