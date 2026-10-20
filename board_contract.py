#!/usr/bin/env python3
"""board_contract.py — dispatch contract gate for the guider sweep board.

Enforced before any coder is dispatched (Alice-authored, zero-API):

  C1  at most ONE push per repo per cycle   (repo_heads counts > 1 => violation)
  C2  CODER_RECEIPTS.md is append-only      (new text must start with prior text;
                                             prior snapshot = <receipts_path>.prev)
  C3  every receipt line that names a repo carries a hounty token
      `hounty=<8 hex>` so a receipt can be traced to a commit.

Pure stdlib, deterministic, no network, no git side effects.
"""
from __future__ import annotations

import os
import re
from typing import Dict, List

HCOUNTY_RE = re.compile(r"hounty=[0-9a-f]{8}\b")


class ContractViolation(Exception):
    """Raised when the caller asks the gate to hard-fail instead of returning a report."""

    def __init__(self, violations: List[str]):
        self.violations = list(violations)
        super().__init__("; ".join(self.violations))


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except FileNotFoundError:
        return ""


def _repo_tokens(repo_heads: Dict[str, int]) -> List[str]:
    """Short repo names used to decide which receipt lines are repo-bearing."""
    toks = []
    for name in repo_heads:
        base = name.rstrip("/").split("/")[-1]
        if base.endswith(".git"):
            base = base[:-4]
        if base:
            toks.append(base.lower())
    return sorted(set(toks), key=len, reverse=True)


def check_dispatch(repo_heads: Dict[str, int], receipts_path: str) -> Dict[str, object]:
    """Return {"ok": bool, "violations": [str]} for one sweep cycle.

    repo_heads  : mapping repo -> number of pushes attempted this cycle
    receipts_path: path to CODER_RECEIPTS.md
    """
    violations: List[str] = []

    # C1 — one push per repo per cycle
    for repo in sorted(repo_heads):
        try:
            n = int(repo_heads[repo])
        except (TypeError, ValueError):
            violations.append(f"C1 {repo}: push count is not an integer")
            continue
        if n > 1:
            violations.append(f"C1 {repo}: {n} pushes in one cycle (max 1)")

    cur = _read(receipts_path)
    prev = _read(receipts_path + ".prev")

    # C2 — append-only receipts
    if prev and not cur.startswith(prev):
        violations.append("C2 CODER_RECEIPTS.md: receipts were rewritten, not appended")

    # C3 — hounty traceability on repo-bearing lines
    toks = _repo_tokens(repo_heads)
    if toks:
        for lineno, line in enumerate(cur.splitlines(), 1):
            low = line.lower()
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if any(t in low for t in toks) and not HCOUNTY_RE.search(low):
                violations.append(f"C3 line {lineno}: repo receipt missing hounty=<8 hex>")

    return {"ok": not violations, "violations": violations}


def enforce(repo_heads: Dict[str, int], receipts_path: str) -> Dict[str, object]:
    """Same as check_dispatch but raises ContractViolation on failure."""
    report = check_dispatch(repo_heads, receipts_path)
    if not report["ok"]:
        raise ContractViolation(report["violations"])  # type: ignore[arg-type]
    return report


if __name__ == "__main__":  # tiny CLI for the sweep step
    import json
    import sys

    heads = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "CODER_RECEIPTS.md"
    )
    print(json.dumps(check_dispatch(heads, path), indent=1))
