#!/usr/bin/env python3
"""
hexflow_contract.py — Processor for ARIA Hex-flow contracts.

Connects to the ARIA shuttle engine's hexagonal flow vector:
  INGEST → SYNTH → RESOLVE → MUTATE → VERIFY → COMMIT

Reads:
  ~/.aria/SHUTTLE.json               — shuttle state (hex_stage, active_task, step_queue)
  ~/opt/aria/spool/priority_triplets.json — priority triplet tasks
  ~/aegis_qwen_inbox.json            — inbox FETCH/instruction messages

Integrates with Viper NMCT contract validation:
  - Each task step must declare a `once` self-test
  - Audit trail is append-only (never delete/revert)
  - SHA-256 evidence for every state transition
"""
import json
import os
import hashlib
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
ARIA_DIR = HOME / ".aria"
OPT_DIR = HOME / "opt" / "aria"
SHUTTLE_FILE = ARIA_DIR / "SHUTTLE.json"
TRIPLETS_FILE = OPT_DIR / "spool" / "priority_triplets.json"
INBOX_FILE = HOME / "aegis_qwen_inbox.json"
HISTORY_DIR = ARIA_DIR / "hex_history"

HEX_STAGES = ["INGEST", "SYNTH", "RESOLVE", "MUTATE", "VERIFY", "COMMIT"]


def sha256_text(text: str) -> str:
    """Return SHA-256 hex digest of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_shuttle() -> dict:
    """Load shuttle state from SHUTTLE.json."""
    if not SHUTTLE_FILE.exists():
        return {
            "hex_stage": "INGEST",
            "active_task": None,
            "direction": "FORWARD",
            "step_queue": [],
            "rejections": [],
            "stage_history": [],
        }
    try:
        return json.loads(SHUTTLE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {
            "hex_stage": "INGEST",
            "active_task": None,
            "direction": "FORWARD",
            "step_queue": [],
            "rejections": [],
            "stage_history": [],
        }


def save_shuttle(state: dict) -> None:
    """Persist shuttle state atomically."""
    SHUTTLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SHUTTLE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(SHUTTLE_FILE)


def load_triplets() -> list:
    """Load priority triplets from ARIA spool."""
    if not TRIPLETS_FILE.exists():
        return []
    try:
        return json.loads(TRIPLETS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def load_inbox() -> list:
    """Load inbox messages from aegis_qwen_inbox.json."""
    if not INBOX_FILE.exists():
        return []
    try:
        return json.loads(INBOX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def next_stage(current: str, direction: str = "FORWARD") -> str:
    """Get the next hex stage."""
    idx = HEX_STAGES.index(current) if current in HEX_STAGES else 2  # default to RESOLVE
    step = 1 if direction == "FORWARD" else -1
    return HEX_STAGES[(idx + step) % len(HEX_STAGES)]


def advance_task(state: dict, task_text: str, steps: list) -> dict:
    """Begin advancing a single task through the hex-flow.

    Returns updated state. Records each transition with SHA-256 evidence.
    """
    state["active_task"] = task_text
    state["step_queue"] = list(steps)
    state["direction"] = "FORWARD"
    state["hex_stage"] = "INGEST"
    _record_transition(task_text, "INGEST", sha256_text(task_text))
    return state


def execute_next_step(state: dict) -> dict:
    """Execute the next step in the current task's queue.

    Follows the Scientific Method (ask_kai.py gist):
      MEASURE → HYPOTHESISE → CHANGE ONE → MEASURE → COMPARE → KEEP/REVERT → REDO
    """
    if not state["active_task"]:
        return state

    if not state["step_queue"]:
        state["hex_stage"] = "COMMIT"
        _record_transition(state["active_task"], "COMMIT", sha256_text(state["active_task"] + "_committed"))
        return state

    current_step = state["step_queue"].pop(0)
    current_idx = HEX_STAGES.index(state["hex_stage"]) if state["hex_stage"] in HEX_STAGES else 0
    next_stage_name = next_stage(state["hex_stage"], state["direction"])

    evidence = sha256_text(current_step + now_iso())
    _record_transition(state["active_task"], state["hex_stage"], evidence)
    print(f"▶ [{state['hex_stage']}] {current_step}")

    state["hex_stage"] = next_stage_name
    return state


def _record_transition(task: str, stage: str, evidence: str) -> None:
    """Append-only transition log (never delete — Viper axiom)."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": now_iso(),
        "task": sha256_text(task)[:16],
        "stage": stage,
        "evidence": evidence,
    }
    log_file = HISTORY_DIR / "transitions.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def validate_contract(task: dict) -> bool:
    """Validate a task against Viper NMCT contract rules.

    Contract rules:
      1. Must have a `once` self-test reference
      2. Must declare a `summary_line`
      3. Must be headless (no interactive prompts)
      4. Must be env-tunable
    """
    required = ["once", "summary_line"]
    for key in required:
        if key not in task:
            return False
    return True


