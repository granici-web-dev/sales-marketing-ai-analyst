"""INFRA-02 schema inspection tests.

Every tenant-scoped table must carry:
  - `tenant_id`, NOT NULL — the structural half of CLAUDE.md Core Principle #3
  - `created_at` / `updated_at` as TIMESTAMPTZ, never naive TIMESTAMP

Read from the SQLAlchemy model definitions. No database is touched.

## Why this file was rewritten (2026-08-25)

It was a Wave 0 stub and had never run. Two things kept it dead:

  1. It imported `TIMESTAMPTZ` from `sqlalchemy.dialects.postgresql`, where no
     such name exists — the answer is written down two lines above the real
     definition in `app/db/base.py`: "the 'TIMESTAMPTZ' SQL alias is not a
     Python class in the dialect module". The ImportError fired at collection,
     so pytest reported an error for the whole module on every single run.
  2. Even collected, every test was disabled by a module-level
     `pytest.mark.skip(reason="Stubs — implementation pending")`, and each body
     began by tolerating a missing import. All of it has existed since Phase 1.

It also claimed to verify "all tenant-scoped tables" while inspecting exactly
one: `users`. Thirteen models now inherit the mixin, and a fourteenth added
without `tenant_id` would have gone unnoticed.

So the checks below sweep the registry instead of naming tables. A new model is
covered the moment it is imported in `app/models/__init__.py` — which it must
be anyway, or Alembic's autogenerate will not see it either.
"""
from __future__ import annotations

from sqlalchemy import DateTime

# Importing the package registers every mapped class on Base.registry.
# Without it this file would test whatever happened to be imported first.
import app.models  # noqa: F401
from app.db.base import Base, TenantScopedMixin
from app.models.tenant import Tenant


def _mapped_classes() -> list[type]:
    """Every model registered on the declarative base."""
    return [m.class_ for m in Base.registry.mappers]


def _tenant_scoped() -> list[type]:
    return [c for c in _mapped_classes() if issubclass(c, TenantScopedMixin)]


def test_registry_is_populated() -> None:
    """Guard the guard.

    Every assertion below iterates a list. An empty registry would make all of
    them pass while checking nothing — the failure mode that let the previous
    version of this file sit green-by-absence for months.
    """
    assert len(_mapped_classes()) >= 10, (
        f"expected the full model registry, found {len(_mapped_classes())} classes — "
        "is app/models/__init__.py still importing every model?"
    )
    assert len(_tenant_scoped()) >= 10, (
        f"only {len(_tenant_scoped())} tenant-scoped models found — suspiciously few"
    )


def test_tenant_scoped_tables_have_not_null_tenant_id() -> None:
    """INFRA-02: tenant_id exists and is NOT NULL on every scoped table."""
    missing: list[str] = []
    nullable: list[str] = []

    for model in _tenant_scoped():
        columns = model.__table__.columns
        if "tenant_id" not in columns:
            missing.append(model.__tablename__)
        elif columns["tenant_id"].nullable is not False:
            nullable.append(model.__tablename__)

    assert not missing, (
        f"tables inheriting TenantScopedMixin but with no tenant_id column: {missing}"
    )
    assert not nullable, (
        f"tenant_id must be NOT NULL — a nullable one lets a row escape every "
        f"tenant filter silently: {nullable}"
    )


def test_tenant_scoped_tables_use_timestamptz() -> None:
    """INFRA-02: created_at / updated_at store a timezone.

    A naive TIMESTAMP is read back in whatever timezone the session happens to
    carry. Every metric in this product is bucketed by day in Europe/Bucharest,
    so an hour of drift moves rows across day boundaries — and the report is
    wrong in a way nothing raises an error about.
    """
    offenders: list[str] = []

    for model in _tenant_scoped():
        for name in ("created_at", "updated_at"):
            column = model.__table__.columns.get(name)
            if column is None:
                offenders.append(f"{model.__tablename__}.{name} (missing)")
                continue
            # app/db/base.TIMESTAMPTZ is an INSTANCE — DateTime(timezone=True) —
            # not a class, so isinstance against it cannot work. The property
            # that matters is the flag.
            if not isinstance(column.type, DateTime) or not column.type.timezone:
                offenders.append(f"{model.__tablename__}.{name} ({column.type})")

    assert not offenders, f"columns that are not TIMESTAMPTZ: {offenders}"


def test_tenant_scoped_tables_have_uuid_primary_key() -> None:
    """The mixin also supplies `id`. Assert it survived on every table."""
    offenders = [
        m.__tablename__
        for m in _tenant_scoped()
        if "id" not in m.__table__.columns or not m.__table__.columns["id"].primary_key
    ]
    assert not offenders, f"tenant-scoped tables without an `id` primary key: {offenders}"


def test_tenants_table_is_the_documented_exception() -> None:
    """`tenants` must NOT carry tenant_id — the record IS the tenant.

    It also must not inherit TenantScopedMixin: `with_loader_criteria` in
    session.py targets that mixin, and a Tenant caught by it would filter the
    tenants table by its own missing column.
    """
    assert not issubclass(Tenant, TenantScopedMixin), (
        "Tenant must not inherit TenantScopedMixin — see app/db/base.py"
    )
    assert "tenant_id" not in Tenant.__table__.columns, (
        "tenants must NOT have a tenant_id column (it is the tenant root)"
    )
    # The exception is only about tenant_id: timestamps still apply.
    for name in ("created_at", "updated_at"):
        column = Tenant.__table__.columns[name]
        assert isinstance(column.type, DateTime) and column.type.timezone, (
            f"tenants.{name} must still be TIMESTAMPTZ, got {column.type}"
        )
