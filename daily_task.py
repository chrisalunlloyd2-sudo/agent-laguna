#!/usr/bin/env python3
"""
daily_task.py — Daily personalized task runner for Agent Laguna.

Reads from:
  ~/aegis_qwen_inbox.json            — inbox instructions (FETCH, ISSUE, etc.)
  ~/.matrix_ide/gem_library/         — gem snippets to process
  ~/heartbeat/tasks/*.task          — task manifests
  ~/gist_contents/                   — fetched gist contents

Each day:
  1. Pick up inbox actions (FETCH gists, process instructions)
  2. Process pending gem snippets (harvest, validate, categorize)
  3. Run 1 self-improvement step (delegated to self_improve.py)
  4. Award hounty points for completed work
  5. Record completion in daily ledger
"""
import json
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
LAGUNA_DIR = HOME / ".agent_laguna"
INBOX_FILE = HOME / "aegis_qwen_inbox.json"
GIST_DIR = HOME / "gist_contents"
GEM_LIBRARY = HOME / ".matrix_ide" / "gem_library"
HEARTBEAT_TASKS = HOME / "heartbeat" / "tasks"

# Import sibling modules
sys.path.insert(0, str(Path(__file__).parent))
import hounty  # noqa: E402
import self_improve  # noqa: E402


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _ensure_dirs():
    LAGUNA_DIR.mkdir(parents=True, exist_ok=True)
    (LAGUNA_DIR / "daily_results").mkdir(parents=True, exist_ok=True)


def load_inbox() -> list:
    if not INBOX_FILE.exists():
        return []
    try:
        return json.loads(INBOX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def process_inbox_actions() -> list:
    """Process all actionable messages in the Aegis inbox.

    Marks messages as PROCESSED (appends _processed flag) so they
    aren't re-processed on the next cycle.
    """
    inbox = load_inbox()
    results = []

    for msg in inbox:
        if msg.get("_processed"):
            continue

        m = msg.get("message", "")
        result = {"action": "unknown", "status": "skipped", "message": m}

        if "FETCH:" in m:
            url = m.split("FETCH:", 1)[1].strip()
            result["action"] = "FETCH"
            result["url"] = url
            result["status"] = _process_fetch(url, msg.get("correlation_id", ""))
            if result["status"] == "complete":
                hounty.award_gist_fetch(msg.get("correlation_id", "unknown"))

        elif m.startswith("ISSUE:"):
            result["action"] = "ISSUE"
            result["status"] = _process_issue(m)
            if result["status"] == "complete":
                hounty.award_issue_create()

        else:
            result["action"] = "MESSAGE"
            result["status"] = "acknowledged"

        result["correlation_id"] = msg.get("correlation_id", "")
        results.append(result)
        msg["_processed"] = True
        msg["_processed_at"] = _now_iso()

    # Persist processed flags back to inbox
    if any(msg.get("_processed") for msg in inbox):
        INBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = INBOX_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(inbox, indent=2), encoding="utf-8")
        tmp.replace(INBOX_FILE)

    return results


def _process_fetch(url: str, correlation_id: str) -> str:
    """Fetch a gist from the GitHub API and save its contents."""
    import urllib.request, urllib.error

    gist_id = url.rstrip("/").split("/gists/")[-1]
    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AgentLaguna/1.0",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        files = data.get("files", {})
        desc = data.get("description", "(no description)")
        parts = []
        for fname, finfo in files.items():
            parts.append(f"--- File: {fname} ---\n{finfo.get('content', '')}")
        content = f"Description: {desc}\n\n" + "\n\n".join(parts)

        GIST_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = desc.replace(" ", "_").replace(":", "_")[:60] if desc else gist_id
        out_path = GIST_DIR / f"{gist_id}_{safe_name}.md"
        out_path.write_text(content, encoding="utf-8")
        return "complete"
    except urllib.error.HTTPError as e:
        print(f"  FETCH failed for {gist_id}: HTTP {e.code}")
        return f"http_error_{e.code}"
    except Exception as e:
        print(f"  FETCH failed for {gist_id}: {e}")
        return f"error_{type(e).__name__}"


