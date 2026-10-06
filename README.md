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
├── agent.py                    # Main orchestrator — daily loop, phases 0-4
├── hexflow_contract.py         # Hexagonal flow vector processor (shuttle engine)
├── daily_task.py               # Daily personalized task runner
├── self_improve.py             # 1 self-improvement step/day (Scientific Method)
├── hounty.py                   # Reward/point system with streaks + achievements
├── github_integration.py       # GitHub issue/discussion management + heartbeat
├── requirements.txt            # stdlib-only (no external deps)
├── VERSION                     # Version string
├── .gitignore
└── tests/
    └── test_agent.py           # Test suite
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
| GitHub API | Agent's own repo `chrisalunlloyd2-sudo/agent-laguna` | Issue creation, comments, sync |

## Usage

```bash
# Initialize
python agent.py init

# Run one daily cycle
python agent.py daily

# Run continuously (24h interval)
python agent.py loop

# Run in background as a daemon
nohup python3 agent.py loop 24 > ~/.agent_laguna/logs/heartbeat.log 2>&1 &

# Check status
python agent.py status

# GitHub integration commands
python agent.py github summary    # Show issue summary
python agent.py github sync        # Sync open issues to inbox
python agent.py github create <title> <body>  # Create new issue
python agent.py github list        # List open issues

# Direct module usage
python3 hexflow_contract.py cycle    # Run hexflow cycle
python3 daily_task.py cycle          # Run daily task processing
python3 self_improve.py run          # Run self-improvement
python3 hounty.py balance            # Check hounty balance
python3 github_integration.py status  # Check GitHub issue status
python3 github_integration.py sync   # Sync issues to inbox
```

## GitHub Integration

The GitHub heartbeat (Phase 0 + Phase 4 of the daily cycle) enables:

| Feature | Description |
|---------|-------------|
| **Issue Sync** | Open task-labeled issues from GitHub are synced into the Aegis inbox (`aegis_qwen_inbox.json`) |
| **Daily Issues** | Each daily cycle creates a summary issue in `chrisalunlloyd2-sudo/agent-laguna` |
| **Self-Improvement Log** | Self-improvement steps are posted as comments on a tracking issue |
| **Task Issues** | Daily tasks are converted to GitHub issues with hounty labels |
| **Controls** | Close, label, and comment on issues programmatically via `gh` CLI |

**Requirements:** `gh` CLI authenticated (`gh auth status`)

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
│ 0. GitHub Heartbeat                            │
│    → Sync issues to inbox                      │
│    → Create daily summary issue                │
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
│ 4. Hounty Tracking + GitHub Posting             │
│    → Record points earned                       │
│    → Post results to GitHub issues              │
│    → Check for new achievements                 │
└─────────────────────────────────────────────────┘
```

## License

Part of the Kai 9000 / VIPER ecosystem — chrisalunlloyd2-sudo
