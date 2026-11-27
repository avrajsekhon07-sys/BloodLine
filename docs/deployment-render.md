# Render deployment runbook

This runbook deploys the existing BloodLine static frontend and FastAPI API as separate Render services. The database can be hosted by Neon; a Render-managed PostgreSQL database is optional. It does not replace the GitHub Pages documentation workflow. Deploy only after reviewing the source and setting private secrets in Render.

## Recommended services

| Service | Render type | Repository settings | Persistent data |
|---|---|---|---|
| Frontend | Static Site | Root directory `code/frontend`; build command `python build_static.py`; publish directory `dist` | None |
| API | Docker Web Service | Root directory `code/backend`; Dockerfile path `Dockerfile`; health check `/health` | Managed database only |
| Database | PostgreSQL (Neon or another provider) | Set the provider's PostgreSQL URL as `DATABASE_URL`; Neon requires TLS | Provider-managed database |

The frontend does not run inside FastAPI. Its static build injects the public API origin into `config.js`; no API secret is placed in the frontend bundle. The API container applies Alembic migrations at startup and binds Uvicorn to `0.0.0.0:$PORT` (fallback `8000` for local Docker).

## Create and configure services

1. Create a PostgreSQL database with your chosen provider. For Neon, copy its direct (non-pooler) PostgreSQL URL from the Neon Console and keep `sslmode=require` (and any supplied `channel_binding=require`) in the query string. Neon URLs in the standard `postgresql://user:password@host/database?sslmode=require` form are supported by SQLAlchemy and the installed `psycopg2-binary` driver; the same URL is used by the app and Alembic. Store it only in Render's private `DATABASE_URL` environment variable. A Render-managed database is optional; if you choose one, use its internal URL and select a plan whose persistence and retention meet your needs.
2. Create a Docker Web Service connected to this repository, branch `master`, root directory `code/backend`, Dockerfile `Dockerfile`, health check path `/health`. Do not set a separate start command; the image command runs migrations then Uvicorn. Render supplies `PORT`.
3. Add these API environment variables in Render (not in Git):

   | Name | Value |
   |---|---|
   | `DATABASE_URL` | Secret PostgreSQL URL from Neon or another provider (for Neon, use the direct URL with TLS enabled) |
   | `BLOODLINE_ENV` | `production` |
   | `BLOODLINE_USE_MIGRATIONS` | `1` |
   | `BLOODLINE_SECRET_KEY` | Unique random secret, generated privately (for example `python -c 'import secrets; print(secrets.token_urlsafe(48))'`) |
   | `BLOODLINE_DEMO_LOGIN` | `0` |
   | `BLOODLINE_DEMO_TOOLS` | `0` |
   | `BLOODLINE_FACULTY_DEMO` | `1` only when enabling the synthetic faculty demo |
   | `ALLOWED_ORIGINS` | Exact HTTPS origin of the Render static site, with no path or trailing slash |

   Optional: set `BLOODLINE_SARIMA=0` if you prefer to disable SARIMA. VAPID values are needed only if you plan to enable web push. Do not set or reuse the development JWT secret.
4. Create a Render Static Site from the same repo and branch. Set root directory `code/frontend`, build command `python build_static.py`, and publish directory `dist`. Set `BLOODLINE_API_URL` to the API's exact public HTTPS origin (for example `https://bloodline-api.onrender.com`, no path, query, or credentials). The build rejects invalid, local, credential-bearing, and non-HTTPS URLs. Set `BLOODLINE_FACULTY_DEMO=1` in the Static Site build environment only when enabling the original synthetic account shortcuts; otherwise use `0`.
5. Once the static site exists, copy its exact origin (scheme + host, no path) into API `ALLOWED_ORIGINS`. Save both services and wait for their builds.
6. Confirm `https://<api-host>/health`, then `https://<api-host>/docs`; check the static site's browser network panel for successful API calls and CORS responses.

## One-time safe database bootstrap

The image's startup command runs Alembic migrations only; migrations intentionally do not create an administrator or sample records. After the API is running and migrations have completed:

1. Run bootstrap from a trusted machine with the backend dependencies installed and network access to the database, setting `DATABASE_URL`, `BLOODLINE_BOOTSTRAP_ADMIN_EMAIL`, and a unique `BLOODLINE_BOOTSTRAP_ADMIN_PASSWORD` (16-72 UTF-8 bytes) in that machine's private environment. Do not put the password in a command argument or repository file. Render Free Web Services do not provide a Shell, so this local one-time step also works when using Render Free compute.
2. From `code/backend`, run `python -m app.bootstrap`. It additively creates missing roles, the initial system administrator if that email does not already exist, three explicitly synthetic planning regions, stock snapshots, and 180 days of synthetic demand per region and blood group. It creates no donors or patients, never changes existing stock/accounts/history, and can be rerun safely.
3. Unset `BLOODLINE_BOOTSTRAP_ADMIN_PASSWORD` from the trusted machine's environment as soon as the command completes; do not add it to the Render service environment. Keep the admin email if useful for audit; rotate the initial password through normal account administration if required.
4. Sign in as the administrator, create individual staff accounts, and verify role-specific navigation and dashboards. Donors can register through the public donor registration form.

## Optional original faculty demo fixture

The original demo picker is separate from the real administrator login. To enable it, set `BLOODLINE_FACULTY_DEMO=1` on both the API and Static Site, keep `BLOODLINE_DEMO_LOGIN=0` and `BLOODLINE_DEMO_TOOLS=0`, and deploy the additive demo-scope migration. After reviewing `0002_demo_scope.py` and `app.bootstrap_demo`, run `python -m app.bootstrap_demo` once with the private production `DATABASE_URL`. This creates only the original five non-donor accounts and fifteen synthetic donors, plus synthetic demo banks, inventory, demand, requests, and screening fixtures. It refuses to take over any reserved email already belonging to a non-demo account and never changes the real administrator. Reruns add only missing records. The historical shared demo password and unauthenticated direct login are not restored; the visible shortcuts use a rate-limited short-lived demo token. Demo Admin is read-only for demo records; all other demo activity is scoped to synthetic records. Demo outreach sends push notifications to browsers that enabled them on a demo donor account. Do not run the destructive `app.seed` against this database.

Never run `python -m app.seed` against a production database: it drops mapped tables. It now refuses `BLOODLINE_ENV=production`, non-SQLite database URLs, and runs without explicit `BLOODLINE_ALLOW_DESTRUCTIVE_SEED=1`; bootstrap does not call that script. Do not load real donor or patient information into this academic prototype.

## Persistence and operations

Keep the API container filesystem out of persistent data storage. Do not point production at SQLite or a container-local file. Configure backups/retention available on the selected database plan. `DATABASE_URL` should be kept private. Render Free Web Services can make outbound PostgreSQL connections to an external provider such as Neon; this uses public internet bandwidth and is subject to Render's free-service limits. It does not require a Render Postgres service. Render Free Web Services sleep after inactivity and are intended for preview/hobby use, not durable production workloads.

The frontend origin must match `ALLOWED_ORIGINS` exactly. If you add a custom domain or preview frontend, add only its exact HTTPS origin to that variable and rebuild the static frontend if its API URL changes. Login throttling is process-local, so it is not shared across API instances; use a single API instance for this prototype and consider shared rate limiting before scaling.

## Important limitations

BloodLine uses synthetic demand, has no operational clinical validation, and should not be used for actual allocation or medical decisions. Render service pricing and free-tier limits can change; check the provider's current pricing and persistence terms before selecting a plan.
