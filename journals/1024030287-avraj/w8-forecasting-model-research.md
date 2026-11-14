# Week 8: Forecasting Model Research

## Objective

To study which time-series models suit blood-demand data better than the baseline and Simple Exponential Smoothing (SES) built earlier, and to plan how they would be compared.

## Work Done

- Reviewed the limits of the baseline and SES models: both forecast a flat level, so they cannot represent the weekly pattern in daily demand.
- Studied SARIMA (seasonal ARIMA) and Prophet as the two options named in the proposal, including what the order terms (p, d, q) and the seasonal terms mean and why a seven-day season fits daily demand.
- Compared the options on practical grounds: data needed, ease of fitting, interpretability, dependencies and how well each can be evaluated fairly against the existing models.
- Planned the evaluation protocol: a chronological train/test split, no use of future data when forecasting, MAE and RMSE as the metrics, and the moving-average baseline as the reference every model must beat.
- Outlined how the model would be kept replaceable, so a new model can be added without changing the API.
- [Add any sources, notes or discussions with teammates here.]

## Outcome

A clear plan: add SARIMA as a third candidate next to the baseline and SES, and compare all three on the same chronological backtest.
