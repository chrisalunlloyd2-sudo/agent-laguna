#!/usr/bin/env python3
"""
hounty.py — Honey/Hounty reward system for Agent Laguna.

Tracks points earned by completing tasks, self-improvement steps, and
hexflow contract processing. Named "hounty" as a portmanteau of
"honey" (sweet reward) and "bounty" (task reward).

Storage: ~/.agent_laguna/hounty.json (append-only ledger + current balance)
"""
import json
import os
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

HOME = Path.home()
LAGUNA_DIR = HOME / ".agent_laguna"
HOUNTY_FILE = LAGUNA_DIR / "hounty.json"
DAILY_LOG = LAGUNA_DIR / "daily_ledger.jsonl"


# ── Hounty award values ─────────────────────────────────────────────────────
AWARDS = {
    "hexflow_step": 5,        # points for completing one hex-stage step
    "hexflow_commit": 50,     # points for committing a task through all stages
    "task_complete": 25,      # points for completing a daily task
    "task_personalize": 10,   # points for personalizing a task
    "self_improve": 30,       # points for completing a self-improvement step
    "gist_fetch": 15,         # points for fetching a gist
    "issue_create": 20,       # points for creating a GitHub issue
    "daily_streak": 10,       # bonus per consecutive day active
}


def _ensure_dirs():
    LAGUNA_DIR.mkdir(parents=True, exist_ok=True)


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_hounty() -> dict:
    """Load or initialize hounty state."""
    _ensure_dirs()
    if not HOUNTY_FILE.exists():
        return {
            "total_points": 0,
            "current_streak": 0,
            "last_active": None,
            "achievements": [],
            "ledger": [],
        }
    try:
        return json.loads(HOUNTY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {
            "total_points": 0,
            "current_streak": 0,
            "last_active": None,
            "achievements": [],
            "ledger": [],
        }


def save_hounty(state: dict) -> None:
    """Persist hounty state atomically."""
    _ensure_dirs()
    tmp = HOUNTY_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(HOUNTY_FILE)


def award(points: int, reason: str, category: str = "general") -> dict:
    """Award hounty points. Returns updated state."""
    state = load_hounty()

    # Daily streak tracking
    today = _today_str()
    if state["last_active"] == today:
        streak_bonus = 0
    else:
        if state["last_active"]:
            yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
            if state["last_active"] == yesterday:
                state["current_streak"] += 1
            else:
                state["current_streak"] = 1
        else:
            state["current_streak"] = 1
        streak_bonus = state["current_streak"] * AWARDS["daily_streak"]

    entry = {
        "ts": _now_iso(),
        "date": today,
        "reason": reason,
        "category": category,
        "base_points": points,
        "streak_bonus": streak_bonus,
        "total_awarded": points + streak_bonus,
    }

    state["total_points"] += entry["total_awarded"]
    state["last_active"] = today
    state["ledger"].append(entry)

    # Check for achievements
    new_achievements = check_achievements(state)
    state["achievements"].extend(new_achievements)

    # Append-only daily ledger
    DAILY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(DAILY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    save_hounty(state)

    if streak_bonus:
        print(f"  🍯 +{points} base + {streak_bonus} streak bonus = {entry['total_awarded']} points! (streak: {state['current_streak']}d)")
    else:
        print(f"  🍯 +{points} points for {reason}")

    return state


def check_achievements(state: dict) -> list:
    """Check if any new achievements have been earned."""
    earned = []
    total = state["total_points"]
    streak = state["current_streak"]
    existing = set(a["name"] for a in state["achievements"])

    achievements = [
        ("first_drop", 10, "First hounty drop — dipped your toe in the lagoon"),
        ("honey_pot", 100, "Honey pot — 100 points accumulated"),
        ("golden_streak", 100, "Golden streak — 10 days consecutive"),
        ("hex_master", 250, "Hex master — completed full hexflow cycle 5 times"),
        ("self_evolved", 300, "Self evolved — 10 self-improvement steps"),
        ("fleet_commander", 500, "Fleet commander — 20 tasks completed"),
        ("legendary", 1000, "Legendary — 1000 points, you're a hounty legend"),
    ]

    # Count hexflow commits and self-improve steps from ledger
    hex_commits = sum(1 for e in state["ledger"] if e["reason"] == "hexflow_commit")
    self_improves = sum(1 for e in state["ledger"] if e["category"] == "self_improve")
    tasks_done = sum(1 for e in state["ledger"] if e["category"] == "task")

    checks = [
        ("first_drop", total >= 10),
        ("honey_pot", total >= 100),
        ("golden_streak", streak >= 10),
        ("hex_master", hex_commits >= 5),
        ("self_evolved", self_improves >= 10),
        ("fleet_commander", tasks_done >= 20),
        ("legendary", total >= 1000),
    ]

    for name, threshold, desc in achievements:
        if name not in existing:
            earned_entry = next((c for c in checks if c[0] == name), None)
            if earned_entry and earned_entry[1]:
                earned.append({"name": name, "description": desc, "ts": _now_iso()})

    return earned


def balance() -> dict:
    """Return current hounty balance and stats."""
    state = load_hounty()
    today = _today_str()
    today_points = sum(e["total_awarded"] for e in state["ledger"] if e["date"] == today)
    return {
        "total_points": state["total_points"],
        "current_streak": state["current_streak"],
        "today_points": today_points,
        "achievements": state["achievements"],
        "ledger_entries": len(state["ledger"]),
    }


def leader() -> list:
    """Return top of hounty leaderboard (just our own entry)."""
    state = load_hounty()
    return [{
        "agent": "agent-laguna",
        "total_points": state["total_points"],
        "streak": state["current_streak"],
        "achievements": len(state["achievements"]),
    }]


def award_hexflow_step(stage: str) -> dict:
    """Award points for completing a hexflow stage."""
    if stage == "COMMIT":
        return award(AWARDS["hexflow_commit"], f"hexflow_commit ({stage})", "hexflow")
    return award(AWARDS["hexflow_step"], f"hexflow_step ({stage})", "hexflow")


def award_task_complete(personalized: bool = False) -> dict:
    """Award points for completing a daily task."""
    points = AWARDS["task_complete"]
    reason = "task_complete"
    if personalized:
        points += AWARDS["task_personalize"]
        reason = "task_complete (personalized)"
    return award(points, reason, "task")


def award_self_improvement() -> dict:
    """Award points for a self-improvement step."""
    return award(AWARDS["self_improve"], "self_improvement_step", "self_improve")


def award_gist_fetch(correlation_id: str) -> dict:
    """Award points for fetching a gist."""
    return award(AWARDS["gist_fetch"], f"gist_fetch ({correlation_id})", "gist")


def award_issue_create() -> dict:
    """Award points for creating a GitHub issue."""
    return award(AWARDS["issue_create"], "issue_create", "github")


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "balance"
    if cmd == "balance":
        print(json.dumps(balance(), indent=2))
    elif cmd == "leader":
        print(json.dumps(leader(), indent=2))
    elif cmd == "demo":
        award(10, "demo award", "test")
        print(json.dumps(balance(), indent=2))
    else:
        print(f"Unknown command: {cmd}. Use: balance, leader, demo")
