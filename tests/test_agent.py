#!/usr/bin/env python3
"""Tests for Agent Laguna."""
import json
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import hounty
import self_improve
import hexflow_contract
import daily_task
import github_integration as gh


def _reset_hounty():
    """Reset hounty state to a clean temp directory."""
    import tempfile
    tmpdir = tempfile.mkdtemp()
    hounty.LAGUNA_DIR = Path(tmpdir) / "agent_laguna"
    hounty.HOUNTY_FILE = hounty.LAGUNA_DIR / "hounty.json"
    hounty.DAILY_LOG = hounty.LAGUNA_DIR / "daily_ledger.jsonl"


def test_hounty_award():
    """Test that hounty points are awarded correctly."""
    _reset_hounty()
    state = hounty.award(10, "test award", "test")
    # Includes streak bonus for first day: 10 base + 10 streak = 20
    assert state["total_points"] == 20
    assert len(state["ledger"]) == 1
    print("✓ test_hounty_award passed")


def test_hounty_balance():
    """Test hounty balance calculation."""
    _reset_hounty()
    hounty.award(25, "task", "task")
    bal = hounty.balance()
    # Includes streak bonus: 25 base + 10 streak = 35
    assert bal["total_points"] == 35
    assert bal["ledger_entries"] == 1
    print("✓ test_hounty_balance passed")


def test_self_improvement_once_per_day():
    """Test that self-improvement only runs once per day."""
    import tempfile
    tmpdir = tempfile.mkdtemp()
    self_improve.LAGUNA_DIR = Path(tmpdir) / "agent_laguna"
    self_improve.IMPROVE_LOG = self_improve.LAGUNA_DIR / "self_improve.jsonl"

    result = self_improve.execute_self_improvement()
    assert result.get("verdict") in ("KEEP", "REVERT")
    assert result.get("scientific_method_pass") is True

    # Second call should be blocked
    result2 = self_improve.execute_self_improvement()
    assert result2.get("status") == "already_done"
    print("✓ test_self_improvement_once_per_day passed")


def test_hexflow_stages():
    """Test hexflow stage transitions."""
    assert hexflow_contract.next_stage("INGEST") == "SYNTH"
    assert hexflow_contract.next_stage("COMMIT") == "INGEST"
    assert hexflow_contract.next_stage("INGEST", "FORWARD") == "SYNTH"
    print("✓ test_hexflow_stages passed")


def test_hexflow_validate_contract():
    """Test contract validation."""
    valid = {"once": True, "summary_line": "test"}
    invalid = {"once": True}
    assert hexflow_contract.validate_contract(valid) is True
    assert hexflow_contract.validate_contract(invalid) is False
    print("✓ test_hexflow_validate_contract passed")


def test_gem_classification():
    """Test gem snippet classification."""
    assert daily_task._classify_gem("import subprocess\ncmd()") == "shell_command"
    assert daily_task._classify_gem("git add -A") == "git_command"
    assert daily_task._classify_gem("def foo(): pass") == "code_function"
    assert daily_task._classify_gem("class Foo: pass") == "code_class"
    print("✓ test_gem_classification passed")


def test_hounty_achievements():
    """Test achievement unlocking."""
    _reset_hounty()
    # Award enough for first_drop achievement (need >= 10 total points)
    hounty.award(10, "test", "test")
    bal = hounty.balance()
    ach_names = [a["name"] for a in bal["achievements"]]
    assert "first_drop" in ach_names
    print("✓ test_hounty_achievements passed")


def test_daily_task_cycle():
    """Test that daily task cycle runs without errors."""
    import tempfile
    tmpdir = tempfile.mkdtemp()
    laguna_dir = Path(tmpdir) / "agent_laguna"
    hounty.LAGUNA_DIR = laguna_dir
    hounty.HOUNTY_FILE = laguna_dir / "hounty.json"
    hounty.DAILY_LOG = laguna_dir / "daily_ledger.jsonl"
    self_improve.LAGUNA_DIR = laguna_dir
    self_improve.IMPROVE_LOG = laguna_dir / "self_improve.jsonl"
    daily_task.LAGUNA_DIR = laguna_dir
    hexflow_contract.HISTORY_DIR = laguna_dir / "hex_history"

    # Should not crash with empty inbox/gems/tasks
    result = daily_task.run_daily_cycle()
    assert "date" in result
    assert "completed" in result
    print("✓ test_daily_task_cycle passed")


def test_github_integration_import():
    """Test that GitHub integration module imports and has expected functions."""
    assert hasattr(gh, "create_issue")
    assert hasattr(gh, "comment_on_issue")
    assert hasattr(gh, "list_issues")
    assert hasattr(gh, "close_issue")
    assert hasattr(gh, "sync_issues_to_inbox")
    assert hasattr(gh, "create_issue_from_task")
    assert hasattr(gh, "issue_summary")
    print("✓ test_github_integration_import passed")


if __name__ == "__main__":
    test_hounty_award()
    test_hounty_balance()
    test_self_improvement_once_per_day()
    test_hexflow_stages()
    test_hexflow_validate_contract()
    test_gem_classification()
    test_hounty_achievements()
    test_daily_task_cycle()
    test_github_integration_import()
    print("\n✅ All tests passed!")
