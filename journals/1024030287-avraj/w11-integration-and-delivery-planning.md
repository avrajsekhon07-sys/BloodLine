# Week 11: Integration, Testing and Delivery Planning

## Objective

To plan how the remaining parts of the system would be completed, tested and delivered so that every SRS requirement is covered.

## Work Done

- Compared the prototype with the SRS and listed the requirements that were still missing or only partly covered, such as donation recording, account management, activity logging, notifications and the regional view.
- Planned the testing approach: unit tests for the forecasting, risk and matching logic, and end-to-end tests of the role-based API workflows using a separate test database.
- Planned the delivery pipeline: automated linting and tests on every change, a container build, and database migrations so the schema can evolve safely.
- Thought through role-based access and security needs: password hashing, expiring tokens, per-role permissions and limits on repeated failed logins.
- Sketched the structure of the dashboards for each role and the information each one should show.
- Planned the division of work across the team by area (database, backend, frontend, forecasting).
- [Add any notes or discussion points here.]

## Outcome

A prioritised plan for completing, testing and delivering the project, which was followed in the weeks after.
