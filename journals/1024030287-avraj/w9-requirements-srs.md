# Week 9: Software Requirements Specification

## Objective

To document the complete requirements of the BloodLine platform in a Software Requirements Specification so that design, implementation and testing can be checked against it.

## Work Done

- Contributed to the SRS (version 1.0) for BloodLine with the team. [State your part, for example the forecasting, shortage-risk and donor-matching sections.]
- Described the six user classes (donors, hospital coordinators, inventory staff, blood-bank manager, medical staff, system administrator) and what each role may do.
- Wrote numbered functional requirements grouped by feature: authentication (FR-AUTH), inventory (FR-INV), demand forecasting (FR-FCST), shortage risk (FR-RISK), donor matching (FR-MATCH), requests, screening, notifications, reports and regional view, donor portal and administration.
- Specified the shortage-risk rule: shortfall = forecast demand - current stock; LOW if shortfall <= 0, MODERATE up to 25% of stock, HIGH above 25% or when stock is zero and demand is expected.
- Specified the donor-compatibility table and the matching rules (compatible group, availability, consent, cooldown period).
- Defined the data model (users, donors, blood banks, inventory, transactions, demand history, predictions, alerts, requests, screening records).
- Added non-functional requirements (inventory update within 1 s, dashboard within 3 s and donor search within 2 s for up to 50 users), security requirements and business rules, such as final donor clearance by medical staff only and simulated data never being presented as real.

## Outcome

SRS version 1.0 was completed and added to the repository. It became the checklist for the later implementation and evaluation work.
