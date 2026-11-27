FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini .
COPY alembic ./alembic
COPY scripts ./scripts
COPY app ./app
ENV PYTHONUNBUFFERED=1 BLOODLINE_USE_MIGRATIONS=1
EXPOSE 8000
# Apply migrations; when BLOODLINE_FACULTY_DEMO=1, add the synthetic demo fixture (additive and safe to rerun,
# so the demo logins are always present after a deploy); then serve.
CMD ["sh", "-c", "alembic upgrade head && { [ \"$BLOODLINE_FACULTY_DEMO\" != 1 ] || python -m app.bootstrap_demo || echo 'Demo fixture provisioning failed; continuing without it.'; } && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
