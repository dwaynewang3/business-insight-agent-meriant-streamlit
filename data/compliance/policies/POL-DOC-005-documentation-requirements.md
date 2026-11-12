---
doc_id: POL-DOC-005
title: Documentation and Evidence Requirements
policy_family: claims_operations
version: 2.4
effective_from: 2026-01-01
effective_to: null
version_basis: action_date
review_date: 2027-01-01
owner: Head of Claims Operations
applies_to_claim_types: [motor, home, liability, travel]
status: active
supersedes: POL-DOC-005 v2.3
---

# POL-DOC-005 — Documentation and Evidence Requirements

## 1. Purpose and Scope

### 1.1 Purpose
This policy sets the documents and evidence that must be on the claim file
before a claim decision is made, and the rules for requesting, waiving and
verifying them.

### 1.2 Scope
Sections 2, 7, 8 and 9 apply to all claim types. Sections 3 to 6 apply to motor
claims. Document codes used in the claims system are listed in Appendix A.

### 1.3 When documents must be on file
Documents are classified by the stage at which they are required:
- **Decision stage**: documents needed to establish cover, eligibility and
  liability. These must be on file before **any** decision to accept,
  partially accept or deny.
- **Settlement stage**: documents needed to establish quantum or to make a
  payment. These must be on file before a settlement decision, but are not
  required where the claim is denied.

The stage for each document is shown in Appendix A. A decision made without a
required document on file is a procedural breach unless the document was
waived under clause 7.3.

---

## 2. Universal Requirements

### 2.1 Claim form and declaration
Every claim requires a completed claim form or recorded FNOL statement
containing the claimant's declaration that the information provided is true and
complete (code CLAIM_FORM).

### 2.2 Identity verification
The claimant's identity must be verified against two independent sources before
any decision (code ID_VERIFIED).

### 2.3 Bank account verification
Before any payment is released, the payee's bank account must be verified, with
callback verification where the account has not previously been verified
against the claimant record, as required by POL-AUT-003 clause 5.2 (code
BANK_VERIFIED).

---

## 3. Motor Core Documents

### 3.1 Driver's licence
A copy of the licence held by the person driving at the time of the incident is
required for every motor claim in which a driver was in control of the vehicle
(code DRIVER_LICENCE). Where the licence has been lost, a licence record
obtained from the issuing authority may be substituted.

### 3.2 Photographs
At least **four** photographs showing all damaged areas and the full vehicle
are required, taken within **7 days** of the incident or, where the claim is
notified more than 7 days after the incident, within 7 days of notification
(code PHOTOS). Not required for theft of a vehicle that has not been
recovered.

### 3.3 Repair quote
A repair settlement requires a quote from a Meridian-accredited repairer (code
REPAIR_QUOTE_ACCREDITED), or two itemised quotes where the claimant uses a
non-accredited repairer (code REPAIR_QUOTE_2).

### 3.4 Assessment report
Where an assessment is required under POL-CLM-001 clause 4.1, the desktop,
field or independent assessment report must be on file before settlement (code
ASSESSMENT_REPORT).

### 3.5 Third-party details
Where another party is involved, the third party's name, address, vehicle
registration and insurer (if known) must be recorded (code TP_DETAILS).

### 3.6 Total loss documents
Before a total loss settlement, the following are required: proof of ownership
(PROOF_OF_OWNERSHIP), finance payout letter or no-finance declaration
(FINANCE_STATUS), all sets of keys (ALL_KEYS), registration papers
(REGO_PAPERS), and a signed salvage release (SALVAGE_RELEASE).

### 3.7 Evidence for exceptions and rebuttals
Where a late-notification exception under POL-CLM-001 clause 2.3 or the
rebuttal of an exclusion under POL-MTR-002 section 3 is relied upon, the
evidence that the condition is met must be on file before the decision (code
EXCEPTION_EVIDENCE). The file note must identify which condition is satisfied.

---

## 4. Peril-Specific Requirements

### 4.1 Collision
A police event number (code POLICE_EVENT) is required for a collision where:
- (a) any person was injured;
- (b) any party failed to stop or to exchange details; or
- (c) any driver is suspected of being under the influence of alcohol or drugs.

### 4.2 Theft
A theft claim requires a police event number, and the theft must have been
reported to police within **24 hours** of discovery. All sets of keys must be
provided (code ALL_KEYS). The police event number may not be waived.

### 4.3 Malicious damage
A malicious damage claim may not be accepted without a police event number
(code POLICE_EVENT). The police event number may not be waived.

### 4.4 Storm, hail and flood
Confirmation that a weather event occurred at the location and date of loss is
required (code WEATHER_CONFIRMATION), unless the claim is linked to a declared
catastrophe event ID, in which case the event ID is sufficient.

### 4.5 Fire
Where a fire brigade attended, the fire brigade incident report is required
(code FIRE_REPORT).

### 4.6 Glass
Glass claims require the glazier's invoice only (code GLASS_INVOICE).
Photographs are optional.

---

## 5. Injury-Related Requirements

### 5.1 CTP reference
Where any person was injured, the Compulsory Third Party claim reference must
be recorded (code CTP_REFERENCE), consistent with POL-MTR-002 clause 5.2.

### 5.2 Medical information
Motor claims staff must not request or store medical records. Where medical
evidence is needed for a late-notification exception, only a medical
certificate confirming the period of incapacity may be collected.

---

## 6. Value-Based Requirements

### 6.1 Claims above AUD 10,000
Where the claimed amount exceeds **AUD 10,000**, the driver's licence must be
verified with the issuing authority (code LICENCE_VERIFIED, decision stage) and
a vehicle history check obtained (code VEHICLE_HISTORY_CHECK, settlement
stage).

