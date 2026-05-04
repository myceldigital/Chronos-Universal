# Contributing

Chronos Universal should stay small, inspectable, and action-safe.

## Principles

- Prefer plain files over infrastructure.
- Prefer one understandable script over a framework.
- Do not add scheduler installers to this repo.
- Do not add network calls to `review-day`.
- Do not hard-code specific sub-agents.
- Do not add new dependencies unless there is a concrete failing use case.
- Keep capability manifests, risk class, retirement conditions, and dismissals central.

## Good Contributions

- Better opportunity templates.
- Better capability matching.
- More realistic examples.
- Improved risk classification.
- Tests for false positives and dismissals.
- Documentation that makes the action boundary clearer.

## Avoid

- Web dashboards.
- Databases before they are needed.
- Auto-installing cron jobs.
- Agent creation in the review skill.
- Overly broad schemas that are not exercised by examples.

## Test

```bash
python3 -m unittest discover -s tests
```
