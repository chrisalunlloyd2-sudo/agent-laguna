#!/usr/bin/env python3
"""
agent.py — Agent Laguna main orchestrator.

Coordinates the daily cycle:
  1. Hexflow contract processing (shuttle engine integration)
  2. Daily task execution (inbox, gems, heartbeat tasks)
  3. Self-improvement (1 step per day, Scientific Method)
  4. Hounty reward tracking
  5. Daily completion + personalization

Runs as a daily cron job or loop. Stdlib-only (no external dependencies).
"""
import json
import os
import sys
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
LAGUNA_DIR = HOME / ".agent_laguna"
AGENT_LAGUNA_DIR = Path(__file__).parent

# Import sibling modules
sys.path.insert(0, str(AGENT_LAGUNA_DIR))
import hexflow_contract  # noqa: E402
import hounty  # noqa: E402
import self_improve  # noqa: E402
import daily_task  # noqa: E402


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _ensure_dirs():
    LAGUNA_DIR.mkdir(parents=True, exist_ok=True)
    (LAGUNA_DIR / "logs").mkdir(parents=True, exist_ok=True)


def _log(msg: str):
    _ensure_dirs()
    log_file = LAGUNA_DIR / "logs" / "agent.log"
    entry = f"[{_now_iso()}] {msg}\n"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry)
    print(entry, end="")


def initialize() -> dict:
    """Initialize Agent Laguna — create directories and default configs."""
    _ensure_dirs()

    # Default config
    config = {
        "agent_id": "agent-laguna",
        "version": "1.0.0",
        "hexflow_integration": True,
        "hounty_enabled": True,
        "daily_personalization": True,
        "self_improve_daily": True,
        "max_inbox_actions_per_cycle": 9,
        "created": _now_iso(),
    }
    config_file = LAGUNA_DIR / "config.json"
    if not config_file.exists():
        config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
    _log(f"Agent Laguna initialized (ID: {config['agent_id']})")
    return config


def run_daily() -> dict:
    """Execute one full daily cycle for Agent Laguna."""
    _log("═══ Starting daily cycle ═══")

    result = {
        "date": _today_str(),
        "timestamp": _now_iso(),
        "hexflow": None,
        "tasks": None,
        "self_improvement": None,
        "hounty_before": {},
        "hounty_after": {},
        "completed": True,
    }

    # Capture hounty before
    result["hounty_before"] = hounty.balance()

    # 1. Hexflow contract processing
    _log("→ Phase 1: Hexflow contract processing")
    hexflow_result = hexflow_contract.run_hexflow_cycle()
    result["hexflow"] = hexflow_result
    _log(f"   Hexflow: stage={hexflow_result.get('hex_stage')}, "
         f"completed={hexflow_result.get('completed')}")

    # Award hounty for hexflow progress
    if hexflow_result.get("completed"):
        hounty.award_hexflow_step("COMMIT")
    else:
        stage = hexflow_result.get("hex_stage", "INGEST")
        hounty.award_hexflow_step(stage)

    # 2. Daily task execution
    _log("→ Phase 2: Daily task execution")
    task_result = daily_task.run_daily_cycle()
    result["tasks"] = task_result

    # 3. Self-improvement (already done in daily_task, but ensure)
    _log("→ Phase 3: Self-improvement check")
    si_result = self_improve.execute_self_improvement()
    result["self_improvement"] = si_result
    if si_result.get("status") != "already_done":
        hounty.award_self_improvement()

    # Capture hounty after
    result["hounty_after"] = hounty.balance()

    # 4. Record completion
    _log(f"→ Daily cycle complete. Points: "
         f"{result['hounty_before']['total_points']} → "
         f"{result['hounty_after']['total_points']}")

    # Save daily result
    _ensure_dirs()
    result_file = LAGUNA_DIR / "daily_results" / f"{_today_str()}.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text(json.dumps(result, indent=2), encoding="utf-8")

    _log("═══ Daily cycle complete ═══\n")
    return result


def run_loop(interval_hours: int = 24, max_iterations: int = 0) -> None:
    """Run Agent Laguna in a continuous loop.

    By default, runs once per day (24h interval). Set max_iterations > 0
    for testing.
    """
    initialize()
    iteration = 0
    _log(f"Agent Laguna loop started (interval: {interval_hours}h)")

    while True:
        iteration += 1
        _log(f"Loop iteration {iteration}")

        try:
            run_daily()
            hounty.award(50, "daily_cycle_complete", "daily")
        except Exception as e:
            _log(f"ERROR in daily cycle: {e}")
            hounty.award(-25, f"cycle_error: {type(e).__name__}", "error")

        if max_iterations > 0 and iteration >= max_iterations:
            _log(f"Reached max iterations ({max_iterations}), stopping.")
            break

        _log(f"Sleeping {interval_hours}h until next cycle...")
        time.sleep(interval_hours * 3600)


def status() -> dict:
    """Return Agent Laguna status."""
    config_file = LAGUNA_DIR / "config.json"
    config = {}
    if config_file.exists():
        config = json.loads(config_file.read_text(encoding="utf-8"))

    return {
        "agent_id": config.get("agent_id", "agent-laguna"),
        "version": config.get("version", "unknown"),
        "status": "running" if self_improve._load_improvement_history() else "initialized",
        "hounty": hounty.balance(),
        "hexflow": hexflow_contract.status(),
        "today": _today_str(),
        "uptime": config.get("created", "unknown"),
    }


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "init"

    if cmd == "init":
        print(json.dumps(initialize(), indent=2))
    elif cmd == "daily":
        print(json.dumps(run_daily(), indent=2))
    elif cmd == "loop":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        max_iter = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        run_loop(interval, max_iter)
    elif cmd == "status":
        print(json.dumps(status(), indent=2))
    else:
        print(f"Usage: python agent.py [init|daily|loop [hours] [max_iter]|status]")
        print(f"  init  — Initialize Agent Laguna")
        print(f"  daily — Run one daily cycle")
        print(f"  loop  — Run continuously (default: 24h interval)")
        print(f"  status— Show current status")
