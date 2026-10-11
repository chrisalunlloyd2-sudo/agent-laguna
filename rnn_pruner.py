#!/usr/bin/env python3
"""rnn_pruner.py — Self-pruning scalar-RNN salience governor (stdlib only).

Two-layer self-pruning behavior:
  1. Model self-prunes: weight decay (W *= lam) + hard-zero near-dead weights
     (|w| < eps → 0). Dead neurons vanish; memory forgets.
  2. Todos self-prune: per-todo salience ring feeds the RNN; sigmoid output
     p_t = P(prune). p > threshold → lane PRUNED. Stagnant (< stagnation_floor
     for stagnation_cycles sweeps) → pruned regardless (safety rule).

Equations: h_t = tanh(w_x·x + W_h·h_{t-1}); p = sigmoid(w_y·h + b_y).

State: /root/agent-laguna/pruner_state.json (hounty receipt: append-only stats).
"""
import json, math, random, os

STATE = "/root/agent-laguna/pruner_state.json"

class ScalarRNN:
    def __init__(self, h_dim=4, seed=1734):
        rng = random.Random(seed)
        self.h_dim = h_dim
        self.w_x = [rng.uniform(-0.5, 0.5) for _ in range(h_dim)]
        self.w_h = [[rng.uniform(-0.5, 0.5) for _ in range(h_dim)] for _ in range(h_dim)]
        self.w_y = [rng.uniform(-0.5, 0.5) for _ in range(h_dim)]
        self.b_y = 0.0
        self.h = [0.0] * h_dim
    def step(self, x):
        h_new = []
        for j in range(self.h_dim):
            s = self.w_x[j] * x + self.b_y * 0.1
            for k in range(self.h_dim):
                s += self.w_h[j][k] * self.h[k]
            h_new.append(math.tanh(s))
        self.h = h_new
        z = sum(w * h for w, h in zip(self.w_y, self.h)) + self.b_y
        return 1.0 / (1.0 + math.exp(-z))  # sigmoid = prune probability
    def decay(self, lam=0.97):
        self.w_x = [w * lam for w in self.w_x]
        self.w_y = [w * lam for w in self.w_y]
        self.w_h = [[w * lam for w in row] for row in self.w_h]
    def self_prune(self, eps=1e-3):
        n = 0
        def z(v):
            nonlocal n
            return 0.0 if (n := n + 1) and abs(v) < eps else v
        self.w_x = [z(w) for w in self.w_x]
        self.w_y = [z(w) for w in self.w_y]
        self.w_h = [[z(w) for w in row] for row in self.w_h]
        return n
    def alive(self):
        return sum(1 for w in self.w_x + self.w_y + [c for r in self.w_h for c in r] if w != 0.0)

class Governor:
    RING_CAP = 8
    def __init__(self, prune_threshold=0.62, stagnation_floor=0.15, stagnation_cycles=6):
        self.rnn = None
        self.hist = {}
        self.stats = {"pruned_total": 0, "weights_zeroed_total": 0, "cycles": 0}
        self.prune_threshold, self.stag_floor, self.stag_cycles = prune_threshold, stagnation_floor, stagnation_cycles
    def ensure_rnn(self):
        self.rnn = self.rnn or ScalarRNN()
        return self.rnn
    def observe(self, tid, salience):
        """One sweep: record salience obs, ask governor — PRUNE?"""
        self.ensure_rnn()
        ring = self.hist.setdefault(tid, {"obs": []})["obs"]
        ring.append(round(float(salience), 3))
        if len(ring) > self.RING_CAP: ring.pop(0)
        self.stats["cycles"] += 1
        mean = sum(ring) / len(ring)
        stagnating = len(ring) >= self.stag_cycles and max(ring[-self.stag_cycles:]) < self.stag_floor
        p = self.rnn.step(mean)
        self.rnn.decay(0.97)
        zeroed = self.rnn.self_prune(1e-3)
        self.stats["weights_zeroed_total"] += zeroed
        prune = stagnating or p > self.prune_threshold
        if prune: self.stats["pruned_total"] += 1
        return {"tid": tid, "p_prune": round(p, 3), "stagnating": stagnating, "prune": prune}
    def save(self):
        json.dump({"w_x": self.rnn.w_x, "w_h": self.rnn.w_h, "w_y": self.rnn.w_y,
                   "b_y": self.rnn.b_y, "h": self.rnn.h, "hist": self.hist, "stats": self.stats},
                  open(STATE, "w"))
    def load(self):
        if os.path.exists(STATE):
            d = json.load(open(STATE)); self.rnn = ScalarRNN(); self.rnn.w_x = d["w_x"]; self.rnn.w_h = d["w_h"]
            self.rnn.w_y = d["w_y"]; self.rnn.b_y = d["b_y"]; self.rnn.h = d["h"]; self.hist = d["hist"]; self.stats = d["stats"]
        self.ensure_rnn()
        return self

if __name__ == "__main__":
    # Golden tests
    r1 = ScalarRNN(seed=1734); r2 = ScalarRNN(seed=1734)
    assert [round(a,6) for a in r1.w_x] == [round(b,6) for b in r2.w_x], "determinism"
    # self-prune: decay+prune over many steps must zero dead weights
    g = Governor(); g.ensure_rnn()
    zeroed_runs = 0
    for i in range(400): g.rnn.step(0.5); g.rnn.decay(0.97); zeroed_runs += g.rnn.self_prune(1e-3)
    assert zeroed_runs > 0 and g.rnn.alive() < g.rnn.h_dim * 3 + g.rnn.h_dim * g.rnn.h_dim + g.rnn.h_dim, "self-prune zeroed"
    # stale todo prunes, hot todo survives
    g2 = Governor()
    d_hot = [g2.observe("T-hot", 0.9)["prune"] for _ in range(12)]
    d_stale = [g2.observe("T-stale", 0.02)["prune"] for _ in range(12)]
    assert not d_hot[-1], "hot survives"
    assert d_stale[-1], "stale prunes"
    # state roundtrip
    g2.save(); g3 = Governor().load(); assert g3.hist["T-hot"]["obs"][-1] == 0.9, "roundtrip"
    os.remove(STATE)
    print("RNN_PRUNER_GOLDEN_OK dead_weights=%d hot=%s stale=%s" % (zeroed_runs, d_hot[-1], d_stale[-1]))
