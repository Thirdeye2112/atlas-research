"""
atlas_research.probability.registry
--------------------------------------
Built-in questions and test specifications.
Calling seed_registry() upserts all definitions into the DB.
"""

from __future__ import annotations

from .questions import ResearchQuestion, upsert_question
from .specs import TestSpec, upsert_spec, get_spec

# ── Built-in questions ────────────────────────────────────────────────────────

QUESTIONS: list[ResearchQuestion] = [
    ResearchQuestion(
        name="SPY down streaks",
        description="What happens after SPY closes down N consecutive days?",
        category="streak",
    ),
    ResearchQuestion(
        name="SPY up streaks",
        description="What happens after SPY closes up N consecutive days?",
        category="streak",
    ),
    ResearchQuestion(
        name="SPY gap down",
        description="What happens after SPY gaps down at the open?",
        category="gap",
    ),
    ResearchQuestion(
        name="SPY gap up",
        description="What happens after SPY gaps up at the open?",
        category="gap",
    ),
]

# ── Built-in specs ────────────────────────────────────────────────────────────

BUILTIN_SPECS: list[dict] = [
    # Down streaks n=2..5
    {"question": "SPY down streaks", "ticker": "SPY", "condition_type": "down_streak", "params": {"n": 2}},
    {"question": "SPY down streaks", "ticker": "SPY", "condition_type": "down_streak", "params": {"n": 3}},
    {"question": "SPY down streaks", "ticker": "SPY", "condition_type": "down_streak", "params": {"n": 4}},
    {"question": "SPY down streaks", "ticker": "SPY", "condition_type": "down_streak", "params": {"n": 5}},
    # Up streaks n=2..5
    {"question": "SPY up streaks",   "ticker": "SPY", "condition_type": "up_streak",   "params": {"n": 2}},
    {"question": "SPY up streaks",   "ticker": "SPY", "condition_type": "up_streak",   "params": {"n": 3}},
    {"question": "SPY up streaks",   "ticker": "SPY", "condition_type": "up_streak",   "params": {"n": 4}},
    {"question": "SPY up streaks",   "ticker": "SPY", "condition_type": "up_streak",   "params": {"n": 5}},
    # Gap studies
    {"question": "SPY gap down",     "ticker": "SPY", "condition_type": "gap_down",    "params": {"threshold_pct": 0.5}},
    {"question": "SPY gap up",       "ticker": "SPY", "condition_type": "gap_up",      "params": {"threshold_pct": 0.5}},
]


# ── DB seeding ────────────────────────────────────────────────────────────────

def seed_registry() -> dict[str, int]:
    """Upsert all built-in questions and specs. Returns {question_name: id}."""
    q_ids: dict[str, int] = {}
    for q in QUESTIONS:
        q_ids[q.name] = upsert_question(q)

    for entry in BUILTIN_SPECS:
        spec = TestSpec(
            ticker=entry["ticker"],
            condition_type=entry["condition_type"],
            params=entry["params"],
            question_id=q_ids.get(entry.get("question", "")),
        )
        upsert_spec(spec)

    return q_ids


def get_or_create_spec(ticker: str, condition_type: str, params: dict) -> int:
    """Return existing spec_id or create a new one (no question link)."""
    existing = get_spec(ticker, condition_type, params)
    if existing is not None:
        return existing.id  # type: ignore[return-value]
    spec = TestSpec(ticker=ticker, condition_type=condition_type, params=params)
    return upsert_spec(spec)
