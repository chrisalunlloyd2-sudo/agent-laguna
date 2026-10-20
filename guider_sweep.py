#!/usr/bin/env python3
"""guider_sweep.py — one guider sweep: burst todos -> RNN prune -> ASCII board for coders.

Sources of burst todos (Chris's idea): hexflow triplets, Chris directives, Alice's own.
Output: sweep_board.txt — the text diagram laguna & glm ingest each hourly sweep.
"""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ascii_flow import render_hexflow, render_board, now_iso
from rnn_pruner import Governor

STATE = "/root/agent-laguna/pruner_state.json"
OUT = "/root/agent-laguna/sweep_board.txt"
SEEDS = "/root/agent-laguna/sweep_seeds.json"  # burst todos appended by lane/chris/alice

TEXT_KEYS = ("text", "label", "title", "desc", "task", "what")

def normalize_seed(t):
    """Seed schema tolerance: accept title/desc/task as the board-visible text.

    Root class of the 2026-10-19 sweep crash: render_board() indexes t["text"]
    while seeds written by chris/alice lanes used t["title"] -> KeyError killed
    the whole sweep after the governor had already been observed. Normalise at
    the boundary so every downstream consumer sees one shape.
    """
    if not isinstance(t, dict):
        return None
    # Seeds written with the sweep-spec key "tid" (Chris's prompt template) were
    # silently dropped by the old `"id" not in t` guard -> empty board, every hour.
    if "id" not in t and isinstance(t.get("tid"), str) and t["tid"].strip():
        t = dict(t, id=t["tid"].strip())
    if "id" not in t:
        return None
    n = dict(t)
    for k in TEXT_KEYS:
        v = n.get(k)
        if isinstance(v, str) and v.strip():
            n["text"] = v.strip()
            break
    n.setdefault("text", str(n["id"]))
    if "source" not in n and "src" in n:
        n["source"] = n["src"]
    n.setdefault("source", "?")
    try:
        n["salience"] = float(n.get("salience", 0.5))
    except (TypeError, ValueError):
        n["salience"] = 0.5
    return n

def load_seeds():
    if os.path.exists(SEEDS):
        try:
            d = json.load(open(SEEDS))
            if isinstance(d, dict):
                d = d.get("seeds") or d.get("todos") or []
            out = [normalize_seed(t) for t in d]
            return [t for t in out if t]
        except Exception: return []
    return []

def write_seeds_atomic(path, seeds):
    """Atomic write of seeds JSON via tempfile + os.replace.

    A crash mid-write leaves the previous file intact (os.replace is
    atomic on POSIX) instead of a torn blob that load_seeds silently
    swallows to [].
    """
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".sweep_seeds_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(seeds, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

def main():
    gov = Governor().load()
    todos = load_seeds()
    verdicts = [gov.observe(t["id"], t.get("salience", 0.5)) for t in todos]
    for t, v in zip(todos, verdicts):
        if v["prune"]: t["lane"] = "PRUNED"
        elif t.get("burst") or t.get("salience", 0) >= 0.6: t["lane"] = "BURST"
        elif t.get("salience", 0) >= 0.45: t["lane"] = "LANES"
        else: t["lane"] = "QUEUED"
    gov.save()
    board = render_hexflow(0) + "\n" + render_board(todos)
    header = f"# guider sweep {now_iso()} pruned={sum(v['prune'] for v in verdicts)} zeroed={gov.stats['weights_zeroed_total']}"
    open(OUT, "w").write(header + "\n" + board + "\n# Next: feed this board to qwen-oca / glm-oca task prompts\n")
    print(header); print(board)

if __name__ == "__main__":
    main()