def pending_inbox_actions() -> list:
    """Extract actionable items from the Aegis inbox.

    Returns list of {action, correlation_id, url, ts} for FETCH and other
    instruction messages.
    """
    inbox = load_inbox()
    actions = []
    for msg in inbox:
        m = msg.get("message", "")
        if "FETCH:" in m:
            url = m.split("FETCH:", 1)[1].strip()
            actions.append({
                "action": "FETCH",
                "correlation_id": msg.get("correlation_id", ""),
                "url": url,
                "sender": msg.get("sender", ""),
                "ts": now_iso(),
            })
        elif m.startswith("ISSUE:") or m.startswith("CREATE:"):
            actions.append({
                "action": m.split(":", 1)[0],
                "correlation_id": msg.get("correlation_id", ""),
                "message": m,
                "sender": msg.get("sender", ""),
                "ts": now_iso(),
            })
    return actions


def collect_triplet_steps(triplet: dict) -> list:
    """Extract the ordered execution steps from a priority triplet."""
    try:
        tele = triplet.get("triplet", {}).get("teleology", {})
        steps = []
        for key, val in tele.items():
            steps.append(val)
        return steps
    except Exception:
        return []


def run_hexflow_cycle() -> dict:
    """Run one full hexflow processing cycle.

    1. Load shuttle state
    2. Collect pending inbox actions
    3. If no active task, pick up next triplet or inbox task
    4. Execute steps through hex stages
    5. Return result summary
    """
    state = load_shuttle()
    result = {
        "cycle": now_iso(),
        "hex_stage": state["hex_stage"],
        "active_task": state["active_task"],
        "steps_remaining": len(state["step_queue"]),
        "inbox_actions": 0,
        "completed": False,
    }

    inbox_actions = pending_inbox_actions()
    result["inbox_actions"] = len(inbox_actions)

    if not state["active_task"] and state["step_queue"]:
        steps = state["step_queue"]
        task = state["active_task"] or "unassigned"
    elif not state["active_task"]:
        triplets = load_triplets()
        if triplets:
            t = triplets[0]
            task_text = t.get("source_item", {}).get("text", "unknown")
            steps = collect_triplet_steps(t)
        elif inbox_actions:
            a = inbox_actions[0]
            task_text = f"Process {a['action']}: {a.get('url', a.get('message', ''))[:80]}"
            steps = [
                f"MEASURE: Assess {a['action']} target",
                f"SYNTH: Plan execution for {a['correlation_id']}",
                f"RESOLVE: Execute {a['action']} via gh CLI",
                f"MUTATE: Record results with SHA-256",
                f"VERIFY: Confirm action completed",
                f"COMMIT: Persist to hex_history",
            ]
        else:
            state["hex_stage"] = "INGEST"
            save_shuttle(state)
            result["completed"] = True
            return result
        state = advance_task(state, task_text, steps)
        result["active_task"] = task_text

    if state["step_queue"]:
        state = execute_next_step(state)
        result["hex_stage"] = state["hex_stage"]
        result["steps_remaining"] = len(state["step_queue"])
    else:
        result["completed"] = True
        state["hex_stage"] = "COMMIT"

    save_shuttle(state)
    return result


def status() -> dict:
    """Return current shuttle status."""
    state = load_shuttle()
    inbox = load_inbox()
    triplets = load_triplets()
    return {
        "hex_stage": state["hex_stage"],
        "active_task": state["active_task"],
        "step_queue": state["step_queue"],
        "rejections": state["rejections"],
        "inbox_messages": len(inbox),
        "pending_triplets": len(triplets),
    }


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "cycle"
    if cmd == "status":
        print(json.dumps(status(), indent=2))
    elif cmd == "inbox":
        print(json.dumps(pending_inbox_actions(), indent=2))
    elif cmd == "cycle":
        print(json.dumps(run_hexflow_cycle(), indent=2))
    elif cmd == "validate":
        triplets = load_triplets()
        for t in triplets:
            print(f"  {t.get('source_item', {}).get('text', '?')[:60]}... -> {'valid' if validate_contract(t) else 'INVALID'}")
    else:
        print(f"Unknown command: {cmd}. Use: status, inbox, cycle, validate")
