#!/usr/bin/env python3
"""guider_sweep.py — one guider sweep: burst todos -> RNN prune -> ASCII board for coders.

Sources of burst todos (Chris's idea): hexflow triplets, Chris directives, Alice's own.
Output: sweep_board.txt — the text diagram laguna & glm ingest each hourly sweep.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ascii_flow import render_hexflow, render_board, now_iso
from rnn_pruner import Governor

STATE = "/root/agent-laguna/pruner_state.json"
OUT = "/root/agent-laguna/sweep_board.txt"
SEEDS = "/root/agent-laguna/sweep_seeds.json"  # burst todos appended by lane/chris/alice

def load_seeds():
    if os.path.exists(SEEDS):
        try: return json.load(open(SEEDS))
        except Exception: return []
    return []

def main():
    gov = Governor().load()
    todos = load_seeds()
    verdicts = [gov.observe(t["id"], t.get("salience", 0.5)) for t in todos]
    for t, v in zip(todos, verdicts):
        if v["prune"]: t["lane"] = "PRUNED"
        elif t.get("burst") or t.get("salience", 0) >= 0.6: t["lane"] = "BURST"
        else: t["lane"] = "LANES" if False else "QUEUED"
    gov.save()
    board = render_hexflow(0) + "\n" + render_board(todos)
    header = f"# guider sweep {now_iso()} pruned={sum(v['prune'] for v in verdicts)} zeroed={gov.stats['weights_zeroed_total']}"
    open(OUT, "w").write(header + "\n" + board + "\n# Next: feed this board to qwen-oca / glm-oca task prompts\n")
    print(header); print(board)

if __name__ == "__main__":
    main()
