"""End-to-end API tests against a freshly seeded throwaway database."""
import os

import pytest
from fastapi.testclient import TestClient

from app import seed
from app.main import app

PW = os.environ["BLOODLINE_TEST_PASSWORD"]


@pytest.fixture(scope="module")
def client():
    seed.run()  # drops/creates tables in the temp DB and loads demo data
    return TestClient(app)


def login(client, email):
    r = client.post("/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_login_rejects_bad_password(client):
    assert client.post("/auth/login", json={"email": "manager@bloodline.demo", "password": "nope"}).status_code == 401


def test_requires_token(client):
    assert client.get("/inventory").status_code == 401


def test_rbac(client):
    donor = login(client, "donor1@bloodline.demo")
    assert client.get("/admin/users", headers=donor).status_code == 403
    assert client.get("/inventory", headers=donor).status_code == 403
    hospital = login(client, "hospital@bloodline.demo")
    assert client.get("/requests", headers=hospital).status_code == 403


def test_stock_never_negative_and_rejects_bad_quantity(client):
    h = login(client, "inventory@bloodline.demo")
    inv = client.get("/inventory", headers=h).json()[0]
    base = {"blood_bank_id": inv["blood_bank_id"], "blood_group": inv["blood_group"], "component": inv["component"]}
    assert client.post("/inventory/transaction", headers=h, json={**base, "txn_type": "issue", "quantity_units": 0}).status_code in (400, 422)
    assert client.post("/inventory/transaction", headers=h, json={**base, "txn_type": "issue", "quantity_units": 10**6}).status_code == 400


def test_risk_overview_and_no_alert_spam(client):
    m = login(client, "manager@bloodline.demo")
    bank = client.get("/inventory", headers=m).json()[0]["blood_bank_id"]
    client.get(f"/risk/{bank}", headers=m)
    n1 = len(client.get(f"/risk/{bank}/history", headers=m).json())
    client.get(f"/risk/{bank}", headers=m)
    n2 = len(client.get(f"/risk/{bank}/history", headers=m).json())
    assert n1 == n2  # repeated page loads must not store duplicate alerts


def test_donor_match_respects_rules(client):
    m = login(client, "manager@bloodline.demo")
    for d in client.get("/donors/match/O-", headers=m).json():
        assert d["is_available"] and d["notification_consent"]


def test_outreach_only_reaches_matched_donors(client):
    m = login(client, "manager@bloodline.demo")
    matched = {d["donor_id"] for d in client.get("/donors/match/B+", headers=m).json()}
    res = client.post("/notifications/outreach", headers=m, json={"blood_group": "B+"}).json()
    assert res["matched"] == len(matched) and res["notified"] <= res["matched"]


def test_donation_requires_eligible_screening_then_updates_stock(client):
    inv_h = login(client, "inventory@bloodline.demo")
    scr_h = login(client, "screening@bloodline.demo")
    cand = next(c for c in client.get("/screening/candidates", headers=scr_h).json() if c["cooldown_cleared"] and c["last_screening_outcome"] is None)
    body = {"donor_id": cand["donor_id"], "units_collected": 1}
    assert client.post("/donations", headers=inv_h, json=body).status_code == 400  # not screened yet
    assert client.post("/screening", headers=scr_h, json={"donor_id": cand["donor_id"], "outcome": "eligible"}).status_code in (200, 201)
    # The seed contains three banks; donation recording defaults to the staff
    # member's assigned bank, so compare stock within that bank only.
    bank_id = next(
        b["id"] for b in client.get("/regional/banks", headers=inv_h).json()
        if b["name"] == "Patiala Central Blood Bank"
    )
    before = {
        i["blood_group"]: i["quantity_units"]
        for i in client.get(f"/inventory?blood_bank_id={bank_id}", headers=inv_h).json()
        if i["component"] == "whole_blood"
    }
    r = client.post("/donations", headers=inv_h, json=body)
    assert r.status_code == 201, r.text
    assert r.json()["new_stock"] == before.get(cand["blood_group"], 0) + 1
    assert client.post("/donations", headers=inv_h, json=body).status_code == 400  # cooldown now applies


def test_request_flow_and_insufficient_stock_stays_pending(client):
    h, m = login(client, "hospital@bloodline.demo"), login(client, "manager@bloodline.demo")
    r = client.post("/hospital/requests", headers=h, json={"blood_group": "O-", "quantity_units": 10**5, "urgency": "urgent"}).json()
    out = client.post(f"/requests/{r['id']}/approve", headers=m).json()
    assert out["status"] == "pending" and "insufficient" in (out["notes"] or "").lower()


def test_admin_user_management_and_audit(client):
    a = login(client, "admin@bloodline.demo")
    u = client.post("/admin/users", headers=a, json={"full_name": "New Staff", "email": "new.staff@bloodline.demo", "password": "longenough1", "role": "inventory_staff"})
    assert u.status_code == 201, u.text
    assert client.patch(f"/admin/users/{u.json()['id']}", headers=a, json={"is_active": False}).status_code == 200
    assert client.post("/auth/login", json={"email": "new.staff@bloodline.demo", "password": "longenough1"}).status_code == 403
    actions = {e["action"] for e in client.get("/admin/audit", headers=a).json()}
    assert {"login", "user_created", "user_updated"} <= actions


def test_donor_self_registration(client):
    r = client.post("/auth/register-donor", json={"full_name": "Self Reg", "email": "selfreg@example.com", "password": "longenough1", "blood_group": "A+", "notification_consent": True})
    assert r.status_code == 201 and r.json()["role"] == "donor"
    assert client.post("/auth/register-donor", json={"full_name": "x", "email": "selfreg@example.com", "password": "longenough1", "blood_group": "A+"}).status_code == 400


# ---------------------------------------------------------------- added features
def test_demo_accounts_lists_all_donors_and_can_be_disabled(client, monkeypatch):
    rows = client.get("/auth/demo-accounts").json()
    donors = [r for r in rows if r["role"] == "donor"]
    assert len(donors) == 15 and donors[0]["email"] == "donor1@bloodline.demo" and donors[0]["blood_group"]
    assert "hashed_password" not in rows[0]
    monkeypatch.setenv("BLOODLINE_DEMO_LOGIN", "0")
    assert client.get("/auth/demo-accounts").status_code == 404


def test_auth_me_returns_bank_for_staff(client):
    me = client.get("/auth/me", headers=login(client, "inventory@bloodline.demo")).json()
    assert me["role"] == "inventory_staff" and me["blood_bank_id"]


def test_regional_overview_and_suggestions_are_manager_only(client):
    m = login(client, "manager@bloodline.demo")
    ov = client.get("/regional/overview", headers=m).json()
    assert len(ov["banks"]) >= 3 and all("groups" in b for b in ov["banks"])
    sug = client.get("/regional/redistribution", headers=m).json()
    assert "authorised" in sug["note"] and all(s["requires_human_approval"] for s in sug["suggestions"])
    assert client.get("/regional/overview", headers=login(client, "inventory@bloodline.demo")).status_code == 403


def test_expiring_units_listed_and_receipt_creates_tracked_units(client):
    h = login(client, "inventory@bloodline.demo")
    bank = client.get("/auth/me", headers=h).json()["blood_bank_id"]
    rows = client.get(f"/units/expiring?blood_bank_id={bank}&days=60", headers=h).json()
    assert rows and rows[0]["days_left"] <= 60
    inv = client.get(f"/inventory?blood_bank_id={bank}", headers=h).json()[0]
    body = {"blood_bank_id": bank, "blood_group": inv["blood_group"], "component": inv["component"], "txn_type": "receipt", "quantity_units": 2}
    assert client.post("/inventory/transaction", headers=h, json=body).status_code == 200
    after = client.get(f"/units/expiring?blood_bank_id={bank}&days=60", headers=h).json()
    assert sum(r["units"] for r in after) >= sum(r["units"] for r in rows) + 2


def test_expire_overdue_requires_overdue_units(client):
    h = login(client, "inventory@bloodline.demo")
    assert client.post("/units/expire-overdue", headers=h).status_code == 400  # seed has none overdue
    assert client.post("/units/expire-overdue", headers=login(client, "manager@bloodline.demo")).status_code == 403


def test_push_not_configured_and_subscription_roundtrip(client, monkeypatch):
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    d = login(client, "donor2@bloodline.demo")
    assert client.get("/push/public-key").status_code == 503
    sub = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "k", "auth": "a"}}
    assert client.post("/push/subscribe", headers=d, json=sub).status_code == 201
    assert client.post("/push/subscribe", headers=d, json=sub).status_code == 201   # idempotent
    assert client.post("/push/unsubscribe", headers=d, json=sub).json() == {"subscribed": False}
    assert client.post("/push/subscribe", headers=login(client, "manager@bloodline.demo"), json=sub).status_code == 403


