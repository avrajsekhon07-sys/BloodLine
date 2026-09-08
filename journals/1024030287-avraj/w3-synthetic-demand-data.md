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
