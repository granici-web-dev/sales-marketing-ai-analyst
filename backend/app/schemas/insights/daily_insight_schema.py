from __future__ import annotations

"""Pydantic v2 schema for DailyInsightResponse — AI Insights Phase 5.

D-05: Full DailyInsightResponse schema (rich SPEC.md version with positives[], warnings[],
      weekly_action_plan[], expected_outcome).
D-02: problems[] hard max 3 enforced via Pydantic max_length=3.
D-19: estimated_loss_ron is Decimal, never float — all monetary values use Decimal.

Classes exported: ActionItem, Problem, Positive, Warning, DailyInsightResponse.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    """Single action item assigned to a named owner with a relative deadline.

    D-09: owner = real Sofa Belle salesperson name or role (Manager, Marketing Sofa).
    D-10: deadline = relative Romanian label (Azi, Mâine, Săptămâna aceasta, Luna aceasta).
    D-12: expected_outcome = measurable metric + target value (not qualitative description).
    """

    order: int
    description: str
    owner: str  # real Sofa Belle name or role (D-09)
    deadline: Literal["Azi", "Mâine", "Săptămâna aceasta", "Luna aceasta"]  # D-10 enforced
    expected_outcome: str  # measurable metric + target (D-12)


class Problem(BaseModel):
    """A detected business problem with root cause and action plan.

    D-04: id = rule_id from detected_problems (traceable link insight → anomaly → data).
    D-11: 2-3 actions per problem (enforced by system prompt instruction, not Pydantic).
    D-19: estimated_loss_ron is Decimal, never float.
    """

    id: str  # = rule_id from detected_problems (D-04)
    severity: Literal["high", "medium", "low"]
    category: Literal["marketing", "sales", "team", "funnel"]
    title: str
    description: str  # 2-3 sentences with figures from input data
    estimated_loss_ron: Decimal  # Decimal not float (D-19)
    actions: list[ActionItem]  # 2-3 items per problem (D-11 — system prompt enforced)


class Positive(BaseModel):
    """A positive signal — what is working well and should be maintained or scaled.

    Count: Claude decides (0-3). No Pydantic constraint.
    """

    title: str
    description: str
    recommendation: str


class Warning(BaseModel):
    """A weak signal that does not reach problem severity but warrants monitoring.

    Count: Claude decides. These are early warnings, not full problems with actions.
    """

    title: str
    description: str


class DailyInsightResponse(BaseModel):
    """Full daily AI insight report for Sofa Belle — AI-02, D-01.

    D-02: problems[] hard max 3 enforced by Pydantic max_length=3.
          When more than 3 anomalies fire, InsightService selects top 3 by estimated_loss_ron
          descending before constructing the user message.
    D-03: weekly_action_plan = 5-7 flat prioritized action strings synthesized by Claude
          independently (not derived by code from problems[].actions[]).
    D-19: All monetary fields are Decimal — validated by Problem schema.
    """

    summary: str  # one overview paragraph in Romanian
    problems: list[Problem] = Field(max_length=3)  # hard cap at 3 (D-02)
    positives: list[Positive]  # 0-3, Claude decides count
    warnings: list[Warning]  # 0-N weak signals, Claude decides
    weekly_action_plan: list[str] = Field(min_length=1)  # D-03: at least 1 item (5-7 expected)
    generated_at: datetime  # set server-side in InsightService, not by Claude
