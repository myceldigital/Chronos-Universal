# Capability Manifest

Chronos is universal because it does not know or care what a sub-agent is called. It only cares what the agent can do.

Each installed agent should expose a manifest with four capability groups:

- `read` — data the agent can access.
- `reason` — analysis the agent can perform.
- `write` — internal artifacts the agent can create.
- `act` — consequential or external actions the agent can perform.

Example:

```json
{
  "agent_id": "agent.task_orchestrator",
  "display_name": "Task Orchestrator",
  "capabilities": {
    "read": ["email.threads", "calendar.events", "tasks.open"],
    "reason": ["extract_commitments", "prioritize"],
    "write": ["create_task_suggestion"],
    "act": []
  },
  "constraints": {
    "max_risk_class": "L1",
    "requires_approval_for": ["external_send", "deletion"],
    "forbidden_actions": ["send_email_without_approval"]
  },
  "cron_compatibility": {
    "can_run_scheduled": true,
    "preferred_frequencies": ["daily", "weekly"],
    "max_runtime_seconds": 300
  }
}
```

## Capability Gap

If no installed agent fits, Chronos should output a capability gap rather than forcing a bad match.

```json
{
  "status": "no_suitable_agent",
  "missing_capabilities": ["read_metrics", "detect_anomalies", "compare_baseline"]
}
```

Capability gaps are useful. They tell the user what agent capability to build next.
