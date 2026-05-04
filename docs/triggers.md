# Triggers

Chronos is not cron-only. Cron is one trigger type.

## Supported Trigger Types

### `cron`

Time-based schedule.

Good for:

- Daily reviews
- Weekly cleanup
- Monthly retrospectives
- Morning briefings

Example:

```json
{"type":"cron","expression":"10 18 * * 1-5","human_readable":"Weekdays at 18:10"}
```

### `event`

Runs when a meaningful event occurs.

Good for:

- A calendar event starts soon
- A document lands in a folder
- A thread receives no reply for a period
- A repository receives a release or issue

Example:

```json
{"type":"event","event":"calendar.event.starts_in_2_hours","human_readable":"When a calendar event starts within 2 hours"}
```

### `threshold`

Runs when a count, age, score, or metric crosses a boundary.

Good for:

- More than 10 unresolved messages
- Anomaly score above threshold
- Task age over 14 days

Example:

```json
{"type":"threshold","condition":"anomaly_score > configured_threshold","human_readable":"When an operational signal crosses a configured anomaly threshold"}
```

### `manual`

No recurrence yet. Use when the proposal is promising but unsafe, under-specified, or not yet proven.

## V1 Policy

V1 may emit event and threshold triggers, but it does not install them. A separate apply-plan skill or human installer decides how to map the trigger into the user's runtime.
