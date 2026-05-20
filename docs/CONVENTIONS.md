# Coding Conventions

> Правила и стандарты разработки. **Соблюдать обязательно.**

## Python

### Imports

```python
from __future__ import annotations  # Always first line

# Standard library
import asyncio
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

# Third-party
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Local
from app.core.tenancy import get_current_tenant
from app.db.session import get_session
from app.models.metrics.daily_kpi import DailyKPI
from app.schemas.dashboard import MarketingDashboardResponse
```

**Rules:**
- `from __future__ import annotations` first line of every file
- Standard library imports separated from third-party
- Local imports last
- One import per line for clarity (no `from x import a, b, c, d, e`)
- Absolute imports only, never relative (`from app.core.x`, not `from ..core.x`)

### Type Hints

```python
# ✅ GOOD: Modern syntax (Python 3.10+)
def get_lead(lead_id: UUID) -> Lead | None: ...

async def list_calls(
    tenant_id: UUID,
    start_date: datetime,
    salesperson_ids: list[UUID] | None = None,
) -> list[Call]: ...

# ❌ BAD: Old syntax
from typing import Optional, List

def get_lead(lead_id: UUID) -> Optional[Lead]: ...
async def list_calls(...) -> List[Call]: ...
```

**Rules:**
- Use `list`, `dict`, `tuple`, `set` (lowercase) — Python 3.9+
- Use `T | None` instead of `Optional[T]` — Python 3.10+
- Type hint **every** function parameter and return value
- For complex types, use type aliases

### Pydantic Models

```python
from pydantic import BaseModel, ConfigDict, Field

class LeadCreate(BaseModel):
    """Schema for creating a new lead."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )
    
    source: str = Field(..., min_length=1, max_length=50)
    customer_phone: str = Field(..., pattern=r"^\+?[0-9]{8,15}$")
    category: LeadCategory  # Use Enum, not raw string


class LeadResponse(BaseModel):
    """Schema returned to API clients."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    source: str
    created_at: datetime
```

**Rules:**
- Separate schemas for create/update/response (don't reuse)
- `BaseModel`, not `dataclass`
- Use `Field()` for constraints and descriptions
- Use Enums for fixed-value strings
- `from_attributes=True` для конвертации из SQLAlchemy models

### SQLAlchemy Models

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Lead(Base):
    """A lead synced from MEFI CRM."""
    
    __tablename__ = "mefi_leads"
    
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str | None] = mapped_column(String(50))
    raw_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    
    # Relationships
    salesperson: Mapped["Salesperson | None"] = relationship(...)
```

**Rules:**
- Use SQLAlchemy 2.x `Mapped[...]` syntax
- Type-safe with proper Python types
- Always specify `tenant_id` (kроме `tenants` table)
- Always have created_at, server-side default
- Use `String(N)` with explicit length, not just `String`
- For JSON data: `JSONB` (not `JSON`)

### Functions

```python
# ✅ GOOD
async def calculate_cpl_for_source(
    db: AsyncSession,
    tenant_id: UUID,
    source: str,
    date_range: tuple[datetime, datetime],
) -> Decimal:
    """Calculate Cost Per Lead for a specific traffic source.
    
    Args:
        db: Async database session
        tenant_id: Tenant scope
        source: Traffic source name (e.g., "facebook", "google")
        date_range: (start_date, end_date) tuple
    
    Returns:
        CPL in tenant's default currency, or 0 if no leads
    
    Raises:
        ValueError: If date_range is invalid
    """
    start, end = date_range
    if start > end:
        raise ValueError("start_date must be before end_date")
    
    # ... implementation ...

# ❌ BAD
async def calc_cpl(db, tid, src, start, end):  # No types, abbreviated names
    # ... implementation ...
```

**Rules:**
- Functions ≤ 50 lines (decompose if longer)
- Always docstring for public functions (Google style)
- Descriptive names, no abbreviations
- Async by default for I/O
- Validate inputs early, raise specific exceptions

### Error Handling

```python
# Custom exceptions hierarchy
class AppError(Exception):
    """Base exception for application errors."""
    pass