### 6.2 Claims above AUD 50,000
Where the claimed amount exceeds **AUD 50,000**, a statutory declaration from
the driver describing the incident is required (code STAT_DEC).

### 6.3 Claims above AUD 100,000 and total losses
Where the claimed amount exceeds **AUD 100,000**, or the claim is settled as a
total loss, an encumbrance (PPSR) search is required (code PPSR_SEARCH). Claims
above AUD 100,000 also require the independent assessment report required by
POL-CLM-001 clause 4.3 (code INDEPENDENT_ASSESSMENT).

---

## 7. Requests, Timeframes and Waivers

### 7.1 Requesting documents
Outstanding documents must be requested in writing, giving the claimant
**20 business days** to respond, with a reminder sent after 10 business days.
The request starts a timeframe suspension under POL-SLA-006 clause 2.3.

### 7.2 Failure to provide
Where a required document is not provided after the reminder and a final
notice of **10 business days**, the claim may be declined for non-provision.
Indicator D-05 under POL-FRD-004 must be recorded.

### 7.3 Waivers
A settlement-stage document may be waived by an officer at **Level 2** or above
with a file note giving the reason. Decision-stage documents may be waived only
at **Level 3** or above where the document is impossible to obtain. The
following may never be waived: the police event number for theft or malicious
damage, the driver's licence (or issuing-authority record), and bank account
verification.

### 7.4 Substitutes
An equivalent document from an authoritative source (for example an issuing
authority record in place of a licence copy) satisfies the requirement and is
not a waiver.

---

## 8. Authenticity

### 8.1 Originals and metadata
Digital documents must be retained in their original format with metadata
intact. Screenshots of documents are not accepted where an original can be
obtained.

### 8.2 Suspected alteration
Where a document or photograph shows signs of alteration, the handler must
record indicator D-01 or D-04 under POL-FRD-004 and make the mandatory SIU
referral required by POL-FRD-004 clause 5.1. The document must not be returned
to the claimant.

---

## 9. Recording

### 9.1 Document checklist
The document checklist for the claim must be completed in the claims system
before the decision, showing each required code as received, waived or not
applicable.

### 9.2 Docs-complete date
The docs-complete date (POL-CLM-001 clause 1.3) must be recorded when the last
required document is received. It starts the decision timeframe in POL-SLA-006
clause 3.1.

---

## Appendix A — Document Codes

| Code | Document | Required when | Stage | Clause |
|---|---|---|---|---|
| CLAIM_FORM | Claim form or FNOL statement with declaration | All claims | Decision | 2.1 |
| ID_VERIFIED | Claimant identity verified against two sources | All claims | Decision | 2.2 |
| BANK_VERIFIED | Payee bank account verified | Any payment | Settlement | 2.3 |
| DRIVER_LICENCE | Licence of the driver at the incident | Motor, driver in control | Decision | 3.1 |
| PHOTOS | At least four photographs within 7 days | Motor, except unrecovered theft | Decision | 3.2 |
| REPAIR_QUOTE_ACCREDITED | Accredited repairer quote | Repair settlement | Settlement | 3.3 |
| REPAIR_QUOTE_2 | Two itemised quotes (non-accredited repairer) | Repair settlement, non-accredited | Settlement | 3.3 |
| ASSESSMENT_REPORT | Desktop, field or independent assessment report | Assessment required (POL-CLM-001 4.1) | Settlement | 3.4 |
| TP_DETAILS | Third-party name, address, registration, insurer | Third party involved | Decision | 3.5 |
| PROOF_OF_OWNERSHIP | Proof of ownership | Total loss | Settlement | 3.6 |
| FINANCE_STATUS | Finance payout letter or no-finance declaration | Total loss | Settlement | 3.6 |
| ALL_KEYS | All sets of keys | Total loss; theft | Settlement (total loss); Decision (theft) | 3.6, 4.2 |
| REGO_PAPERS | Registration papers | Total loss | Settlement | 3.6 |
| SALVAGE_RELEASE | Signed salvage release | Total loss | Settlement | 3.6 |
| EXCEPTION_EVIDENCE | Evidence for an exception or rebuttal | Exception or rebuttal relied on | Decision | 3.7 |
| POLICE_EVENT | Police event number | Theft; malicious damage; collisions under 4.1 | Decision | 4.1–4.3 |
| WEATHER_CONFIRMATION | Weather event confirmation | Storm, hail, flood without catastrophe event ID | Decision | 4.4 |
| FIRE_REPORT | Fire brigade incident report | Fire, brigade attended | Decision | 4.5 |
| GLASS_INVOICE | Glazier's invoice | Glass claims | Settlement | 4.6 |
| CTP_REFERENCE | CTP claim reference | Any person injured | Decision | 5.1 |
| LICENCE_VERIFIED | Licence verified with issuing authority | Claimed amount > AUD 10,000 | Decision | 6.1 |
| VEHICLE_HISTORY_CHECK | Vehicle history check | Claimed amount > AUD 10,000 | Settlement | 6.1 |
| STAT_DEC | Driver's statutory declaration | Claimed amount > AUD 50,000 | Decision | 6.2 |
| PPSR_SEARCH | Encumbrance (PPSR) search | Claimed amount > AUD 100,000; total loss | Settlement | 6.3 |
| INDEPENDENT_ASSESSMENT | Independent external assessment report | Claimed amount > AUD 100,000 | Settlement | 6.3 |
| GST_DECLARATION | Claimant's GST registration and ITC percentage | Claimant registered for GST | Settlement | POL-STL-007 4.4 |
