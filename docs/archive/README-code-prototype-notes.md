# BloodLine — Predictive Blood Shortage & Smart Donor Matching Platform

Inventory tracking, 7-day demand forecasting, rule-based shortage-risk detection and
donor matching in one role-based web app (FastAPI + SQLAlchemy backend, dependency-free
static frontend). **All demand data is synthetic/simulated and labelled as such.**
BloodLine never makes medical eligibility decisions: donors are only *suggested*, and
medical staff enter every screening outcome.

## Frontend
No build step and no npm packages (works offline): `frontend/index.html` (app), `frontend/viz.js` (hand-built SVG visual kit: liquid blood-drop
tiles, tick gauges, donut, interactive area/bar charts with tooltips, count-up numbers) and `frontend/sw.js` (Web Push). Dark and light themes,
saved per browser, following the system setting on first visit. Respects `prefers-reduced-motion`.

## Run locally

```bash
cd backend
python3 -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed                                    # demo data (drops and recreates tables!)
uvicorn app.main:app --reload --port 8000             # docs: http://localhost:8000/docs

cd ../frontend && python3 -m http.server 5500         # open http://localhost:5500
```
The frontend calls `http://localhost:8000`; to change it run
`localStorage.bl_api = "https://your-api"` in the browser console.
The login page lists every demo account (staff chips plus a picker for all 15 donors with blood group and status). Demo logins (password `bloodline123`): manager@, inventory@, hospital@, screening@, admin@,
donor1@ … donor15@ `bloodline.demo`.

