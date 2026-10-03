# Agent Laguna

Autonomous daily agent for the Kai 9000 / VIPER ecosystem.

> *"Agent Laguna — dipped your toe in the lagoon, now dive in."*

## What is Agent Laguna?

Agent Laguna is a stdlib-only Python agent that runs daily cycles, processing:

1. **Hexflow Contracts** — Connects to the ARIA shuttle engine's hexagonal flow vector (INGEST → SYNTH → RESOLVE → MUTATE → VERIFY → COMMIT), reading priority triplets and inbox actions
2. **Daily Tasks** — Processes inbox instructions (FETCH gists, ISSUE creation), harvests gem snippets, and executes heartbeat task manifests
3. **Self-Improvement** — Runs exactly 1 improvement step per day using the VIPER Scientific Method (MEASURE → HYPOTHESISE → CHANGE ONE → MEASURE → COMPARE → KEEP/REVERT → REDO)
4. **Hounty System** — Earns "hounty" (honey+bounty) points for completed work, tracks streaks, and unlocks achievements

## Architecture

```
agent-laguna/
├── agent.py              # Main orchestrator — daily loop, phases 1-4
├── hexflow_contract.py   # Hexagonal flow vector processor (shuttle engine integration)
├── daily_task.py         # Daily personalized task runner
├── self_improve.py       # 1 self-improvement step/day (Scientific Method)
├── hounty.py             # Reward/point system with streaks + achievements
├── requirements.txt      # stdlib-only (no external deps)
├── VERSION               # Version string
├── .gitignore
└── tests/
    └── test_agent.py     # Test suite
```

## Integration Points

| Component | File | Integration |
|-----------|------|-------------|
| ARIA Shuttle | `~/.aria/SHUTTLE.json` | Reads hex_stage, active_task, step_queue |
| Priority Triplets | `~/opt/aria/spool/priority_triplets.json` | Task source for hexflow |
| Aegis Inbox | `~/aegis_qwen_inbox.json` | FETCH/ACTION messages |
| Gem Library | `~/.matrix_ide/gem_library/` | Snippet harvesting |
| Heartbeat Tasks | `~/heartbeat/tasks/*.task` | NOVA_JOB task manifests |
| Gist Contents | `~/gist_contents/` | Fetched gist storage |

## Usage

```bash
# Initialize
python agent.py init

# Run one daily cycle
python agent.py daily

# Run continuously (24h interval)
python agent.py loop

# Check status
python agent.py status

# Run tests
python -m pytest tests/ -v
```

## Hounty Awards

| Action | Points |
|--------|--------|
| hexflow_step | 5 |
| hexflow_commit | 50 |
| task_complete | 25 |
| task_personalize | 10 |
| self_improve | 30 |
| gist_fetch | 15 |
| issue_create | 20 |
| daily_streak | 10 per day |

## Achievements

- **first_drop** — First 10 points
- **honey_pot** — 100 points
- **golden_streak** — 10 day streak
- **hex_master** — 5 hexflow commits
- **self_evolved** — 10 self-improvement steps
- **fleet_commander** — 20 tasks completed
- **legendary** — 1000 points

## Daily Cycle Flow

```
┌─────────────────────────────────────────────────┐
│ Agent Laguna Daily Cycle                        │
├─────────────────────────────────────────────────┤
│ 1. Hexflow Contract Processing                  │
│    → Load SHUTTLE.json                          │
│    → Process active task through hex stages     │
│    → Award hounty for stage progress            │
├─────────────────────────────────────────────────┤
│ 2. Daily Task Execution                         │
│    → Process inbox actions (FETCH, ISSUE)       │
│    → Harvest gem snippets                       │
│    → Scan heartbeat tasks                       │
│    → Personalize tasks (date-based adaptation)  │
├─────────────────────────────────────────────────┤
│ 3. Self-Improvement                             │
│    → MEASURE baseline                           │
│    → HYPOTHESISE improvement                    │
│    → CHANGE ONE variable                        │
│    → MEASURE result                             │
│    → COMPARE + KEEP/REVERT                     │
│    → REDO if not satisfied                      │
├─────────────────────────────────────────────────┤
│ 4. Hounty Tracking                              │
│    → Record points earned                       │
│    → Check for new achievements                 │
│    → Persist daily result                       │
└─────────────────────────────────────────────────┘
```

## License

Part of the Kai 9000 / VIPER ecosystem — chrisalunlloyd2-sudo
