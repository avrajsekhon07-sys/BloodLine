# Week 12: Completing the Backend, Extending the Forecasting and Redesigning the Interface

## Objective

To audit the working prototype against the SRS, complete the missing mandatory requirements, strengthen the forecasting evaluation, and replace the basic interface with a polished role-based one.

## Work Done

- Audited the prototype against the SRS and listed the missing requirements.
- Implemented donation recording (FR-INV-5): a donation is accepted only after medical staff screen the donor as eligible and the cooldown has passed; it updates the last donation date and increases stock.
- Added administrator account management (create, deactivate, change role) and an activity log of logins, stock changes and admin actions (FR-ADM-1, FR-ADM-2).
- Added donor self-registration (FR-AUTH-4) and in-app donor notifications sent only to donors who pass the matching rules (FR-NOTE-1).
- Extended the forecasting pipeline: added RMSE next to MAE and a SARIMA model as a third candidate. All models are compared on the same chronological, leakage-free backtest and the lowest-MAE model is selected.
- Added unit-level expiry tracking (FR-INV-6), a multi-bank regional stock and risk view with redistribution suggestions that always need human approval (FR-REG-1), CSV/PDF report export, database migrations, Docker Compose and a CI workflow.
- Fixed three defects found during review: an alert was stored on every dashboard load, a screening result overwrote the donor's last donation date, and first-time donors were shown as "999 days since last donation".
- Replaced the interface with a role-based dashboard: dark and light themes, liquid blood-group tiles, gauges, donut and interactive charts, a donor picker for demo logins and a notification bell.
- Ran the application locally and tested the main flows for each role.

## Testing

Backend unit tests were written for the risk rule (including the SRS example of 20 units in stock and 25 forecast giving MODERATE), donor matching, forecasting evaluation and the API workflows. Each role was tried manually in Chrome.

## Tools and AI assistance

An AI assistant (Claude) was used to generate and refactor code, write tests and help troubleshoot. [Edit this line to match your course's AI-use policy and describe what you did yourself: running, testing, reporting problems, integrating.]

## Outcome

The prototype became a complete role-based application covering the mandatory SRS requirements, with a more rigorous forecasting evaluation.
