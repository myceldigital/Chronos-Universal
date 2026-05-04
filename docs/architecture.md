# Architecture

Chronos Universal is a pure review skill.

```text
history.jsonl + agent_registry.json + dismissals.jsonl
→ review_day.py
→ review.md + plan.json
```

## Boundaries

Chronos never crosses the action boundary. It does not install jobs, trigger sub-agents, create agents, or call external services.

## Components

1. **History reader** — loads normalized JSONL events.
2. **Opportunity detector** — scans for repeated patterns such as commitments, follow-ups, stale work, documentation drift, preparation gaps, and anomalies.
3. **Capability matcher** — compares each opportunity’s required capabilities against installed agents.
4. **Risk classifier** — assigns L0–L5 risk classes.
5. **Ranking engine** — combines evidence frequency, agent fit, estimated value, confidence, false-positive risk, and prior dismissals.
6. **Renderer** — writes a Markdown report and JSON plan.

## Why Plain Files

Plain files make the skill inspectable. A user can read exactly what Chronos saw, what it suggested, and why.

Use a database only after plain JSONL demonstrably fails.