def test_outreach_reports_push_count(client):
    m = login(client, "manager@bloodline.demo")
    assert client.post("/notifications/outreach", headers=m, json={"blood_group": "O-", "message": "push test"}).json()["pushed"] == 0


# ---------------------------------------------------------------- evaluation, scenarios, rate limiting
def test_evaluation_report_shape_and_rbac(client):
    m = login(client, "manager@bloodline.demo")
    r = client.get("/evaluation/report", headers=m).json()
    assert r["forecast"]["rows"] and r["shortage_detection"]["cases"] > 0
    assert r["matching"]["passed"] is True and "synthetic" in r["data_note"].lower()
    assert client.get("/evaluation/report", headers=login(client, "inventory@bloodline.demo")).status_code == 403


def test_whatif_more_demand_never_lowers_shortfall(client):
    m = login(client, "manager@bloodline.demo")
    base = {g["blood_group"]: g["shortfall"] for g in client.get("/demo/whatif?demand_change_pct=0", headers=m).json()["groups"]}
    more = {g["blood_group"]: g["shortfall"] for g in client.get("/demo/whatif?demand_change_pct=50", headers=m).json()["groups"]}
    assert base and all(more[g] >= base[g] for g in base)


def test_shortage_scenario_creates_high_risk_then_restock_and_can_be_disabled(client, monkeypatch):
    m = login(client, "manager@bloodline.demo")
    bank = client.get("/auth/me", headers=m).json().get("blood_bank_id") or client.get("/regional/banks", headers=m).json()[0]["id"]
    r = client.post("/demo/scenario", headers=m, json={"blood_group": "A+", "action": "shortage", "blood_bank_id": bank}).json()
    assert r["new_units"] == 3
    risk = {x["blood_group"]: x["risk_level"] for x in client.get(f"/risk/{bank}", headers=m).json()}
    assert risk["A+"] == "HIGH"
    assert client.post("/demo/scenario", headers=m, json={"blood_group": "A+", "action": "restock", "blood_bank_id": bank}).json()["new_units"] == 60
    monkeypatch.setenv("BLOODLINE_DEMO_TOOLS", "0")
    assert client.post("/demo/scenario", headers=m, json={"blood_group": "A+", "action": "shortage"}).status_code == 404
    assert client.post("/demo/scenario", headers=login(client, "inventory@bloodline.demo"), json={"blood_group": "A+", "action": "shortage"}).status_code == 403


