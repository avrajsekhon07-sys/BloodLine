# BloodLine — First Prototype (W6/W7)

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
