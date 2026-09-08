# Week 2: System Design

## Objective

To understand the architecture, data flow, and database structure required for integrating the predictive component into BloodLine.

## Work Done

- Studied the high-level architecture of the BloodLine system.
- Studied the Level 0 and Level 1 Data Flow Diagrams.
- Understood the communication between the frontend, FastAPI backend, application services, and SQLite database.
- Identified the database tables relevant to demand forecasting and shortage-risk analysis.
- Studied the role of demand history, inventory, predictions, and alerts in the predictive workflow.
- Traced how forecasting results are passed to the shortage-risk component.

## Relevant Data

The predictive module mainly works with:

- Demand history
- Current inventory
- Forecast predictions
- Shortage-risk alerts

## Key Learning

The predictive functionality is implemented as part of the backend service layer. The frontend communicates with the backend through REST APIs and JSON responses, while the backend interacts with the SQLite database.

## Outcome

Understood the system architecture and established how the forecasting and risk-analysis components fit into the complete BloodLine system.