def test_login_rate_limit_returns_429_then_recovers_for_good_credentials(client):
    from app.services import ratelimit
    ratelimit.limiter.clear()
    for _ in range(5):
        assert client.post("/auth/login", json={"email": "rate.test@bloodline.demo", "password": "wrong"}).status_code == 401
    r = client.post("/auth/login", json={"email": "rate.test@bloodline.demo", "password": "wrong"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    assert client.post("/auth/login", json={"email": "manager@bloodline.demo", "password": PW}).status_code == 200  # other accounts unaffected
    ratelimit.limiter.clear()


def test_production_disables_all_demo_endpoints(client, monkeypatch):
    manager = login(client, "manager@bloodline.demo")
    monkeypatch.setenv("BLOODLINE_ENV", "production")
    monkeypatch.setenv("BLOODLINE_DEMO_TOOLS", "1")
    assert client.get("/demo/status", headers=manager).status_code == 404
    assert client.get("/demo/whatif", headers=manager).status_code == 404
    assert client.post("/demo/scenario", headers=manager, json={"blood_group": "A+", "action": "shortage"}).status_code == 404
    monkeypatch.setenv("BLOODLINE_DEMO_LOGIN", "1")
    assert client.get("/auth/demo-accounts").status_code == 404


def test_production_cors_requires_exact_https_origins(monkeypatch):
    from app.main import configured_origins

    monkeypatch.setenv("BLOODLINE_ENV", "production")
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS"):
        configured_origins()
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")
    with pytest.raises(RuntimeError, match="Wildcard"):
        configured_origins()
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://bloodline.example")
    assert configured_origins() == ["https://bloodline.example"]
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://bloodline.example/path")
    with pytest.raises(RuntimeError, match="exact HTTPS"):
        configured_origins()
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://bloodline.example/")
    with pytest.raises(RuntimeError, match="exact HTTPS"):
        configured_origins()


def test_safe_bootstrap_is_idempotent_and_additive(client):
    from app import bootstrap, models
    from app.database import SessionLocal

    db = SessionLocal()
    bank_count = db.query(models.BloodBank).count()
    donor_count = db.query(models.Donor).count()
    existing_stock = db.query(models.Inventory).filter_by(quantity_units=20).first()
    existing_stock_id = existing_stock.id
    db.close()

    first = bootstrap.bootstrap_database("initial-admin@example.com", "a-strong-bootstrap-password")
    second = bootstrap.bootstrap_database("initial-admin@example.com", "a-different-strong-password")
    assert first["admin"] is True and second["admin"] is False
    assert second["banks"] == second["inventory"] == second["demand"] == second["roles"] == 0

    db = SessionLocal()
    assert db.query(models.BloodBank).count() == bank_count + len(bootstrap.SYNTHETIC_BANKS)
    assert db.query(models.Inventory).filter_by(id=existing_stock_id).first().quantity_units == 20
    admin = db.query(models.UserAccount).filter_by(email="initial-admin@example.com").one()
    assert admin.role.name == models.RoleName.SYSTEM_ADMIN
    synthetic_banks = db.query(models.BloodBank).filter(models.BloodBank.name.like("BloodLine Synthetic Region %")).all()
    assert all(db.query(models.DemandHistory).filter_by(blood_bank_id=b.id, is_synthetic=True).count() >= 8 * 180 for b in synthetic_banks)
    assert db.query(models.Donor).count() == donor_count  # bootstrap did not add synthetic donor identities
    synthetic_bank_id = synthetic_banks[0].id
    db.close()

    admin_login = client.post("/auth/login", json={"email": "initial-admin@example.com", "password": "a-strong-bootstrap-password"})
    assert admin_login.status_code == 200
    admin_headers = {"Authorization": "Bearer " + admin_login.json()["access_token"]}
    assert client.get("/admin/users", headers=admin_headers).status_code == 200
    assert client.get("/inventory?blood_bank_id=" + synthetic_bank_id, headers=admin_headers).status_code == 200
    assert client.get("/risk/" + synthetic_bank_id, headers=admin_headers).status_code == 200
    assert client.get("/forecast/" + synthetic_bank_id + "/A+", headers=admin_headers).status_code == 200
    assert client.get("/regional/overview", headers=admin_headers).status_code == 200


def test_production_demo_accounts_are_isolated_from_real_admin_and_inventory(client, monkeypatch):
    from app import models
    from app.database import SessionLocal
    from app.services import ratelimit

    db = SessionLocal()
    fixture_emails = {
        "manager@bloodline.demo", "inventory@bloodline.demo", "screening@bloodline.demo",
        "hospital@bloodline.demo", "admin@bloodline.demo",
        *(f"donor{i}@bloodline.demo" for i in range(1, 16)),
    }
    for user in db.query(models.UserAccount).filter(models.UserAccount.email.in_(fixture_emails)).all():
        user.is_demo = True
    for bank in db.query(models.BloodBank).filter(models.BloodBank.name.like("%Blood Bank%" )).all():
        if bank.name == "Patiala Central Blood Bank" or "(synthetic)" in bank.name:
            bank.is_demo = True
    hospital = db.query(models.Hospital).filter_by(name="Rajindra Government Hospital").one()
    hospital.is_demo = True
    real_bank = models.BloodBank(
        name="Scope Isolation Fixture (test)", address="Synthetic test location", is_demo=False,
    )
    db.add(real_bank)
    db.flush()
    real_inventory = models.Inventory(
        blood_bank_id=real_bank.id, blood_group=models.BloodGroup.A_POS,
        component="whole_blood", quantity_units=57,
    )
    db.add(real_inventory)
    real_admin_role = db.query(models.Role).filter_by(name=models.RoleName.SYSTEM_ADMIN).one()
    from app import auth
    real_admin_user = models.UserAccount(
        email="real-admin-isolation-test@example.invalid", full_name="Real Admin Test Fixture",
        hashed_password=auth.hash_password("test-only-strong-password"), role_id=real_admin_role.id,
        is_active=True, is_demo=False,
    )
    db.add(real_admin_user)
    db.commit()
    real_admin_id = real_admin_user.id
    demo_bank = db.query(models.BloodBank).filter_by(name="Patiala Central Blood Bank", is_demo=True).one()
    real_before = db.query(models.Inventory).filter_by(blood_bank_id=real_bank.id, blood_group=models.BloodGroup.A_POS).one().quantity_units
    demo_donor_ids = {d.id for d in db.query(models.Donor).join(models.UserAccount).filter(models.UserAccount.is_demo.is_(True)).all()}
    db.close()

    monkeypatch.setenv("BLOODLINE_ENV", "production")
    monkeypatch.setenv("BLOODLINE_FACULTY_DEMO", "1")
    monkeypatch.setenv("BLOODLINE_DEMO_LOGIN", "0")
    monkeypatch.setenv("BLOODLINE_DEMO_TOOLS", "0")
    ratelimit.limiter.clear()

    catalog = client.get("/auth/demo-accounts")
    assert catalog.status_code == 200
    assert len([u for u in catalog.json() if u["role"] != "donor"]) == 5
    assert len([u for u in catalog.json() if u["role"] == "donor"]) == 15
    demo_admin = client.post("/auth/demo-login", json={"email": "admin@bloodline.demo"})
    demo_manager = client.post("/auth/demo-login", json={"email": "manager@bloodline.demo"})
    assert demo_admin.status_code == demo_manager.status_code == 200
    da = {"Authorization": "Bearer " + demo_admin.json()["access_token"]}
    dm = {"Authorization": "Bearer " + demo_manager.json()["access_token"]}

    assert client.post("/admin/users", headers=da, json={
        "full_name": "Not allowed", "email": "blocked@example.invalid", "password": "longenough1", "role": "inventory_staff",
    }).status_code == 403
    assert client.get("/admin/summary", headers=da).json()["total_users"] == 20
    assert len(client.get("/admin/users", headers=da).json()) == 20

    demo_banks = client.get("/regional/banks", headers=dm).json()
    real_admin_token = auth.create_access_token({"sub": real_admin_id, "demo": False})
    ra = {"Authorization": "Bearer " + real_admin_token}
    real_banks = client.get("/regional/banks", headers=ra).json()
    assert {b["id"] for b in demo_banks} == {demo_bank.id} | {
        b["id"] for b in demo_banks if "(synthetic)" in b["name"]
    }
    assert all(not b["name"].startswith("Demo Blood Bank") and b["id"] != demo_bank.id for b in real_banks)
    assert all(u["email"] not in fixture_emails for u in client.get("/admin/users", headers=ra).json())
    assert client.get(f"/inventory?blood_bank_id={real_bank.id}", headers=dm).json() == []

    match_rows = client.get("/donors/match/O-", headers=dm).json()
    assert all(row["donor_id"] in demo_donor_ids for row in match_rows)
    before_demo = client.get(f"/inventory?blood_bank_id={demo_bank.id}", headers=dm).json()
    assert client.post("/demo/scenario", headers=dm, json={
        "blood_group": "A+", "action": "shortage", "blood_bank_id": demo_bank.id,
    }).status_code == 200
    after_demo = client.get(f"/inventory?blood_bank_id={demo_bank.id}", headers=dm).json()
    assert next(i["quantity_units"] for i in after_demo if i["blood_group"] == "A+") == 3
    assert any(i["quantity_units"] != 3 for i in before_demo if i["blood_group"] == "A+")

    db = SessionLocal()
    assert db.query(models.Inventory).filter_by(blood_bank_id=real_bank.id, blood_group=models.BloodGroup.A_POS).one().quantity_units == real_before
    db.close()
    assert client.post("/auth/demo-login", json={"email": "initial-admin@example.com"}).status_code == 401


def test_destructive_seed_refuses_production_and_non_sqlite(client, monkeypatch):
    from app import models, seed
    from app.database import SessionLocal

    db = SessionLocal()
    before = db.query(models.BloodBank).count()
    db.close()
    monkeypatch.setenv("BLOODLINE_ALLOW_DESTRUCTIVE_SEED", "1")
    monkeypatch.setenv("BLOODLINE_ENV", "production")
    with pytest.raises(RuntimeError, match="disabled in production"):
        seed.run()
    monkeypatch.setenv("BLOODLINE_ENV", "development")
    monkeypatch.setattr(seed, "DATABASE_URL", "postgresql://remote.example/database")
    with pytest.raises(RuntimeError, match="local SQLite"):
        seed.run()
    db = SessionLocal()
    assert db.query(models.BloodBank).count() == before
    db.close()
