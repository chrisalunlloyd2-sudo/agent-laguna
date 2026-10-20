import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from board_contract import ContractViolation, check_dispatch, enforce  # noqa: E402

GOOD = "2026-10-18 sweep: aria-swarm push hounty=deadbeef reviewed by Alice\n"


def _write(tmp_path, new, prev=None):
    p = tmp_path / "CODER_RECEIPTS.md"
    p.write_text(new, encoding="utf-8")
    if prev is not None:
        (tmp_path / "CODER_RECEIPTS.md.prev").write_text(prev, encoding="utf-8")
    return str(p)


def test_clean_cycle_passes(tmp_path):
    rp = _write(tmp_path, GOOD, prev=GOOD)
    rep = check_dispatch({"aria-swarm": 1}, rp)
    assert rep["ok"] is True and rep["violations"] == []


def test_push_overflow_is_violation(tmp_path):
    rp = _write(tmp_path, GOOD, prev=GOOD)
    rep = check_dispatch({"aria-swarm": 2}, rp)
    assert rep["ok"] is False
    assert any(v.startswith("C1") and "aria-swarm" in v for v in rep["violations"])


def test_truncated_receipts_is_violation(tmp_path):
    rp = _write(tmp_path, GOOD[:20], prev=GOOD)
    rep = check_dispatch({"aria-swarm": 1}, rp)
    assert rep["ok"] is False
    assert any(v.startswith("C2") for v in rep["violations"])


def test_missing_hounty_is_violation(tmp_path):
    rp = _write(tmp_path, "2026-10-18 sweep: aria-swarm push reviewed by Alice\n")
    rep = check_dispatch({"aria-swarm": 1}, rp)
    assert rep["ok"] is False
    assert any(v.startswith("C3") for v in rep["violations"])
    # token present but malformed (not hounty=<8 hex>) is equally a violation
    for bad in ("hounty=xyz", "hounty=deadbe", "hounty=deadbeef0"):
        rp = _write(tmp_path, f"sweep: aria-swarm push {bad}\n")
        rep = check_dispatch({"aria-swarm": 1}, rp)
        assert rep["ok"] is False, bad
        assert any(v.startswith("C3") for v in rep["violations"]), bad


def test_enforce_raises(tmp_path):
    rp = _write(tmp_path, GOOD, prev=GOOD)
    try:
        enforce({"aria-swarm": 3}, rp)
    except ContractViolation as exc:
        assert exc.violations
    else:  # pragma: no cover
        raise AssertionError("enforce did not raise")
