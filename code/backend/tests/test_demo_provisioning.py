import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import auth, bootstrap_demo, models
from app.database import Base


def _isolated_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'demo-fixtures.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(bootstrap_demo, "SessionLocal", sessions)
    db = sessions()
    roles = {r.value: models.Role(name=r) for r in models.RoleName}
    db.add_all(roles.values())
    db.flush()
    # An independently provisioned real administrator must survive demo setup.
    real_admin = models.UserAccount(
        email="actual.admin@example.com", hashed_password=auth.hash_password("not-a-demo-password"),
        full_name="Actual Administrator", role_id=roles[models.RoleName.SYSTEM_ADMIN.value].id,
    )
    db.add(real_admin)
    db.commit()
    original_hash, original_id = real_admin.hashed_password, real_admin.id
    db.close()
    monkeypatch.setenv("BLOODLINE_FACULTY_DEMO", "1")
    return engine, sessions, original_hash, original_id


def test_demo_bootstrap_adds_exact_synthetic_fixtures_and_is_idempotent(tmp_path, monkeypatch):
    engine, sessions, original_hash, original_id = _isolated_db(tmp_path, monkeypatch)
    first = bootstrap_demo.bootstrap_demo_database(today=dt.date(2026, 1, 1))
    second = bootstrap_demo.bootstrap_demo_database(today=dt.date(2026, 1, 1))
    assert first == {"users": 20, "donors": 15, "banks": 3, "inventory": 24, "demand": 4320, "requests": 3}
    assert second == {"users": 0, "donors": 0, "banks": 0, "inventory": 0, "demand": 0, "requests": 0}

    db = sessions()
    demo_users = db.query(models.UserAccount).filter(models.UserAccount.is_demo.is_(True)).all()
    assert len(demo_users) == 20
    assert len([u for u in demo_users if u.role.name != models.RoleName.DONOR]) == 5
    assert len([u for u in demo_users if u.role.name == models.RoleName.DONOR]) == 15
    assert {u.email for u in demo_users if u.role.name == models.RoleName.DONOR} == {
        f"donor{i}@bloodline.demo" for i in range(1, 16)
    }
    assert {u.email for u in demo_users if u.role.name == models.RoleName.SYSTEM_ADMIN} == {"admin@bloodline.demo"}
    assert all(u.hashed_password != "not-a-demo-password" for u in demo_users)
    actual_admin = db.query(models.UserAccount).filter_by(id=original_id).one()
    assert actual_admin.hashed_password == original_hash and not actual_admin.is_demo
    assert all(b.is_demo for b in db.query(models.BloodBank).all())
    assert all(h.is_demo for h in db.query(models.Hospital).all())
    assert db.query(models.DemandHistory).filter(models.DemandHistory.is_synthetic.is_(False)).count() == 0
    db.close()
    engine.dispose()


def test_demo_bootstrap_refuses_reserved_real_account_without_partial_rows(tmp_path, monkeypatch):
    engine, sessions, original_hash, original_id = _isolated_db(tmp_path, monkeypatch)
    db = sessions()
    real_role = db.query(models.Role).filter_by(name=models.RoleName.BLOOD_BANK_MANAGER).one()
    reserved = models.UserAccount(
        email="manager@bloodline.demo", hashed_password=original_hash,
        full_name="Reserved real account", role_id=real_role.id,
    )
    db.add(reserved)
    db.commit()
    reserved_id = reserved.id
    db.close()

    try:
        bootstrap_demo.bootstrap_demo_database(today=dt.date(2026, 1, 1))
        raise AssertionError("provisioner should refuse to claim a real reserved account")
    except RuntimeError as exc:
        assert "Refusing to claim" in str(exc)

    db = sessions()
    assert db.query(models.BloodBank).count() == 0
    assert db.query(models.Hospital).count() == 0
    assert db.query(models.UserAccount).count() == 2
    assert db.query(models.UserAccount).filter_by(id=reserved_id).one().full_name == "Reserved real account"
    assert db.query(models.UserAccount).filter_by(id=original_id).one().hashed_password == original_hash
    db.close()
    engine.dispose()
