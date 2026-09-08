# Week 5: Forecast Evaluation

## Objective

To evaluate the forecasting approaches and select the better-performing model using historical data.

## Problem

A forecasting model should be evaluated before being used for future predictions. Since actual future demand is not available at the time of forecasting, historical data was used for backtesting.

## Work Done

- Implemented rolling-origin backtesting.
- Evaluated both the baseline and SES forecasting approaches.
- Used Mean Absolute Error (MAE) as the evaluation metric.
- Compared predicted historical demand with actual historical demand.
- Calculated the error for different forecasting origins.
- Compared the average MAE of the candidate models.
- Selected the model with the lower MAE.

## Backtesting Process

Historical Demand
       ↓
Select a historical forecast origin
       ↓
Generate forecast using only previous data
       ↓
Compare forecast with actual demand
       ↓
Calculate MAE
       ↓
Move the forecast origin forward
       ↓
Repeat

## MAE

Mean Absolute Error is calculated as:

MAE = Mean(|Actual - Predicted|)

A lower MAE indicates that the forecasting method produced smaller prediction errors.

## Model Selection

The baseline and SES models were evaluated using the same historical data. The model producing the lower MAE was selected for the final forecast.

## Key Learning

The actual future demand cannot be compared with today's prediction immediately because the future values are not yet known. Backtesting solves this problem by using known historical data to simulate future predictions.

## Outcome

The forecasting pipeline was enhanced with objective evaluation and model selection instead of relying on a single forecasting method without validation.