class NotFoundError(AppError):
    """Resource not found."""
    pass


class TenantIsolationError(AppError):
    """Attempted to access resource outside tenant scope."""
    pass


# Usage
async def get_lead_by_id(
    db: AsyncSession,
    tenant_id: UUID,
    lead_id: UUID,
) -> Lead:
    result = await db.execute(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.tenant_id == tenant_id,  # Always filter by tenant!
        )
    )
    lead = result.scalar_one_or_none()
    if lead is None:
        raise NotFoundError(f"Lead {lead_id} not found")
    return lead


# In API layer — catch specific exceptions and translate to HTTP
@router.get("/{lead_id}")
async def read_lead(lead_id: UUID, ...) -> LeadResponse:
    try:
        lead = await get_lead_by_id(db, tenant.id, lead_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Lead not found")
    return LeadResponse.model_validate(lead)
```

**Rules:**
- Service layer raises domain exceptions
- API layer catches and translates to HTTP exceptions
- Never expose internal errors to clients
- Log full traceback, return user-friendly message

### Logging

```python
import structlog

logger = structlog.get_logger(__name__)

# ✅ GOOD: Structured, no PII
logger.info(
    "lead.synced",
    tenant_id=str(tenant_id),
    lead_id=str(lead.id),
    source=lead.source,
    duration_ms=duration,
)

# ❌ BAD: Unstructured, contains PII
logger.info(f"Synced lead for customer {customer_name} with phone {phone}")
```

**Rules:**
- Use `structlog`, never `print()`
- Event names in `dot.notation` style (`lead.synced`, `etl.failed`)
- Cast UUIDs to str (JSON serialization)
- **NEVER log PII**: phone, email, name, transcript content
- OK: tenant_id, entity_id, status, duration, error class

## Database Queries

### Always filter by tenant_id

```python
# ✅ GOOD
stmt = select(Lead).where(
    Lead.tenant_id == tenant_id,
    Lead.status == "qualified",
)

# ❌ BAD — missing tenant_id filter!
stmt = select(Lead).where(Lead.status == "qualified")
```

### Use specific columns, not SELECT *

```python
# ✅ GOOD
stmt = select(Lead.id, Lead.source, Lead.created_at).where(...)

# ❌ BAD
stmt = select(Lead).where(...)  # Загружает все колонки включая raw_payload
```

### Pagination

```python
# Use LIMIT/OFFSET для UI, keyset pagination для больших данных
stmt = (
    select(Lead)
    .where(Lead.tenant_id == tenant_id)
    .order_by(Lead.created_at.desc())
    .limit(page_size)
    .offset(page * page_size)
)
```

### Aggregations

```python
from sqlalchemy import func, case

# Group by category, count leads
stmt = (
    select(
        Lead.category,
        func.count(Lead.id).label("count"),
    )
    .where(
        Lead.tenant_id == tenant_id,
        Lead.created_at >= start_date,
    )
    .group_by(Lead.category)
)
```

## TypeScript / Frontend

### Component structure

```tsx
// components/dashboards/MarketingFunnel.tsx
"use client";  // Only if needed for interactivity

import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { FunnelChart } from "@/components/charts/FunnelChart";
import { fetchMarketingDashboard } from "@/lib/api/dashboards";
import type { MarketingDashboardData } from "@/types/dashboard";

interface MarketingFunnelProps {
  dateFrom: Date;
  dateTo: Date;
  comparison?: "yoy" | "prev_period";
}

export function MarketingFunnel({
  dateFrom,
  dateTo,
  comparison = "prev_period",
}: MarketingFunnelProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["marketing-dashboard", dateFrom, dateTo, comparison],
    queryFn: () => fetchMarketingDashboard({ dateFrom, dateTo, comparison }),
  });
  
  if (isLoading) return <FunnelSkeleton />;
  if (error) return <ErrorState error={error} />;
  if (!data) return null;
  
  return (
    <Card>
      <FunnelChart data={data.funnel} />
    </Card>
  );
}
```

**Rules:**
- Functional components with hooks (no class components)
- Named export, not default export (for refactoring)
- Props interface defined separately
- Server Components by default; `"use client"` only when needed
- One component per file
- Component file name = component name (`MarketingFunnel.tsx`)

### API client

```tsx
// lib/api/dashboards.ts
import { apiClient } from "./client";
import type { MarketingDashboardData } from "@/types/dashboard";

