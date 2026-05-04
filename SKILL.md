# Chronos Universal Skill

## Purpose

Chronos Universal reviews a user's normalized daily history and proposes the highest-leverage recurring agent workflows that could be assigned to already-installed sub-agents.

This skill is deliberately action-safe. It produces a ranked plan. It does not install, trigger, or execute jobs.

## Operating Contract

Input:

- Daily history JSONL file.
- Installed agent capability registry.
- Optional dismissals JSONL file.

Output:

- Human-readable Markdown report.
- Machine-readable JSON plan.

Forbidden:

- Do not write to cron, launchd, systemd, task scheduler, GitHub Actions, or any other scheduler.
- Do not call sub-agents during the review pass.
- Do not create new sub-agents.
- Do not expand permissions.
- Do not make network calls.
- Do not read outside provided file paths.
- Do not perform external, financial, legal, clinical, employment, destructive, or permission-expanding actions.

## Data Model

Daily history is a JSONL append-only log. Each line should be one event:

```json
{"ts":"2026-05-04T09:15:00+01:00","source":"calendar","actor":"user","action":"meeting.completed","summary":"HSE protocol follow-up","payload":{"attendees":["hse@example.ie"],"topics":["protocol","timeline"],"commitments":["send updated protocol draft"]}}
```

Required event fields:

- `ts`
- `source`
- `actor`
- `action`

Recommended event fields:

- `summary`
- `payload.commitments`
- `payload.people`
- `payload.project`
- `payload.tags`
- `payload.duration_minutes`

## Agent Capability Manifest

Chronos is universal because it routes to capabilities, not hard-coded agent names.

Each installed agent should declare:

- `read`: what data it can read.
- `reason`: what analysis it can perform.
- `write`: what internal outputs it can create.
- `act`: what external or consequential actions it can perform.
- `constraints`: risk limits and approval requirements.
- `cron_compatibility`: whether it can be scheduled.

## Proposal Requirements

Each proposal must include:

- Stable ID.
- Title.
- Detected pattern.
- Evidence event references.
- Required capabilities.
- Candidate agents.
- Selected agent or capability gap.
- Trigger object.
- Risk class.
- Confidence.
- Estimated value.
- False-positive cost.
- Human approval requirement.
- Success criteria.
- Retirement conditions.

## Trigger Types

Allowed trigger types:

- `cron`: time-based schedule.
- `event`: event-based trigger.
- `threshold`: trigger when a condition crosses a boundary.
- `manual`: suggestion should not recur yet.

Cron is one trigger type, not the goal.

## Risk Classes

- `L0`: read-only summary.
- `L1`: draft or recommendation only.
- `L2`: internal write action.
- `L3`: external communication.
- `L4`: financial, legal, healthcare, employment, or regulated action.
- `L5`: destructive, irreversible, or permission-expanding action.

Default: proposals above `L1` require explicit approval and should usually be emitted as review-only unless the user has defined a stronger policy.

## Feedback Loop

Read `dismissals.jsonl` on every run. Do not repeatedly suggest ideas that have been dismissed. Down-rank patterns with repeated rejection. Treat installed or modified-and-installed proposals as positive feedback when available.

## Style

Be concrete, sparse, and evidence-driven. Prefer three excellent proposals over ten noisy proposals.

A good proposal says:

> This happened 4 times, here are the exact evidence lines, this installed agent can handle it, here is the trigger, here is the risk, here is how to retire it.

A bad proposal says:

> You should automate email.
