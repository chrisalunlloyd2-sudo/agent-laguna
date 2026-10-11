#!/usr/bin/env python3
"""ascii_flow.py — ASCII steering diagrams for text-only models (laguna is text, not vision).

Renders the hexflow pipeline + todo board as deterministic ASCII the small
coder can ingest each sweep. Parse(board) restores state — text in, text out.

Format (stable golden):
  [INGEST]==>[SYNTH]==>[RESOLVE]==>[MUTATE]==>[VERIFY]==>[COMMIT]
  BOARD v1
  | QUEUED  | T042 hexflow:aria shuttle triplets   s=0.82 src=hexflow
  | BURST   | T041 kai CHANGELOG drift              s=0.91 src=alice
  | PRUNED  | T039 old gists fetch                  s=0.04 src=chris
  | DONE    | T038 py_compile sweep                 s=1.00 src=glm
"""
import re
from datetime import datetime, timezone

PHASES = ["INGEST", "SYNTH", "RESOLVE", "MUTATE", "VERIFY", "COMMIT"]
LANES = ["QUEUED", "BURST", "PRUNED", "DONE"]
_HEADER = re.compile(r"^BOARD v1$")
_ROW = re.compile(r"^\| ([A-Z]+)\s+\| ([A-Z]\d+) (.+?)\s+s=([\d.]+) src=(\w+)$")

def render_todo(tid, text, lane, salience, source):
    return "| %-8s| %s %s" % (lane + " ", tid, f"{text} s={salience:.2f} src={source}")

def render_hexflow(phase_index):
    arrows = ["==>"] * (len(PHASES) - 1)
    parts = []
    for i, p in enumerate(PHASES):
        parts.append("[%s]" % p)
        if i < len(arrows):
            parts.append(arrows[i])
    return "".join(parts)

def render_board(todos):
    """todos: list of dicts {id,text,lane,salience,source}. Deterministic order."""
    lines = ["BOARD v1"]
    for lane in LANES:
        for t in sorted([t for t in todos if t["lane"] == lane],
                        key=lambda t: (-t["salience"], t["id"])):
            lines.append("| %-8s| %s %s s=%.2f src=%s" % (lane, t["id"], t["text"], t["salience"], t["source"]))
    return "\n".join(lines)

def parse_board(board_text):
    todos = []
    phase = None
    for line in board_text.splitlines():
        line = line.rstrip()
        if line.startswith("[") and line.endswith("]") and "]==>" not in line and line[1:-1] in PHASES:
            phase = line[1:-1]
        elif not _HEADER.match(line) and _ROW.match(line):
            lane, tid, text, s, src = _ROW.match(line).groups()
            todos.append({"id": tid, "text": text.strip(), "lane": lane, "salience": float(s), "source": src})
    return todos, phase

def hexflow_advance(todos, current_phase):
    """Hexflow walk: move all DONE-salience items one phase if phase == VERIFY gate."""
    i = PHASES.index(current_phase)
    return PHASES[min(i + 1, len(PHASES) - 1)], todos

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

if __name__ == "__main__":
    demo = [
        {"id": "T001", "text": "aria changelog drift", "lane": "QUEUED", "salience": 0.8, "source": "hexflow"},
        {"id": "T002", "text": "kai py_compile", "lane": "BURST", "salience": 0.9, "source": "alice"},
        {"id": "T003", "text": "stale gist fetch", "lane": "PRUNED", "salience": 0.05, "source": "chris"},
    ]
    b = render_board(demo)
    print(render_hexflow(0))
    print(b)
    back, ph = parse_board(b)
    assert len(back) == 3 and ph is None
    print("ROUNDTRIP OK " + now_iso())
