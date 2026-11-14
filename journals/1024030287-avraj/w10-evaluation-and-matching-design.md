# Week 10: Evaluation Design and Matching Rules Planning

## Objective

To decide, after the SRS was written, how the system's forecasting, shortage-risk detection and donor matching would be verified against the proposal's success metrics.

## Work Done

- Re-read the SRS requirements for forecasting (FR-FCST), shortage risk (FR-RISK) and donor matching (FR-MATCH) and listed what each would need to be tested.
- Worked out how to evaluate shortage detection when historical stock is not recorded: forecast each future week from earlier data only, compare with what actually happened, and test the risk rule against a range of possible stock levels.
- Planned a way to check donor matching independently: use the SRS compatibility table as the reference and verify that every returned donor is compatible, available, consenting and past the cooldown, and that no eligible donor is left out.
- Thought through the rule thresholds (LOW, MODERATE, HIGH) and the edge cases, such as zero stock with expected demand and a shortfall of exactly zero.
- Planned how seasonality, parameter choice for SARIMA and the risk of fitting on future data would be handled.
- [Add any notes or discussion points here.]

## Outcome

An evaluation plan covering forecast error, shortage detection and matching correctness, ready to be turned into code and tests.