interface FetchMarketingParams {
  dateFrom: Date;
  dateTo: Date;
  comparison: "yoy" | "prev_period";
}

export async function fetchMarketingDashboard(
  params: FetchMarketingParams,
): Promise<MarketingDashboardData> {
  const response = await apiClient.get<MarketingDashboardData>(
    "/api/v1/dashboards/marketing",
    {
      params: {
        from: params.dateFrom.toISOString(),
        to: params.dateTo.toISOString(),
        compare: params.comparison,
      },
    },
  );
  return response.data;
}
```

### Types

```typescript
// types/dashboard.ts

export interface MarketingDashboardData {
  period: DateRange;
  comparison_period: DateRange;
  budgets: BudgetsByChannel;
  funnel: MarketingFunnel;
  leads_by_category: LeadsByCategory;
  // ...
}

export interface BudgetsByChannel {
  meta: number;
  google: number;
  tiktok: number;
  total: number;
}

// Use string literal types for enums
export type LeadCategory =
  | "mail_fb_ig"
  | "telefon"
  | "whatsapp"
  | "site"
  | "designer"
  | "alte";
```

## Tests

### Test naming

```python
# Pattern: test_<unit>_<scenario>_<expected>

def test_calculate_cpl_with_no_leads_returns_zero(): ...
def test_calculate_cpl_with_valid_data_returns_correct_value(): ...
def test_get_lead_with_wrong_tenant_raises_not_found(): ...
```

### Test structure (AAA)

```python
async def test_sync_mefi_leads_creates_records(
    db_session: AsyncSession,
    tenant: Tenant,
    mefi_api_mock: Mock,
):
    # Arrange
    mefi_api_mock.fetch_leads.return_value = [
        {"id": "ext_1", "source": "facebook", ...},
        {"id": "ext_2", "source": "google", ...},
    ]
    
    # Act
    result = await sync_mefi_leads(db_session, tenant.id)
    
    # Assert
    assert result.synced_count == 2
    leads = await db_session.execute(
        select(Lead).where(Lead.tenant_id == tenant.id)
    )
    assert len(leads.scalars().all()) == 2
```

### Coverage targets

- **Business logic** (services/): ≥ 80%
- **API endpoints**: ≥ 70% (mostly integration tests)
- **Database models**: ≥ 50% (most logic is in services)
- **Utilities**: ≥ 90%

## Git

### Branch naming

```
feat/mefi-integration
fix/cpl-calculation-zero-division
chore/upgrade-celery-to-5.4
docs/add-sofa-belle-context
refactor/extract-anomaly-rules
```

### Commit messages (Conventional Commits)

```
feat(integrations): add MEFI leads sync task

Implements the basic ETL flow for syncing leads from MEFI API.
Handles pagination, retry on transient failures, and tenant isolation.

Closes #42
```

**Types:**
- `feat:` — new feature
- `fix:` — bug fix
- `chore:` — maintenance, deps, config
- `docs:` — documentation only
- `refactor:` — code restructuring without behavior change
- `test:` — adding/updating tests
- `perf:` — performance improvement
- `style:` — formatting (no code change)

### Pull Requests

- Title follows Conventional Commits format
- Description includes:
  - What changed
  - Why
  - How to test
  - Screenshots if UI
- Linked issue (`Closes #N`)
- All checks pass (lint, tests, type check)
- At least 1 reviewer (if team grows)

## When in doubt

1. Check existing code for patterns
2. Check this document
3. Check [CLAUDE.md](../CLAUDE.md)
4. Ask the user

Never:
- Skip tests "just this once"
- Hardcode tenant IDs
- Use raw SQL without explicit justification
- Catch generic `Exception`
- Use `Any` type to avoid figuring out the real type
