#!/usr/bin/env python3
"""pacer.py — free-tier pacing governor for coder APIs (stdlib only).

Why: OpenRouter :free models share ONE account-level daily pool; unthrottled
sweeps freeze the account (429 storms). VIPER area: resource_efficiency.
Gates: daily budget/account, min gap between drives, 429 cooldown, and
allow_tokens (Chris's "press 1" = +1 emergency drive, minted by Alice on his word).
CLI: reserve|allow|penalty|status [account] [--test]
"""
import json, os, sys, time
from datetime import datetime, timezone

DEFAULT_CONFIG = {"openrouter": {"daily": 40, "min_gap_s": 90}, "ollama": {"daily": 200, "min_gap_s": 30}}
CONFIG = "/root/agent-laguna/pacer.json"
STATE = "/root/agent-laguna/pacer_state.json"

def _utcday(ts): return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y%m%d")

class Pacer:
    def __init__(self, config=None, state_path=STATE, now_fn=time.time):
        self.cfg = config if config is not None else self._load_config()
        self.state_path = state_path; self.now = now_fn; self.state = self._load_state()
    def _load_config(self):
        if os.path.exists(CONFIG):
            try: return json.load(open(CONFIG))
            except Exception: pass
        return json.loads(json.dumps(DEFAULT_CONFIG))
    def _load_state(self):
        if os.path.exists(self.state_path):
            try: return json.load(open(self.state_path))
            except Exception: pass
        return {}
    def _acct(self, a):
        s = self.state.setdefault(a, {"date": _utcday(self.now()), "used": 0, "extra": 0, "last_ts": 0, "cooldown_until": 0})
        if s["date"] != _utcday(self.now()):  # UTC rollover = fresh pool (matches OpenRouter reset)
            s.update({"date": _utcday(self.now()), "used": 0, "extra": 0, "last_ts": 0, "cooldown_until": 0})
        return s
    def reserve(self, account):
        c = self.cfg.get(account) or {"daily": 100, "min_gap_s": 60}
        s = self._acct(account); t = self.now()
        if t < s.get("cooldown_until", 0): return False, "PACED COOLDOWN %ds" % int(s["cooldown_until"] - t)
        gap = c.get("min_gap_s", 60)
        if s.get("last_ts", 0) and t - s["last_ts"] < gap: return False, "PACED GAP %d<%ds" % (int(t - s["last_ts"]), gap)
        budget = c.get("daily", 100) + s.get("extra", 0)
        if s["used"] >= budget: return False, "PACED BUDGET %d/%d" % (s["used"], budget)
        s["used"] += 1; s["last_ts"] = t; self._save()
        return True, "RESERVED %s %d/%d" % (account, s["used"], budget)
    def allow(self, account):
        s = self._acct(account); s["extra"] = s.get("extra", 0) + 1; self._save()
        return True, "ALLOWED %s +1 (pool now %d)" % (account, self.cfg.get(account, {}).get("daily", 100) + s["extra"])
    def penalty(self, account, cooldown_s=600):
        s = self._acct(account); s["cooldown_until"] = self.now() + cooldown_s; self._save()
        return True, "COOLDOWN %s %ds" % (account, cooldown_s)
    def _save(self): json.dump(self.state, open(self.state_path, "w"), indent=1)
    def status(self, account=None):
        accts = [account] if account else list(self.cfg.keys()); out = []
        for a in accts:
            s = self._acct(a); c = self.cfg.get(a) or {}
            out.append("%s %d/%d+%d gap=%ds" % (a, s["used"], c.get("daily", 100), s.get("extra", 0), c.get("min_gap_s", 60)))
        return " | ".join(out)

def _selftest():
    import tempfile
    d = tempfile.mkdtemp(); t = [1000000.0]
    cfg = {"openrouter": {"daily": 2, "min_gap_s": 0}, "ollama": {"daily": 1, "min_gap_s": 0}}
    p = Pacer(config=cfg, state_path=os.path.join(d, "s.json"), now_fn=lambda: t[0])
    assert p.reserve("openrouter")[0] and p.reserve("openrouter")[0]
    ok, m = p.reserve("openrouter"); assert not ok and "BUDGET" in m
    p.allow("openrouter"); ok, m = p.reserve("openrouter"); assert ok and "3/3" in m
    ok, m = p.reserve("openrouter"); assert not ok and "BUDGET" in m
    t[0] += 86400.0; ok, m = p.reserve("openrouter"); assert ok and "1/2" in m, m  # rollover resets
    t2 = [1000000.0]; cfg2 = {"openrouter": {"daily": 5, "min_gap_s": 90}}
    p2 = Pacer(config=cfg2, state_path=os.path.join(d, "s2.json"), now_fn=lambda: t2[0])
    assert p2.reserve("openrouter")[0]
    ok, m = p2.reserve("openrouter"); assert not ok and "GAP" in m
    t2[0] += 120.0; assert p2.reserve("openrouter")[0]
    p2.penalty("openrouter", 600); t2[0] += 120.0
    ok, m = p2.reserve("openrouter"); assert not ok and "COOLDOWN" in m
    t2[0] += 600.0; assert p2.reserve("openrouter")[0]
    print("PACER_GOLDEN_OK")

if __name__ == "__main__":
    if "--test" in sys.argv: _selftest(); sys.exit(0)
    a = sys.argv[1] if len(sys.argv) > 1 else "status"
    acct = sys.argv[2] if len(sys.argv) > 2 else "openrouter"
    ok, msg = True, ""
    if a == "reserve": ok, msg = Pacer().reserve(acct)
    elif a == "allow": ok, msg = Pacer().allow(acct)
    elif a == "penalty": ok, msg = Pacer().penalty(acct, int(sys.argv[3]) if len(sys.argv) > 3 else 600)
    else: print(Pacer().status(None if a == "status" else acct)); sys.exit(0)
    print(msg); sys.exit(0 if ok else 75)
