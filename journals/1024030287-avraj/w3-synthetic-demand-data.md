# Week 3: Synthetic Blood-Demand Data Generation

## Objective

To generate realistic synthetic blood-demand data for developing and testing the forecasting module.

## Problem

Detailed real-world blood-bank demand data was not available for the prototype. Therefore, synthetic data was required to simulate historical blood demand.

## Work Done

- Implemented synthetic demand generation.
- Generated 180 days of historical demand.
- Generated demand for all eight blood groups.
- Defined different baseline demand levels for each blood group.
- Added weekly demand patterns.
- Added seasonal variation.
- Added holiday/event effects.
- Added rare emergency spikes.
- Added random noise to make the data more realistic.
- Ensured that generated demand values remain non-negative.

## Demand Model

The generated demand is based on multiple components:

```text
Demand =
Baseline
+ Weekly Pattern
+ Seasonal Effect
+ Holiday Bump
+ Emergency Spike
+ Random Noise
```

## Parameters Used

| Component | Value |
|---|---|
| Baseline (units/day) | O+ 18, A+ 15, B+ 13, O- 7, A- 6, AB+ 5, B- 5, AB- 2.5 (higher for common blood groups) |
| Weekly pattern | +10% of baseline on weekdays, -18% on weekends (elective surgery is scheduled midweek) |
| Seasonal effect | Yearly sine wave with an amplitude of 12% of baseline |
| Holiday bump | +35% of baseline within two days of eight fixed days of the year (festival/accident periods) |
| Emergency spike | On about 2% of days, an extra 80-180% of baseline (mass-casualty or local emergencies) |
| Random noise | Gaussian noise with a standard deviation of 8% of baseline |

Final values are clipped at zero and rounded to one decimal place. Each blood group uses a fixed random seed derived from its name, so the same data is generated on every run and results can be reproduced.

## Labelling

The data is stored with an `is_synthetic` flag and every page and API response that shows it labels it as synthetic, so it is never presented as real hospital statistics.

## Key Learning

A forecasting model can only be tested properly if the data contains realistic structure. Combining a per-group baseline with weekly, seasonal and random components produces data that behaves like real demand, including occasional unpredictable spikes that the models must cope with.

## Outcome

A reproducible 180-day synthetic demand dataset for all eight blood groups was created and used to develop and evaluate the forecasting and shortage-risk components.
