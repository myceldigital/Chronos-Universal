#!/usr/bin/env python3
"""Chronos Universal review-day skill.

Pure function:
    daily history JSONL + agent capability registry + dismissals JSONL
    -> markdown report + JSON plan

This script never installs cron jobs, triggers agents, expands permissions, or makes
network calls. It is intentionally small and inspectable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

RISK_ORDER = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}

KEYWORDS = {
    "commitment": ["send", "follow up", "follow-up", "confirm", "prepare", "draft", "review", "book", "schedule", "reply"],
    "meeting": ["meeting", "call", "consultation", "demo", "review", "sync"],
    "stale": ["waiting", "blocked", "stale", "overdue", "pending", "no response", "unanswered"],
    "prep": ["prepare", "agenda", "brief", "pre-read", "context", "tomorrow"],
    "docs": ["documentation", "readme", "sop", "policy", "protocol", "guideline", "template"],
    "anomaly": ["spike", "drop", "failed", "error", "refund", "anomaly", "unexpected"],
}

OPPORTUNITY_TEMPLATES = [
    {
        "key": "open_loop_capture",
        "title": "End-of-day open-loop capture",
        "pattern": "The user made commitments or created open loops that should be captured before the day ends.",
        "needed": ["read_email", "read_calendar", "extract_commitments", "create_or_suggest_tasks"],
        "trigger": {"type": "cron", "expression": "10 18 * * 1-5", "human_readable": "Weekdays at 18:10"},
        "risk": "L1",
        "instruction": "Review today's activity history. Identify commitments, waiting-for items, unresolved decisions, and implied next actions. Suggest tasks with source, owner, priority, and due date. Do not create or modify tasks unless separately approved.",
        "evidence_tags": ["commitment"],
        "base_value": 0.82,
        "false_positive_cost": "Medium: noisy task suggestions create review burden.",
    },
    {
        "key": "post_event_followup",
        "title": "Post-event follow-up sweep",
        "pattern": "Meetings or calls occurred where follow-up may be needed.",
        "needed": ["read_calendar", "read_email", "detect_followups", "draft_message"],
        "trigger": {"type": "cron", "expression": "45 16 * * 1-5", "human_readable": "Weekdays at 16:45"},
        "risk": "L1",
        "instruction": "Review today's completed meetings and related email threads. Identify missing follow-ups and draft suggested next-step messages. Do not send messages without approval.",
        "evidence_tags": ["meeting", "commitment"],
        "base_value": 0.78,
        "false_positive_cost": "Medium-high: irrelevant follow-up drafts are annoying and can damage trust.",
    },
    {
        "key": "pre_event_briefing",
        "title": "Pre-event briefing",
        "pattern": "Upcoming or repeated meetings would benefit from preparation context.",
        "needed": ["read_calendar", "search_email", "search_files", "summarize_context"],
        "trigger": {"type": "event", "event": "calendar.event.starts_in_2_hours", "human_readable": "When a calendar event starts within 2 hours"},
        "risk": "L0",
        "instruction": "Before high-value meetings, gather relevant calendar, email, notes, and file context. Produce a concise briefing with people, agenda, open questions, and decisions likely required.",
        "evidence_tags": ["meeting", "prep"],
        "base_value": 0.74,
        "false_positive_cost": "Low-medium: extra briefings can become noise if meetings are low value.",
    },
    {
        "key": "stale_work_cleanup",
        "title": "Weekly stale-work cleanup",
        "pattern": "Stale, blocked, pending, or unanswered work appeared in the history.",
        "needed": ["read_tasks", "read_email", "detect_staleness", "prioritize"],
        "trigger": {"type": "cron", "expression": "30 15 * * 5", "human_readable": "Fridays at 15:30"},
        "risk": "L1",
        "instruction": "Review open tasks, unanswered threads, old drafts, and pending decisions. Surface items that are stuck, abandoned, or need closure. Recommend next action or archive decision; do not change records automatically.",
        "evidence_tags": ["stale"],
        "base_value": 0.70,
        "false_positive_cost": "Low-medium: stale-work reports can be skimmed quickly.",
    },
    {
        "key": "documentation_drift",
        "title": "Documentation drift review",
        "pattern": "Decisions, process changes, or repeated questions suggest documentation may be out of date.",
        "needed": ["read_docs", "read_repos", "compare_changes_to_docs", "suggest_doc_updates"],
        "trigger": {"type": "cron", "expression": "0 11 * * 5", "human_readable": "Fridays at 11:00"},
        "risk": "L1",
        "instruction": "Review recent decisions, code changes, policy/process references, and repeated questions. Identify documentation that is outdated, missing, or contradicted by practice. Suggest doc updates only.",
        "evidence_tags": ["docs"],
        "base_value": 0.66,
        "false_positive_cost": "Low: documentation suggestions are easy to reject.",
    },
    {
        "key": "anomaly_review",
        "title": "Operational anomaly review",
        "pattern": "Potential anomalies, errors, failed actions, drops, or spikes appeared in the day.",
        "needed": ["read_metrics", "detect_anomalies", "compare_baseline", "generate_alert"],
        "trigger": {"type": "threshold", "condition": "anomaly_score > configured_threshold", "human_readable": "When an operational signal crosses a configured anomaly threshold"},
        "risk": "L1",
        "instruction": "Review available metrics and operational events. Detect unusual spikes, drops, failures, or missing expected events. Report likely causes and recommended checks. Do not modify systems.",
        "evidence_tags": ["anomaly"],
        "base_value": 0.72,
        "false_positive_cost": "Medium: false anomaly alerts create alert fatigue.",
    },
]

CAPABILITY_ALIASES = {
    "read_email": ["read_email", "email.threads", "gmail.read", "search_email"],
    "search_email": ["search_email", "email.threads", "gmail.search", "read_email"],
    "read_calendar": ["read_calendar", "calendar.events", "calendar.read"],
    "read_tasks": ["read_tasks", "tasks.open", "tasks.read"],
    "read_docs": ["read_docs", "docs.read", "files.read"],
    "read_repos": ["read_repos", "github.read", "repo.read"],
    "read_metrics": ["read_metrics", "metrics.read", "analytics.read"],
    "extract_commitments": ["extract_commitments", "infer_next_actions", "commitment_extraction"],
    "create_or_suggest_tasks": ["create_or_suggest_tasks", "create_task_suggestion", "create_task", "suggest_tasks"],
    "detect_followups": ["detect_followups", "followup_detection", "infer_next_actions"],
    "draft_message": ["draft_message", "create_email_draft", "draft_response"],
    "summarize_context": ["summarize_context", "summarize", "context_summary"],
    "detect_staleness": ["detect_staleness", "stale_work_detection"],
    "prioritize": ["prioritize", "rank", "classify"],
    "compare_changes_to_docs": ["compare_changes_to_docs", "doc_drift_detection"],
    "suggest_doc_updates": ["suggest_doc_updates", "draft_doc_update"],
    "detect_anomalies": ["detect_anomalies", "anomaly_detection"],
    "compare_baseline": ["compare_baseline", "baseline_comparison"],
    "generate_alert": ["generate_alert", "alert", "report"],
}

@dataclass
class Evidence:
    event_index: int
    summary: str

@dataclass
class CandidateAgent:
    agent_id: str
    fit_score: float
    matched_capabilities: List[str]
    missing_capabilities: List[str]


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
    return rows


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def event_text(event: Dict[str, Any]) -> str:
    parts = [str(event.get("source", "")), str(event.get("action", "")), str(event.get("summary", ""))]
    payload = event.get("payload", {})
    if isinstance(payload, dict):
        parts.append(json.dumps(payload, ensure_ascii=False).lower())
    return " ".join(parts).lower()


def tagged_events(events: Sequence[Dict[str, Any]], tags: Sequence[str]) -> List[Evidence]:
    evidence: List[Evidence] = []
    for idx, event in enumerate(events):
        text = event_text(event)
        matched = False
        for tag in tags:
            if any(keyword in text for keyword in KEYWORDS.get(tag, [])):
                matched = True
                break
        if matched:
            summary = event.get("summary") or f"{event.get('source', 'unknown')}:{event.get('action', 'unknown')}"
            evidence.append(Evidence(event_index=idx, summary=str(summary)))
    return evidence


def flatten_agent_capabilities(agent: Dict[str, Any]) -> List[str]:
    caps = agent.get("capabilities", {})
    flat: List[str] = []
    for group in ("read", "reason", "write", "act"):
        vals = caps.get(group, [])
        if isinstance(vals, list):
            flat.extend(str(v) for v in vals)
    return flat


def capability_matches(required: str, available: Iterable[str]) -> bool:
    available_set = {a.lower() for a in available}
    aliases = {required.lower(), *[a.lower() for a in CAPABILITY_ALIASES.get(required, [])]}
    return bool(aliases & available_set)


def fit_agent(agent: Dict[str, Any], required: Sequence[str], risk_class: str) -> CandidateAgent:
    available = flatten_agent_capabilities(agent)
    matched = [cap for cap in required if capability_matches(cap, available)]
    missing = [cap for cap in required if cap not in matched]
    constraints = agent.get("constraints", {})
    max_risk = constraints.get("max_risk_class", "L0")
    risk_ok = RISK_ORDER.get(risk_class, 99) <= RISK_ORDER.get(max_risk, -1)
    scheduled_ok = agent.get("cron_compatibility", {}).get("can_run_scheduled", False)
    base = len(matched) / max(1, len(required))
    if not risk_ok:
        base *= 0.55
    if not scheduled_ok:
        base *= 0.75
    return CandidateAgent(
        agent_id=str(agent.get("agent_id", "unknown")),
        fit_score=round(base, 3),
        matched_capabilities=matched,
        missing_capabilities=missing,
    )


def dismissal_penalty(dismissals: Sequence[Dict[str, Any]], pattern_key: str) -> float:
    penalty = 0.0
    for row in dismissals:
        if row.get("pattern_key") == pattern_key or str(row.get("proposal_id", "")).find(pattern_key) >= 0:
            decision = row.get("decision")
            if decision == "dismissed":
                penalty += 0.18
            elif decision == "ignored":
                penalty += 0.08
            elif decision in {"installed", "modified_then_installed"}:
                penalty -= 0.08
    return min(0.55, max(-0.25, penalty))


def stable_id(date_hint: str, key: str, evidence: Sequence[Evidence]) -> str:
    raw = f"{date_hint}:{key}:{','.join(str(e.event_index) for e in evidence[:5])}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"p_{date_hint}_{key}_{digest}".replace("-", "_")


def build_proposals(events: Sequence[Dict[str, Any]], agents: Sequence[Dict[str, Any]], dismissals: Sequence[Dict[str, Any]], date_hint: str) -> List[Dict[str, Any]]:
    proposals: List[Dict[str, Any]] = []
    for template in OPPORTUNITY_TEMPLATES:
        evidence = tagged_events(events, template["evidence_tags"])
        if len(evidence) == 0:
            continue
        if len(evidence) == 1 and template["key"] not in {"anomaly_review", "pre_event_briefing"}:
            continue

        candidate_agents = sorted(
            [fit_agent(agent, template["needed"], template["risk"]) for agent in agents],
            key=lambda a: a.fit_score,
            reverse=True,
        )
        best = candidate_agents[0] if candidate_agents else None
        if best and best.fit_score >= 0.75:
            status = "matched"
            selected_agent_id: Optional[str] = best.agent_id
            missing = best.missing_capabilities
        elif best and best.fit_score >= 0.45:
            status = "partial_match"
            selected_agent_id = best.agent_id
            missing = best.missing_capabilities
        else:
            status = "no_suitable_agent"
            selected_agent_id = None
            missing = list(template["needed"])

        frequency_score = min(1.0, len(evidence) / 5)
        fit_score = best.fit_score if best else 0.0
        penalty = dismissal_penalty(dismissals, template["key"])
        confidence = max(0.05, min(0.98, 0.35 + (0.35 * frequency_score) + (0.25 * fit_score) - penalty))
        score = max(0.0, min(1.0, (template["base_value"] * 0.45) + (confidence * 0.35) + (fit_score * 0.20) - penalty))

        if score < 0.42:
            continue

        proposal = {
            "id": stable_id(date_hint, template["key"], evidence),
            "title": template["title"],
            "detected_pattern": template["pattern"],
            "evidence": [asdict(e) for e in evidence[:8]],
            "needed_capabilities": template["needed"],
            "agent_match": {
                "status": status,
                "selected_agent_id": selected_agent_id,
                "fit_score": round(fit_score, 3),
                "candidate_agents": [asdict(a) for a in candidate_agents[:5]],
                "missing_capabilities": missing,
            },
            "trigger": template["trigger"],
            "job_instruction": template["instruction"],
            "risk_class": template["risk"],
            "confidence": round(confidence, 3),
            "score": round(score, 3),
            "estimated_value": estimate_value(template["base_value"], len(evidence), fit_score),
            "false_positive_cost": template["false_positive_cost"],
            "approval_required": template["risk"] != "L0" or status != "matched",
            "success_criteria": success_criteria(template["key"]),
            "retirement_conditions": [
                "No useful findings for 14 consecutive runs",
                "User dismisses this proposal 3 times",
                "A better-fit installed agent becomes available",
            ],
        }
        proposals.append(proposal)
    proposals.sort(key=lambda p: p["score"], reverse=True)
    return proposals


def estimate_value(base_value: float, evidence_count: int, fit_score: float) -> str:
    total = base_value + min(0.25, evidence_count * 0.04) + fit_score * 0.15
    if total >= 1.0:
        return "High"
    if total >= 0.78:
        return "Medium-high"
    if total >= 0.6:
        return "Medium"
    return "Low"


def success_criteria(key: str) -> List[str]:
    common = ["User accepts, edits, or installs the proposal at least once during trial", "False positives remain tolerable in review"]
    specific = {
        "open_loop_capture": ["Captures at least 80% of manually identified commitments", "Creates no external actions"],
        "post_event_followup": ["Surfaces high-value follow-ups within the same working day", "Drafts require minimal editing"],
        "pre_event_briefing": ["Briefings are useful in at least 2 of 3 reviewed meetings", "Low-value meetings are filtered out"],
        "stale_work_cleanup": ["Identifies genuinely stale items", "Reduces abandoned open loops"],
        "documentation_drift": ["Finds at least one useful documentation update per month", "Does not create busywork"],
        "anomaly_review": ["Alerts are rare and meaningful", "No automatic remediation occurs"],
    }
    return specific.get(key, []) + common


def render_markdown(proposals: Sequence[Dict[str, Any]], history_path: Path, agents_path: Path) -> str:
    lines = [
        "# Chronos Daily Review",
        "",
        f"History: `{history_path}`",
        f"Agent registry: `{agents_path}`",
        "",
    ]
    if not proposals:
        lines.extend([
            "## No strong recurring-workflow proposals today",
            "",
            "Chronos did not find a proposal that cleared the minimum score threshold. This is a feature, not a failure: fewer noisy suggestions are better than automation sprawl.",
        ])
        return "\n".join(lines) + "\n"

    lines.extend([
        "## Ranked Proposals",
        "",
        "| Rank | Proposal | Score | Confidence | Trigger | Agent Match | Risk | Approval |",
        "|---:|---|---:|---:|---|---|---|---|",
    ])
    for i, p in enumerate(proposals, start=1):
        match = p["agent_match"]
        agent = match.get("selected_agent_id") or "capability gap"
        trigger = p["trigger"].get("human_readable", p["trigger"].get("type", "manual"))
        approval = "yes" if p["approval_required"] else "no"
        lines.append(f"| {i} | {p['title']} | {p['score']:.3f} | {p['confidence']:.3f} | {trigger} | {match['status']} / {agent} | {p['risk_class']} | {approval} |")

    for i, p in enumerate(proposals, start=1):
        lines.extend([
            "",
            f"## {i}. {p['title']}",
            "",
            f"**ID:** `{p['id']}`",
            f"**Pattern:** {p['detected_pattern']}",
            f"**Estimated value:** {p['estimated_value']}",
            f"**False-positive cost:** {p['false_positive_cost']}",
            f"**Risk:** {p['risk_class']}",
            f"**Approval required:** {'yes' if p['approval_required'] else 'no'}",
            "",
            "### Trigger",
            "",
            f"- Type: `{p['trigger']['type']}`",
            f"- Human-readable: {p['trigger']['human_readable']}",
        ])
        if "expression" in p["trigger"]:
            lines.append(f"- Expression: `{p['trigger']['expression']}`")
        if "event" in p["trigger"]:
            lines.append(f"- Event: `{p['trigger']['event']}`")
        if "condition" in p["trigger"]:
            lines.append(f"- Condition: `{p['trigger']['condition']}`")
        lines.extend([
            "",
            "### Agent Match",
            "",
            f"- Status: `{p['agent_match']['status']}`",
            f"- Selected agent: `{p['agent_match'].get('selected_agent_id')}`",
            f"- Fit score: `{p['agent_match']['fit_score']}`",
            f"- Missing capabilities: {', '.join(p['agent_match']['missing_capabilities']) or 'none'}",
            "",
            "### Evidence",
            "",
        ])
        for ev in p["evidence"]:
            lines.append(f"- Event `{ev['event_index']}`: {ev['summary']}")
        lines.extend([
            "",
            "### Instruction",
            "",
            p["job_instruction"],
            "",
            "### Success Criteria",
            "",
        ])
        for c in p["success_criteria"]:
            lines.append(f"- {c}")
        lines.extend(["", "### Retirement Conditions", ""])
        for c in p["retirement_conditions"]:
            lines.append(f"- {c}")

    return "\n".join(lines) + "\n"


def infer_date_hint(history_path: Path, events: Sequence[Dict[str, Any]]) -> str:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", history_path.name)
    if match:
        return match.group(1)
    if events and isinstance(events[0].get("ts"), str):
        return events[0]["ts"][:10]
    return "unknown_date"


def command_review(args: argparse.Namespace) -> int:
    history_path = Path(args.history).expanduser()
    agents_path = Path(args.agents).expanduser()
    dismissals_path = Path(args.dismissals).expanduser() if args.dismissals else None
    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    events = load_jsonl(history_path)
    agents_data = load_json(agents_path)
    agents = agents_data.get("agents", agents_data if isinstance(agents_data, list) else [])
    if not isinstance(agents, list):
        raise ValueError("Agent registry must be a list or an object with an 'agents' list")
    dismissals = load_jsonl(dismissals_path) if dismissals_path else []
    date_hint = infer_date_hint(history_path, events)

    proposals = build_proposals(events, agents, dismissals, date_hint)
    plan = {
        "schema_version": "0.1.0",
        "history": str(history_path),
        "agent_registry": str(agents_path),
        "proposal_count": len(proposals),
        "proposals": proposals,
    }
    (out_dir / "plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "review.md").write_text(render_markdown(proposals, history_path, agents_path), encoding="utf-8")
    print(f"Wrote {out_dir / 'review.md'}")
    print(f"Wrote {out_dir / 'plan.json'}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Chronos Universal daily review skill")
    sub = parser.add_subparsers(dest="command", required=True)
    review = sub.add_parser("review", help="Generate a daily review report and JSON plan")
    review.add_argument("--history", required=True, help="Path to daily history JSONL")
    review.add_argument("--agents", required=True, help="Path to installed agent registry JSON")
    review.add_argument("--dismissals", help="Path to dismissals JSONL")
    review.add_argument("--out-dir", default=".chronos-out", help="Output directory")
    review.set_defaults(func=command_review)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
