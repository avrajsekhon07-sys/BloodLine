# Areas and next tasks

Proposed split (edit names if you agree something different). Everyone commits their own work from their
own GitHub account, on a branch, through a pull request that another member reviews. Journal entries go in
`journals/<roll-no>-<name>/`.

| Area | Owner (proposed) | Code |
|---|---|---|
| ML and DevOps/Git | Avraj | `backend/app/services/{forecasting,risk,donor_matching,evaluation}.py`, Evaluation page, `.github/workflows`, Docker |
| Database | Krish | `backend/app/models.py`, `seed.py`, `services/synthetic_data.py`, `backend/alembic/` |
| Backend and security | Kyna | `backend/app/routers/`, `auth.py`, `services/ratelimit.py`, audit log, `tests/test_api.py` |
| Frontend | Manya | `frontend/index.html`, `viz.js`, `sw.js` |

## Avraj: ML and DevOps
- [ ] Confirm the Forecast page lists three models (baseline, exponential smoothing, SARIMA) with the real `statsmodels`; note any difference from the stand-in tests.
- [ ] Write up the evaluation (MAE/RMSE, shortage precision/recall/F1, matching checks) from the Evaluation page.
- [ ] Enable Actions on the fork, get `BloodLine CI` green on a pull request, protect `master`.

## Krish: Database
- [ ] ER diagram and data dictionary for every table in `models.py`.
- [ ] Run the stack on PostgreSQL (`docker compose up`, `alembic upgrade head`, seed) and list any issues.
- [ ] Add indexes for the frequent queries (inventory by bank and group; demand by bank, group and date; donors by blood group) with an Alembic migration.

## Kyna: Backend and security
- [ ] Per-bank access control: staff may only read and change their own bank's data. Add tests.
- [ ] Role-by-endpoint permissions table, with one test per row.
- [ ] Pagination for long lists (transactions, audit log); consistent error messages.

## Manya: Frontend
- [ ] Mobile pass (width 800 px and below) on every page, with screenshots.
- [ ] Accessibility pass: keyboard use, contrast in light and dark themes, labels.
- [ ] A per-role UI test checklist (what to click, what should happen) for the report.
