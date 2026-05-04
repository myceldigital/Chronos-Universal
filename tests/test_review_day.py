import json
import tempfile
import unittest
from pathlib import Path

from scripts.review_day import build_proposals, fit_agent, main


class ReviewDayTests(unittest.TestCase):
    def test_agent_fit_matches_alias_capabilities(self):
        agent = {
            "agent_id": "agent.task",
            "capabilities": {
                "read": ["email.threads", "calendar.events"],
                "reason": ["extract_commitments"],
                "write": ["create_task_suggestion"],
                "act": [],
            },
            "constraints": {"max_risk_class": "L1"},
            "cron_compatibility": {"can_run_scheduled": True},
        }
        fit = fit_agent(agent, ["read_email", "read_calendar", "extract_commitments", "create_or_suggest_tasks"], "L1")
        self.assertEqual(fit.agent_id, "agent.task")
        self.assertGreaterEqual(fit.fit_score, 0.99)
        self.assertEqual(fit.missing_capabilities, [])

    def test_build_proposals_outputs_capability_gap_when_no_agent_fits(self):
        events = [
            {"ts": "2026-05-04T09:00:00+01:00", "source": "ops", "actor": "system", "action": "metric.failed", "summary": "Unexpected failed payment spike"}
        ]
        agents = []
        proposals = build_proposals(events, agents, [], "2026-05-04")
        self.assertTrue(any(p["agent_match"]["status"] == "no_suitable_agent" for p in proposals))

    def test_dismissals_downrank_repeated_pattern(self):
        events = [
            {"ts": "2026-05-04T09:00:00+01:00", "source": "email", "actor": "user", "action": "email.sent", "summary": "send updated notes"},
            {"ts": "2026-05-04T10:00:00+01:00", "source": "calendar", "actor": "user", "action": "meeting.completed", "summary": "follow up after meeting"},
        ]
        agent = {
            "agent_id": "agent.task",
            "capabilities": {
                "read": ["email.threads", "calendar.events"],
                "reason": ["extract_commitments"],
                "write": ["create_task_suggestion"],
                "act": [],
            },
            "constraints": {"max_risk_class": "L1", "requires_approval_for": [], "forbidden_actions": []},
            "cron_compatibility": {"can_run_scheduled": True},
        }
        without = build_proposals(events, [agent], [], "2026-05-04")
        with_dismissals = build_proposals(
            events,
            [agent],
            [{"proposal_id": "p_old_open_loop_capture", "pattern_key": "open_loop_capture", "decision": "dismissed"}],
            "2026-05-04",
        )
        top_without = next(p for p in without if "open-loop" in p["title"])
        top_with = next(p for p in with_dismissals if "open-loop" in p["title"])
        self.assertLess(top_with["score"], top_without["score"])

    def test_cli_writes_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            history = root / "2026-05-04.jsonl"
            history.write_text(
                '{"ts":"2026-05-04T09:00:00+01:00","source":"email","actor":"user","action":"email.sent","summary":"send draft"}\n'
                '{"ts":"2026-05-04T10:00:00+01:00","source":"calendar","actor":"user","action":"meeting.completed","summary":"follow up after meeting"}\n',
                encoding="utf-8",
            )
            agents = root / "agents.json"
            agents.write_text(json.dumps({"agents": [{
                "agent_id": "agent.task",
                "display_name": "Task Agent",
                "capabilities": {
                    "read": ["email.threads", "calendar.events"],
                    "reason": ["extract_commitments", "detect_followups"],
                    "write": ["create_task_suggestion", "draft_message"],
                    "act": []
                },
                "constraints": {"max_risk_class": "L1", "requires_approval_for": [], "forbidden_actions": []},
                "cron_compatibility": {"can_run_scheduled": True, "preferred_frequencies": ["daily"], "max_runtime_seconds": 100}
            }]}), encoding="utf-8")
            out = root / "out"
            rc = main(["review", "--history", str(history), "--agents", str(agents), "--out-dir", str(out)])
            self.assertEqual(rc, 0)
            self.assertTrue((out / "review.md").exists())
            self.assertTrue((out / "plan.json").exists())


if __name__ == "__main__":
    unittest.main()