## Environment variables
| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy URL (SQLite or PostgreSQL) | `sqlite:///./bloodline.db` |
| `BLOODLINE_SECRET_KEY` | JWT signing key (**required** when `BLOODLINE_ENV=production`) | dev placeholder |
| `BLOODLINE_ENV` | `production` refuses to start with the placeholder secret | unset |
| `ALLOWED_ORIGINS` | comma-separated CORS origins | `*` |
| `BLOODLINE_SARIMA` | set `0` to disable the SARIMA candidate (baseline + exponential smoothing only) | enabled |
| `BLOODLINE_USE_MIGRATIONS` | `1` = schema managed by Alembic instead of `create_all` | unset |
| `BLOODLINE_SHELF_<COMPONENT>` | shelf life in days, e.g. `BLOODLINE_SHELF_PLATELETS=5` (defaults are planning values, **not medical guidance**: set your blood centre's policy) | whole_blood 35, red_cells 42, platelets 5, plasma 365 |
| `BLOODLINE_DEMO_TOOLS` | `0` disables `POST /demo/scenario` (the Scenarios page's simulate-shortage/restock buttons, which change stock); always off in production | enabled |
| `LOGIN_RATE_LIMIT` | `0` turns login rate limiting off | on |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_MAX_ATTEMPTS_PER_IP` / `LOGIN_WINDOW_SECONDS` | failed sign-ins allowed per account+IP / per IP within the window (then HTTP 429 with `Retry-After`) | 5 / 20 / 900 |
| `BLOODLINE_DEMO_LOGIN` | `0` disables `GET /auth/demo-accounts` (the unauthenticated demo account picker on the login page); always off when `BLOODLINE_ENV=production` | enabled |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` | enable Web Push (generate with `python scripts/gen_vapid.py`) | push disabled |

## Forecasting notes
SARIMA needs `statsmodels` (in `requirements.txt`); if it is missing or a fit fails, the pipeline falls back to the other two
models without error. It needs at least 60 days of history. Fitting takes a moment, so results are cached while the data is
unchanged: the first dashboard load after seeding can be slower than later ones. Forecasts are trained on synthetic data and are
risk signals, not validated clinical predictions.

## Tests, lint, CI
```bash
cd backend && pip install -r requirements-dev.txt
ruff check . && pytest -q       # tests/test_logic.py (pure logic) + tests/test_api.py (end-to-end, temp DB)
```
GitHub Actions (`.github/workflows/ci.yml`) runs lint + tests and builds the API image on every push.

## Docker / PostgreSQL
```bash
cp .env.example .env            # set POSTGRES_PASSWORD and BLOODLINE_SECRET_KEY
docker compose up --build       # API :8000, web :8080, PostgreSQL
docker compose exec api python -m app.seed
```

## SRS coverage
**Implemented:** AUTH-1..4 · INV-1..6 (donation recording requires an 'eligible' screening; single units with
collection/expiry dates, oldest issued first, expiry panel) · FCST-1..4 (moving-average baseline vs exponential smoothing vs
SARIMA(1,0,1)(1,0,1,7), one chronological one-step-ahead backtest, MAE + RMSE, lowest MAE selected) · RISK-1..3 (alerts stored,
de-duplicated, with history) · MATCH-1..5 (incl. optional radius) · REQ-1/2 · SCR-1 · NOTE-1 (in-app plus optional Web Push, sent only
to donors who pass the matching rules) · RPT-1 (CSV and browser print-to-PDF) · REG-1 (multi-bank stock/risk heatmap, bank map,
redistribution *suggestions* that always require human approval) · DON-1 · ADM-1/2 · Alembic migrations · CI + staging CD workflow.

**Also included:** Evaluation page (`/evaluation/report`: forecast MAE/RMSE per blood group, shortage-detection precision/recall/F1 on a chronological protocol, independent SRS rule check of donor matching and notification targeting, browser-measured response times) ·
Scenarios page (read-only what-if demand slider; demo-only simulate-shortage/restock, recorded as simulated) · login rate limiting (in memory: resets on restart and isn't shared across workers; behind a proxy all clients share its IP) ·
Cmd/Ctrl+K command palette.

**Deliberately not implemented:**
* **Prophet.** FR-FCST-2 asks for "Prophet *or* SARIMA"; SARIMA is in. Prophet needs a heavy Stan toolchain and can't be scored with the
  same frozen-parameter one-step-ahead protocol, so a side-by-side comparison would not be fair. `services/forecasting.py` is modular
  if you want to add it as another candidate.
* **Google Maps.** The regional view uses a dependency-free SVG; a maps API needs a key and billing account.
* **Server-side PDF.** PDF export uses the browser's print-to-PDF with a print stylesheet (no extra dependency).

**Needs your setup (untested here):** Web Push (VAPID keys + HTTPS or localhost), the staging deploy (needs a server and the secrets listed in
`.github/workflows/deploy-staging.yml`; without them it only publishes the image to GitHub Container Registry), PostgreSQL via Docker.

## Migrations
```bash
cd backend && alembic upgrade head          # new database
alembic stamp head                          # existing database already created by app.seed / create_all
alembic revision --autogenerate -m "describe change"   # future schema changes
```
`0001_baseline` builds the 1.0 schema with `create_all`; replace it with an explicit autogenerated baseline before your next model change (instructions are in the file).

## Changes made to the earlier prototype
* `/risk/{bank}` stored a new alert on every page load; it now de-duplicates and has `/risk/{bank}/history`.
* A screening outcome of "eligible" used to overwrite `last_donation_date`; it is now set only when a donation is recorded.
* Matching showed "999 days since last donation" for first-time donors; it now says "No donation on record".
* Forecast responses now include MAE/RMSE; matching returns `distance_km`.
* Synthetic demand data changed on every seed run because Python randomises `hash()` per process; it now uses a stable checksum, so seeded data is reproducible.
* The previous UI is kept as `frontend/legacy-index.html`.

---
## Earlier prototype notes (W6/W7)

Predictive blood shortage & smart donor matching platform.

This is the **first working prototype**, built directly on top of the W5
vertical slice (nothing from W5 was rewritten — inventory, demand
generation, forecasting, shortage-risk, and donor matching all work exactly
as before). W6 added the remaining role workflows, an integrated hospital
request → approval → inventory-issue flow, and a proper UI shell so the
whole thing reads as one coherent product rather than a handful of pages.

## 1. Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Seed demo data

```bash
python -m app.seed
```

This creates one blood bank, seeded inventory (some blood groups
deliberately low to demonstrate HIGH risk), 180 days of synthetic demand
history per blood group, 15 donor records, one hospital with three sample
blood requests (mixed statuses), one sample screening record, and one demo
account per role — see credentials below.

## 3. Run the backend

```bash
uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

## 4. Run the frontend

Still a single static HTML file, no build step (see `frontend/index.html`)
— deliberately kept off React for the prototype so there's zero toolchain
to break during a live demo. Swapping to React/Vite later only touches this
file; the API contract is unaffected either way.

```bash
cd ../frontend
python3 -m http.server 5500
```
Open http://localhost:5500

## 5. Demo credentials

All accounts use the password `bloodline123`.

| Role | Email |
|---|---|
| Blood Bank Manager | manager@bloodline.demo |
| Inventory Staff | inventory@bloodline.demo |
| Hospital Coordinator | hospital@bloodline.demo |
| Medical / Screening Staff | screening@bloodline.demo |
| System Admin | admin@bloodline.demo |
| Donor (×15) | donor1@bloodline.demo … donor15@bloodline.demo |

## 6. W7 demo sequence

1. Log in as **Manager** → Overview shows total stock, high-risk count,
   pending requests, and a critical-shortages panel with an inline
   "Find donors" action.
2. Open **Inventory** → current stock per blood group.
3. Open **Demand History** → pick a blood group, see the 180-day synthetic
   series (chart + table + summary stats), clearly labelled synthetic.
4. Open **Shortage Risk** → HIGH/MODERATE/LOW per group with the plain-
   English shortfall explanation, and "Find donors" on any at-risk group.
5. Open **Blood Requests** → see the pending queue.
6. Log out, log in as **Hospital Coordinator** → submit a new B+ request
   (urgent/emergency), see it appear with status `pending`.
7. Log out, log in as **Manager** → **Blood Requests** → **Approve** the new
   request. If stock covers it, inventory is auto-issued and status becomes
   `fulfilled`; watch the number actually drop.
8. Log out, log in as **Inventory Staff** → manually record a receipt/issue
   and watch the grid update immediately, with proper validation (no
   negative units, can't issue more than available).
9. Optionally also show:
   - **Reports** (manager) — received/issued/expired totals, risk summary,
     demand-vs-forecast table.
   - **Screening** (medical staff) — candidate donor worklist, record an
     eligible/deferred/rejected outcome.
   - **My Profile** (donor) — eligibility status, donation history,
     availability/consent toggle.
   - **Admin** — user counts by role, full user list.

## 7. What changed in the W7 polish pass (on top of W6)

**Real bug fixed:** "Find donors" from the Manager Overview page silently did
nothing useful — the results container was being dropped from the DOM by a
templating helper that only kept the first of two sibling elements it
built. Root cause fixed by rebuilding that section with the same
single-string `innerHTML` pattern the (working) Shortage Risk page already
used, and both pages now share one `findDonorsInto()` function so there's
one code path instead of two that can drift apart again.

**Screening workflow rebuilt:** "Screen" now opens a modal showing the
donor's blood group, availability, cooldown status, and last donation
before recording an outcome. Submitting reloads the whole candidate table
from the API (not just closes a form), so the new outcome and screening
date are visibly persisted without a manual refresh. Added a "Last
screened" column, backed by a new `last_screened_at` field.

**Login page redesigned:** subtitle added, demo credentials moved behind a
"For demonstration" toggle instead of being printed on the page by default,
per-account quick-fill buttons inside the toggle.

**Inventory Staff dashboard extended:** now shows a low-stock indicator on
tiles under 15 units, and a Recent Transactions feed (new endpoint,
`GET /inventory/transactions`) — without duplicating the manager's
forecast-based risk view.

**Reports page extended:** added Blood Group Distribution and Blood
Requests Summary sections (new `inventory_by_group` / `requests_summary`
fields on the existing endpoint).

**UI alignment/responsiveness:** sidebar is now sticky and full-height,
tables scroll horizontally on narrow screens instead of overflowing, badges
and long text no longer break card layouts, and a single `.shortage-row`
style is now shared everywhere a HIGH/MODERATE shortage row is rendered.

**Manager approve/reject** now show inline success/error messages in the
page instead of a browser `alert()` popup.

**New backend endpoint:** `GET /inventory/transactions` (recent stock
movements, newest first).

## 8. What changed in W6 — file by file

**Schema:** one additive column, `BloodRequest.notes` (nullable). Nothing
else in the 19-table schema changed shape.

**New backend routers** (all reuse the existing services — forecasting,
risk, donor matching — nothing was duplicated):
- `routers/hospital.py` — hospital coordinator creates/views own requests
- `routers/requests.py` — manager reviews pending requests; **approve**
  auto-issues inventory via the same transaction logic `inventory.py`
  already used, demonstrating the request → approval → inventory flow
  end-to-end
- `routers/screening.py` — candidate worklist + record screening outcome
- `routers/admin.py` — system-wide counts + user list
- `routers/donor.py` — donor's own profile, donation history, availability
- `routers/reports.py` — aggregates existing inventory transactions +
  reruns the existing forecast/risk functions per group

**Fixed:** `inventory.py` now rejects zero/negative transaction quantities
(the one genuine validation gap from W5).

**Frontend:** full restyle — sidebar navigation, card-based dashboards,
consistent badges (blood group / risk level / status), clean tables, and a
page per role — still one HTML file, still vanilla JS, still calling the
same API. No page was invented without a backing endpoint.

**Seed data:** added a hospital + hospital coordinator, an admin account, a
medical-staff account, three sample blood requests, and one sample
screening record, so no role's first login shows an empty page.

## 9. What's intentionally left for W8+ / second prototype

- Prophet/SARIMA forecasting (the proposal explicitly scopes this later —
  the current model is naive-baseline vs. exponential smoothing, honestly
  labelled as such in the API response)
- Targeted donor push notifications (schema exists — `DonorNotification` —
  unused until this phase)
- Regional multi-bank surplus/redistribution view
- Managed/production deployment, PostgreSQL migration, CI/CD hardening
- Fine-grained donor availability windows (`DonorAvailability` table exists,
  unused — donor availability is currently a simple on/off toggle)
- Saved/exported PDF reports (`Report` table exists, unused — the current
  Reports page is live-computed, not persisted)

## 10. Likely professor questions

**"Is this forecast really Prophet/SARIMA?"**
No — deliberately not yet. It's naive-baseline vs. exponential smoothing,
and the API always reports which one it picked and why (backtested MAE).
Prophet/SARIMA is explicit W8+ scope per the proposal; the forecasting
module is structured so swapping the model doesn't change the API contract.

**"Is the demand data real?"**
No, and the UI says so on every page that shows it — "Synthetic /
Simulated Demand Data" — because the prototype has no access to granular
real blood-bank consumption data. The generation method (baseline + weekly
pattern + seasonal effect + holiday bump + emergency spike + noise) is
documented in `services/synthetic_data.py` and explained in-app.

**"Does approving a request actually do anything, or is it just a status
flag?"**
It actually issues inventory — same `InventoryTransaction` mechanism the
Inventory Staff page uses — so the stock number visibly drops. If stock is
insufficient it stays pending with a note rather than silently failing.

**"Why is the frontend vanilla JS and not React, when the proposal says
React?"**
Speed and reliability for a first prototype: no build step to break during
a demo. The API is framework-agnostic — swapping in the React+Tailwind
frontend from the proposal is a frontend-only change later.

**"What decides donor eligibility — the system or a person?"**
A person. Screening records an outcome a human medical staff member
entered; BloodLine never auto-approves a donor. This is enforced at the
data-model level (`ScreeningRecord.performed_by_id` requires a `Staff`
row) not just a UI convention.

## 11. Swapping SQLite → PostgreSQL

```bash
export DATABASE_URL="postgresql+psycopg2://user:pass@localhost:5432/bloodline"
pip install psycopg2-binary
```
No model or route code changes needed.
