# Week 4: Demand Forecasting

## Objective

To implement short-term blood-demand forecasting using simple and interpretable forecasting techniques.

## Work Done

- Studied time-series demand forecasting.
- Implemented a 14-day baseline forecasting method.
- Implemented Simple Exponential Smoothing (SES).
- Used an alpha value of 0.3 for SES.
- Generated forecasts for the next 7 days.
- Integrated the forecasting logic into the backend service.

## 14-Day Baseline

The baseline uses the recent 14 days of observed demand to estimate the current daily demand level.

Baseline = Average demand over the last 14 days

The 14-day period is the historical look-back window, while the 7-day period is the future forecast horizon.

## Simple Exponential Smoothing

SES gives more importance to recent observations while gradually reducing the influence of older observations.

The smoothing equation is:

L_t = αX_t + (1 - α)L_(t-1)

where:

α = 0.3

## Forecast Horizon

The system generates a short-term forecast for the next 7 days.

## Key Learning

The historical look-back period and forecast horizon have different purposes:

- 14 days → data used to estimate the current demand level
- 7 days → period for which demand is predicted

## Outcome

The demand forecasting component was implemented and connected to the BloodLine backend.
