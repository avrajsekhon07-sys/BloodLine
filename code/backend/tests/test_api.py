"""End-to-end API tests against a freshly seeded throwaway database."""
import pytest
from fastapi.testclient import TestClient

from app import seed
from app.main import app

PW = "bloodline123"


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
    before = {i["blood_group"]: i["quantity_units"] for i in client.get("/inventory", headers=inv_h).json() if i["component"] == "whole_blood"}
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