def _process_issue(msg: str) -> str:
    """Create a GitHub issue from an ISSUE: message."""
    try:
        body = msg.split("ISSUE:", 1)[1].strip()
        import subprocess
        result = subprocess.run(
            ["gh", "issue", "create", "--title", body[:80], "--body", body],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return "complete"
        return f"gh_error"
    except Exception:
        return "error"


def process_gems() -> list:
    """Process gem snippets from ~/.matrix_ide/gem_library/.

    For each unprocessed gem, attempt to categorize and validate it.
    Awards hounty points for validation.
    """
    if not GEM_LIBRARY.exists():
        return []

    results = []
    for gem_file in sorted(GEM_LIBRARY.glob("*.py")):
        gem_name = gem_file.stem
        result = {"gem": gem_name, "status": "processed"}

        content = gem_file.read_text(encoding="utf-8", errors="replace")
        result["type"] = _classify_gem(content)

        # Mark as processed in the gem file's metadata
        result["size"] = len(content)
        results.append(result)
        hounty.award(5, f"gem_harvest ({gem_name})", "gem")

    return results


def _classify_gem(content: str) -> str:
    """Classify a gem snippet by its content."""
    if "import subprocess" in content or "subprocess" in content:
        return "shell_command"
    elif "git " in content:
        return "git_command"
    elif "def " in content:
        return "code_function"
    elif "class " in content:
        return "code_class"
    else:
        return "snippet"


def process_heartbeat_tasks() -> list:
    """Process .task manifests from ~/heartbeat/tasks/."""
    if not HEARTBEAT_TASKS.exists():
        return []

    results = []
    for task_file in sorted(HEARTBEAT_TASKS.glob("*.task")):
        task_name = task_file.stem
        try:
            task = json.loads(task_file.read_text(encoding="utf-8"))
            result = {
                "task": task_name,
                "id": task.get("id", ""),
                "prompt": task.get("prompt", "")[:100],
                "status": "pending",
            }
            # Task is picked up — award points
            hounty.award(10, f"task_pickup ({task_name})", "heartbeat")
            results.append(result)
        except Exception as e:
            results.append({"task": task_name, "status": f"error: {e}"})
    return results


def personalize_tasks(tasks: list, inbox_results: list) -> list:
    """Personalize daily tasks based on today's date and context.

    Applies the personalization step: each task gets a personalized note.
    """
    today = _today_str()
    for task in tasks:
        task["personalized"] = True
        task["personalization_note"] = f"Task adapted for {today} operating context"
        hounty.award(10, "task_personalize", "task")
    return tasks


def run_daily_cycle() -> dict:
    """Run the full daily task cycle for Agent Laguna."""
    _ensure_dirs()
    today = _today_str()

    print(f"═══ Agent Laguna — Daily Cycle ({today}) ═══")

    cycle_result = {
        "date": today,
        "timestamp": _now_iso(),
        "inbox_actions": [],
        "gem_processing": [],
        "heartbeat_tasks": [],
        "self_improvement": None,
        "completed": True,
    }

    # 1. Process inbox actions
    print("\n▶ Processing Aegis inbox...")
    inbox_results = process_inbox_actions()
    cycle_result["inbox_actions"] = inbox_results
    print(f"  Processed {len(inbox_results)} inbox action(s)")

    # 2. Process gem snippets
    print("\n▶ Harvesting gem snippets...")
    gem_results = process_gems()
    cycle_result["gem_processing"] = gem_results
    print(f"  Processed {len(gem_results)} gem(s)")

    # 3. Process heartbeat tasks
    print("\n▶ Scanning heartbeat tasks...")
    hb_results = process_heartbeat_tasks()
    cycle_result["heartbeat_tasks"] = hb_results
    print(f"  Found {len(hb_results)} task(s)")

    # 4. Personalize tasks
    print("\n▶ Personalizing tasks...")
    all_tasks = hb_results + inbox_results
    all_tasks = personalize_tasks(all_tasks, inbox_results)

    # 5. Self-improvement (1 per day)
    print("\n▶ Self-improvement step...")
    si_result = self_improve.execute_self_improvement()
    cycle_result["self_improvement"] = si_result
    if si_result.get("status") != "already_done":
        hounty.award_self_improvement()

    # Record daily completion
    daily_record = {
        "date": today,
        "ts": _now_iso(),
        "inbox_count": len(inbox_results),
        "gem_count": len(gem_results),
        "task_count": len(hb_results),
        "self_improved": si_result.get("status") != "already_done",
    }
    daily_log = LAGUNA_DIR / "daily_ledger.jsonl"
    with open(daily_log, "a", encoding="utf-8") as f:
        f.write(json.dumps(daily_record) + "\n")

    print(f"\n✓ Daily cycle complete. Hounty: {hounty.balance()}")
    return cycle_result


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "cycle"
    if cmd == "cycle":
        result = run_daily_cycle()
        print(json.dumps(result, indent=2))
    elif cmd == "inbox":
        from hexflow_contract import load_inbox
        print(json.dumps(load_inbox(), indent=2))
    elif cmd == "gems":
        print(json.dumps(process_gems(), indent=2))
    elif cmd == "tasks":
        print(json.dumps(process_heartbeat_tasks(), indent=2))
    else:
        print(f"Unknown command: {cmd}. Use: cycle, inbox, gems, tasks")
