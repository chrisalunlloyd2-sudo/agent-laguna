#!/usr/bin/env python3
"""
github_integration.py — GitHub issue + discussion integration for Agent Laguna.

Enables the agent to:
  - Create issues from daily tasks (with hounty bounty labels)
  - Comment on existing issues with results
  - List open/closed issues assigned to the agent
  - Update issue labels and status
  - Sync GitHub issues back to heartbeat inbox for processing

Requires: `gh` CLI authenticated (uses the user's PAT via gh credential helper).
Falls back gracefully if gh is unavailable.
"""
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
LAGUNA_DIR = HOME / ".agent_laguna"


def _run_gh(args: list, timeout: int = 30) -> dict:
    """Run a gh CLI command, returning {success, stdout, stderr, returncode}."""
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True, text=True, timeout=timeout,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
        }
    except FileNotFoundError:
        return {"success": False, "stdout": "", "stderr": "gh CLI not found", "returncode": -1}
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "timeout", "returncode": -1}


def gh_auth_status() -> dict:
    """Check if gh CLI is authenticated."""
    return _run_gh(["auth", "status"])


def create_issue(title: str, body: str, labels: list = None, assignee: str = None) -> str:
    """Create a GitHub issue in the agent-laguna repo.

    Returns the issue URL or empty string on failure.
    """
    args = ["issue", "create", "--title", title, "--body", body]
    if labels:
        args += ["--label", ",".join(labels)]
    if assignee:
        args += ["--assignee", assignee]

    result = _run_gh(args, timeout=30)
    if result["success"]:
        return result["stdout"]
    return ""


def comment_on_issue(issue_number: str, body: str) -> bool:
    """Post a comment on an existing GitHub issue."""
    result = _run_gh(["issue", "comment", issue_number, "--body", body])
    return result["success"]


def list_issues(state: str = "open", labels: str = None, assignee: str = None) -> list:
    """List GitHub issues with optional filtering.

    state: 'open', 'closed', or 'all'
    """
    args = ["issue", "list", f"--state={state}"]
    if labels:
        args += [f"--label={labels}"]
    if assignee:
        args += [f"--assignee={assignee}"]
    args += ["--json", "number,title,state,labels,assignees,url"]

    result = _run_gh(args, timeout=15)
    if result["success"]:
        try:
            return json.loads(result["stdout"])
        except json.JSONDecodeError:
            return []
    return []


def close_issue(issue_number: str) -> bool:
    """Close a GitHub issue."""
    result = _run_gh(["issue", "close", issue_number])
    return result["success"]


def add_labels(issue_number: str, labels: list) -> bool:
    """Add labels to an issue."""
    result = _run_gh(["issue", "edit", issue_number, "--add-label", ",".join(labels)])
    return result["success"]


def create_issue_from_task(task: dict, hounty_value: int = 0) -> str:
    """Convert a task manifest into a GitHub issue with hounty label."""
    title = f"[Task] {task.get('id', 'unknown')}"
    body = f"""# Task: {task.get('id', 'unknown')}

**Prompt:**
```
{task.get('prompt', '(no prompt)')[:500]}
```

**Workdir:** {task.get('workdir', '(none)')}

**Deliver:** {task.get('deliver', 'local')}

**Source:** {task.get('source', 'unknown')}

---
*Auto-created by Agent Laguna daily cycle*
_Hounty: {hounty_value} points available_
"""
    labels = ["task", "auto-generated"]
    if hounty_value > 0:
        labels.append(f"hounty-{hounty_value}")

    if task.get("prompt", "").lower().startswith("self-improvement"):
        labels.append("self-improvement")
    elif task.get("source") == "hexflow":
        labels.append("hexflow")

    return create_issue(title, body, labels=labels)


def comment_task_result(issue_number: str, task_id: str, result: str, points: int) -> bool:
    """Post task completion results as a comment on the GitHub issue."""
    body = f"""## Task Complete: {task_id}

**Result:** {result[:500]}

**Hounty Earned:** {points} points

**Completed:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}

*Auto-comment from Agent Laguna*
"""
    return comment_on_issue(issue_number, body)


def sync_issues_to_inbox() -> int:
    """Sync open GitHub issues into the Aegis inbox for processing.

    Creates inbox entries for each open issue with the 'task' label.
    Returns the number of issues synced.
    """
    issues = list_issues(state="open", labels="task")
    inbox_file = HOME / "aegis_qwen_inbox.json"
    inbox = []
    if inbox_file.exists():
        try:
            inbox = json.loads(inbox_file.read_text(encoding="utf-8"))
        except Exception:
            inbox = []

    synced = 0
    for issue in issues:
        # Check if we've already synced this issue
        already_synced = any(
            "ISSUE" in m.get("message", "") and str(issue["number"]) in m.get("message", "")
            for m in inbox
        )
        if not already_synced:
            inbox.append({
                "sender": "agent-laguna",
                "message": f"ISSUE: #{issue['number']} — {issue['title']}",
                "correlation_id": f"issue-{issue['number']}",
            })
            synced += 1

    if synced > 0:
        tmp = inbox_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(inbox, indent=2), encoding="utf-8")
        tmp.replace(inbox_file)

    return synced


def create_discussion(title: str, body: str) -> str:
    """Create a GitHub discussion (if Discussions enabled)."""
    result = _run_gh(["discussion", "create", "--title", title, "--body", body])
    if result["success"]:
        return result["stdout"]
    return ""


def issue_summary() -> dict:
    """Return a summary of GitHub issues."""
    open_issues = list_issues(state="open")
    closed_issues = list_issues(state="closed")
    return {
        "open": len(open_issues),
        "closed": len(closed_issues),
        "total": len(open_issues) + len(closed_issues),
        "recent_open": open_issues[:5],
    }


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "status":
        print(json.dumps(issue_summary(), indent=2))
    elif cmd == "sync":
        count = sync_issues_to_inbox()
        print(f"Synced {count} issues to inbox")
    elif cmd == "create":
        title = sys.argv[2] if len(sys.argv) > 2 else "Test Issue"
        body = sys.argv[3] if len(sys.argv) > 3 else "Created by Agent Laguna"
        url = create_issue(title, body, labels=["auto-generated"])
        print(f"Issue created: {url}")
    elif cmd == "comment":
        num = sys.argv[2] if len(sys.argv) > 2 else "1"
        body = sys.argv[3] if len(sys.argv) > 3 else "Comment from Agent Laguna"
        ok = comment_on_issue(num, body)
        print(f"Comment: {'posted' if ok else 'failed'}")
    else:
        print(f"Usage: python github_integration.py [status|sync|create <title> <body>|comment <num> <body>]")
