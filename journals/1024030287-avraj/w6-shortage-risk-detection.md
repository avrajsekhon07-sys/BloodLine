# Week 6: Shortage Risk Detection

## Objective

To determine whether the predicted blood demand can be met using the current inventory and classify the shortage risk.

## Work Done

- Implemented shortage-risk detection.
- Used forecasted demand and current stock as inputs.
- Calculated the expected shortfall.
- Implemented LOW, MODERATE, and HIGH risk levels.
- Added special handling for zero-stock situations.
- Generated explanations for the assigned risk level.

## Shortfall Calculation

The expected shortage is calculated as:

Shortfall = Predicted Demand - Current Stock

For example:

Predicted demand = 83.4 units
Current stock = 10 units

Shortfall = 83.4 - 10
          = 73.4 units

## Risk Classification

### LOW

Shortfall ≤ 0

The current stock is sufficient to cover the predicted demand.

### MODERATE

0 < Shortfall ≤ 25% of current stock

There is a shortage, but it remains within the defined moderate threshold.

### HIGH

Shortfall > 25% of current stock

A zero-stock situation with positive predicted demand is also treated as HIGH risk.

## Example

Current stock = 10
7-day forecast = 83.4

Shortfall = 83.4 - 10
          = 73.4

Since the shortfall is greater than the defined threshold, the blood group is classified as HIGH risk.

## Key Learning

Forecasting tells us how much blood may be required, while shortage-risk detection determines whether the current inventory is sufficient to satisfy that predicted demand.

## Outcome

A rule-based shortage-risk detection layer was implemented on top of the forecasting output, producing interpretable LOW, MODERATE, and HIGH risk levels.
