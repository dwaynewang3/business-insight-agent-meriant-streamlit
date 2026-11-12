# Glossary

Business terms used in Meridian General Insurance's claims warehouse. Meridian is an Australian motor and home insurer; all amounts are in Australian dollars (AUD). Metric definitions are in `metrics.yaml`, and table and column descriptions are in `tables.yaml`.

## Regions

Meridian works in all eight Australian states and territories, grouped into four regions:

- **NSW & ACT:** NSW, ACT
- **VIC & TAS:** VIC, TAS
- **QLD & NT:** QLD, NT
- **West & South:** WA, SA

Adjusters work claims in one region. A place name such as "New South Wales", "Victoria" or "Queensland" means the state (filter on `state`), not the region that contains it.

## Products and causes of loss

- **Motor:** collision, glass, storm, theft, third_party_property
- **Home** (building and contents): water_damage (escape of liquid), storm, fire (including bushfire), theft, liability

**Storm** covers wind, hail and rain damage. Motor policies don't cover injuries to people: in Australia those are claimed from compulsory third party (CTP) insurance, which Meridian doesn't sell. **Third-party property** claims pay for damage the insured caused to someone else's car or property.

Third-party property and liability claims are reported later and take longer to settle than damage to the insured's own car or home.

Seasons are southern-hemisphere: summer is December to February. Storm claims peak in Queensland from December to March and in New South Wales in spring, and bushfires peak in Victoria in summer.

## Claim lifecycle

A claim moves through these dates:

1. **Loss date:** when the damage happened.
2. **Report date:** when the customer told the insurer.
3. **Payments:** one or more payments while the claim is handled.
4. **Close date:** when the claim was settled.

A claim is **open** until it closes. Some claims close without any payment, for example when the loss is below the excess or isn't covered.

## Money terms

- **Paid:** money already paid on a claim.
- **Reserve:** money set aside for future payments on an open claim. It's an estimate and changes as the claim develops.
- **Incurred:** paid plus reserve. It's the best estimate of what a claim will cost in total.
- **Average claim cost (severity):** incurred divided by the number of claims.
- **Earned premium:** the part of the premium that covers the period being measured.
- **Excess:** the amount the policyholder pays towards each claim (called a deductible in some countries).
- **Loss ratio:** incurred losses divided by earned premium.

## Exposure and frequency

- **Policies in force:** policies providing coverage during a month, counted as policy-months.
- **Claim frequency:** claims per 1,000 policies in force, per month. Use frequency rather than raw claim counts when the number of policies changes over time.

## Data freshness

The warehouse is a snapshot taken on the extract date, which is in the `warehouse_info` table. Anything reported or paid after that date is missing. Claims are often reported days or weeks after the loss, so the most recent weeks are incomplete. Payments load into the warehouse overnight in batches.

## Sales channels

- **broker:** sold through insurance brokers.
- **direct:** sold by Meridian's own call centre.
- **online:** bought on the insurer's website.
- **partner:** sold through partner companies. A bank partnership for home insurance launched in January 2026.

## Repair network

Preferred repair shops are in the insurer's network and have agreed rates. Non-preferred shops aren't. Customers can choose any shop.

## Data access by role

- **Head of Claims, claims operations manager and actuarial analyst:** all data except personal data.
- **Fraud team lead:** all data, including personal data.

Personal data means policyholder names and email addresses.
