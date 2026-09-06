#!/usr/bin/env python3
"""
Decision Agent — Research options, cut noise, pick one, honestly.

A reusable subagent for the autonomous swarm that turns messy "which option?"
questions into one clear, evidence-backed recommendation.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Decision protocol:
#   1. Frame the decision
#   2. Research each option (parallel where possible)
#   3. Filter noise
#   4. Compare on what matters
#   5. Make the call
#   6. Say what you don't know
# ---------------------------------------------------------------------------


class DecisionAgent:
    """Research and recommend on a decision question."""

    def __init__(self, workspace: Path | str = "."):
        self.workspace = Path(workspace)
        self.reports_dir = self.workspace / "decision_reports"
        self.reports_dir.mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decide(
        self,
        question: str,
        options: list[str],
        criteria: list[str],
        context: str = "",
        search_fn=None,
        extraction_fn=None,
        max_depth: str = "medium",  # low | medium | high
    ) -> dict:
        """Run the full 6-step decision protocol and return a report.

        Args:
            question: The decision in one sentence.
            options: Candidate options to compare.
            criteria: What actually matters for this decision.
            context: Any extra context the user provided.
            search_fn: Optional async callable(queries: list[str]) -> list[dict]
                       Each result dict should have url, title, description, content.
            extraction_fn: Optional callable(urls: list[str]) -> list[dict]
                           Each result dict should have url, title, content.
            max_depth: Research depth — low/medium/high.

        Returns:
            Decision report dict with recommendation, reasoning, uncertainty.
        """
        report = {
            "question": question,
            "options": options,
            "criteria": criteria,
            "context": context,
            "generated_at": datetime.now().isoformat(),
            "steps": {},
            "recommendation": {},
            "uncertainty": [],
            "raw_research": {},
        }

        # Step 1 — Frame
        framed = self._step1_frame(question, options, criteria, context)
        report["steps"]["frame"] = framed
        if framed.get("needs_clarification"):
            report["recommendation"] = {
                "status": "needs_clarification",
                "questions": framed["questions"],
            }
            self._save_report(report)
            return report

        # Step 2 — Research
        research = self._step2_research(
            framed["options"], framed["criteria"], max_depth, search_fn, extraction_fn
        )
        report["steps"]["research"] = research
        report["raw_research"] = research.get("per_option", {})

        # Step 3 — Filter
        filtered = self._step3_filter(research)
        report["steps"]["filter"] = filtered

        # Step 4 — Compare
        comparison = self._step4_compare(filtered, framed["criteria"])
        report["steps"]["comparison"] = comparison

        # Step 5 — Decide
        recommendation = self._step5_decide(comparison, framed["criteria"])
        report["recommendation"] = recommendation

        # Step 6 — Uncertainty
        uncertainty = self._step6_uncertainty(research, recommendation)
        report["uncertainty"] = uncertainty

        self._save_report(report)
        return report

    # ------------------------------------------------------------------
    # Step 1 — Frame
    # ------------------------------------------------------------------

    def _step1_frame(self, question, options, criteria, context):
        result = {
            "question": question,
            "options": options,
            "criteria": criteria,
            "needs_clarification": False,
            "questions": [],
        }

        if not question or len(question.strip()) < 10:
            result["needs_clarification"] = True
            result["questions"].append(
                "The question is too vague. What exactly are you deciding?"
            )

        if not options or len(options) < 2:
            result["needs_clarification"] = True
            result["questions"].append(
                "I need at least 2 options to compare. What are you choosing between?"
            )

        if not criteria or len(criteria) < 1:
            result["needs_clarification"] = True
            result["questions"].append(
                "What criteria matter for this decision? (cost, time, quality, risk, fit...)"
            )

        return result

    # ------------------------------------------------------------------
    # Step 2 — Research
    # ------------------------------------------------------------------

    def _step2_research(self, options, criteria, max_depth, search_fn, extraction_fn):
        result = {"per_option": {}, "depth": max_depth, "sources_used": []}

        searches_per_option = {"low": 2, "medium": 5, "high": 10}.get(max_depth, 5)

        for option in options:
            queries = self._build_queries(option, criteria)
            queries = queries[:searches_per_option]

            per_option = {"queries": queries, "findings": [], "sources": [], "red_flags": []}

            if search_fn and queries:
                try:
                    raw = search_fn(queries)
                    per_option["sources"] = [
                        {"url": r.get("url"), "title": r.get("title"), "snippet": r.get("description")}
                        for r in raw.get("data", {}).get("web", [])
                    ]
                    result["sources_used"].extend(per_option["sources"])

                    # Optionally extract full content for high-depth
                    if max_depth == "high" and extraction_fn and per_option["sources"]:
                        urls = [s["url"] for s in per_option["sources"][:3]]
                        try:
                            extracted = extraction_fn(urls)
                            for ex in extracted:
                                per_option["findings"].append(
                                    {"url": ex.get("url"), "content": ex.get("content", "")[:2000]}
                                )
                        except Exception:
                            pass

                except Exception as e:
                    per_option["search_error"] = str(e)

            result["per_option"][option] = per_option

        return result

    def _build_queries(self, option, criteria):
        """Build search queries for one option against the criteria."""
        queries = []
        option_clean = option.replace('"', "").strip()

        queries.append(f'"{option_clean}" review')
        queries.append(f'"{option_clean}" vs alternatives')
        queries.append(f'"{option_clean}" pros cons')

        for c in criteria[:3]:
            queries.append(f'"{option_clean}" {c}')

        return list(dict.fromkeys(queries))  # dedupe, preserve order

    # ------------------------------------------------------------------
    # Step 3 — Filter noise
    # ------------------------------------------------------------------

    def _step3_filter(self, research):
        result = {"filtered": {}, "removed": []}

        for option, data in research.get("per_option", {}).items():
            kept = []
            removed_count = 0

            for source in data.get("sources", []):
                snippet = (source.get("snippet") or "").lower()
                url = source.get("url", "")

                # Drop obvious vendor/marketing pages without independent info
                if any(x in url for x in ["/?utm_", "affiliate", "/compare-", "alternative-to"]):
                    if "review" not in snippet and "pros" not in snippet:
                        removed_count += 1
                        continue

                # Drop empty snippets
                if not snippet.strip() or len(snippet) < 30:
                    removed_count += 1
                    continue

                kept.append(source)

            result["filtered"][option] = {"sources": kept, "findings": data.get("findings", [])}
            if removed_count:
                result["removed"].append({"option": option, "count": removed_count})

        return result

    # ------------------------------------------------------------------
    # Step 4 — Compare
    # ------------------------------------------------------------------

    def _step4_compare(self, filtered, criteria):
        result = {"matrix": {}, "summary": []}

        for criterion in criteria:
            scores = {}
            for option, option_data in filtered.items():
                if isinstance(option_data, dict):
                    sources = option_data.get("sources", [])
                    findings = option_data.get("findings", [])
                else:
                    sources = []
                    findings = []

                # Heuristic scoring based on what we found
                positive_signals = sum(
                    1 for s in sources if any(w in (s.get("snippet") or "").lower()
                    for w in ["good", "best", "recommended", "fast", "easy", "powerful", "reliable"])
                )
                negative_signals = sum(
                    1 for s in sources if any(w in (s.get("snippet") or "").lower()
                    for w in ["bad", "slow", "expensive", "bug", "issue", "problem", "downside"])
                )

                # Default: tie if no data
                if not sources and not findings:
                    scores[option] = "no_data"
                elif positive_signals > negative_signals + 1:
                    scores[option] = "wins"
                elif negative_signals > positive_signals + 1:
                    scores[option] = "loses"
                else:
                    scores[option] = "tie"

            result["matrix"][criterion] = scores

            # Build human-readable summary for this criterion
            winners = [o for o, s in scores.items() if s == "wins"]
            losers = [o for o, s in scores.items() if s == "loses"]
            ties = [o for o, s in scores.items() if s == "tie"]
            no_data = [o for o, s in scores.items() if s == "no_data"]

            parts = []
            if winners:
                parts.append(f"Wins: {', '.join(winners)}")
            if losers:
                parts.append(f"Loses: {', '.join(losers)}")
            if ties:
                parts.append(f"Indistinguishable: {', '.join(ties)}")
            if no_data:
                parts.append(f"No data: {', '.join(no_data)}")

            result["summary"].append({"criterion": criterion, "assessment": ". ".join(parts) if parts else "No assessment possible"})

        return result

    # ------------------------------------------------------------------
    # Step 5 — Decide
    # ------------------------------------------------------------------

    def _step5_decide(self, comparison, criteria):
        matrix = comparison.get("matrix", {})

        if not matrix:
            return {
                "status": "no_data",
                "recommendation": None,
                "reason": "Not enough information to compare options.",
                "tiebreaker_needed": True,
            }

        # Count wins per option across all criteria
        win_counts = {}
        for criterion_scores in matrix.values():
            for option, score in criterion_scores.items():
                win_counts[option] = win_counts.get(option, 0) + (1 if score == "wins" else 0)

        if not win_counts:
            return {
                "status": "no_data",
                "recommendation": None,
                "reason": "No comparable data across criteria.",
            }

        best = max(win_counts, key=win_counts.get)
        best_score = win_counts[best]
        total_criteria = len(criteria)

        # Check if there's a clear winner
        others = [(o, s) for o, s in win_counts.items() if o != best]
        max_other = max([s for _, s in others]) if others else 0
        gap = best_score - max_other

        if best_score == 0:
            return {
                "status": "no_winner",
                "recommendation": None,
                "reason": "No option scored positively on any criterion with available data.",
                "tiebreaker_needed": True,
            }

        if gap >= 2:
            # Clear winner
            runner_up = max(others, key=lambda x: x[1])[0] if others else None
            return {
                "status": "clear_winner",
                "recommendation": best,
                "reason": f"Wins on {best_score}/{total_criteria} criteria that matter.",
                "runner_up": runner_up,
                "gap": gap,
                "trade_off": self._infer_trade_off(best, matrix, criteria),
                "when_wrong": self._infer_when_wrong(best, matrix, criteria),
            }

        if gap == 1:
            # Narrow winner — note the uncertainty
            runner_up = max(others, key=lambda x: x[1])[0] if others else None
            return {
                "status": "narrow_winner",
                "recommendation": best,
                "reason": f"Wins on {best_score}/{total_criteria} criteria, but margin is thin.",
                "runner_up": runner_up,
                "gap": gap,
                "trade_off": self._infer_trade_off(best, matrix, criteria),
                "when_wrong": self._infer_when_wrong(best, matrix, criteria),
                "uncertainty": "The margin is small. If the runner-up is better on a criterion you weight heavily, reconsider.",
            }

        # Tie or near-tie
        tied = [o for o, s in win_counts.items() if s == best_score]
        if len(tied) > 1:
            return {
                "status": "tied",
                "recommendation": None,
                "reason": f"{len(tied)} options are effectively tied: {', '.join(tied)}",
                "tied_options": tied,
                "tiebreaker_needed": True,
                "tiebreaker_question": self._suggest_tiebreaker(criteria, tied),
            }

        return {
            "status": "uncertain",
            "recommendation": None,
            "reason": "Could not determine a clear winner from available data.",
            "tiebreaker_needed": True,
        }

    def _infer_trade_off(self, winner, matrix, criteria):
        """What does the winner make you give up?"""
        for criterion, scores in matrix.items():
            if scores.get(winner) != "wins":
                others_winning = [o for o, s in scores.items() if s == "wins" and o != winner]
                if others_winning:
                    return f"You give up on '{criterion}' where {', '.join(others_winning)} do better."
        return "No clear trade-off visible in the data — the winner may be broadly strong, or data is thin."

    def _infer_when_wrong(self, winner, matrix, criteria):
        """Under what condition would this recommendation be wrong?"""
        weak_on = []
        for criterion, scores in matrix.items():
            if scores.get(winner) == "loses":
                weak_on.append(criterion)
        if weak_on:
            return f"If {', '.join(weak_on)} turn out to matter more than the criteria where {winner} wins, this recommendation reverses."
        return "If new information surfaces showing a critical flaw in the winner, reconsider."

    def _suggest_tiebreaker(self, criteria, tied):
        """Suggest a question that breaks the tie."""
        if "cost" in criteria or "price" in criteria:
            return "Which costs less over the time horizon you care about?"
        if "time" in criteria or "speed" in criteria:
            return "Which gets you to the outcome faster?"
        if "risk" in criteria:
            return "Which has the lower downside if it doesn't work out?"
        return "Which one do you trust more based on what you already know?"

    # ------------------------------------------------------------------
    # Step 6 — Uncertainty
    # ------------------------------------------------------------------

    def _step6_uncertainty(self, research, recommendation):
        uncertainties = []

        rec_status = recommendation.get("status", "")

        # Check for no_data options
        for option, data in research.get("per_option", {}).items():
            if not data.get("sources") and not data.get("findings"):
                uncertainties.append({
                    "type": "missing_data",
                    "option": option,
                    "what": f"No information found for '{option}'. I'm basing the comparison on zero evidence for this option.",
                })

        if rec_status in ("no_data", "no_winner", "tied", "uncertain"):
            uncertainties.append({
                "type": "cannot_decide",
                "what": recommendation.get("reason", "Could not determine a winner."),
                "what_would_change": recommendation.get("tiebreaker_question", "More information on the criteria that matter."),
            })

        if recommendation.get("uncertainty"):
            uncertainties.append({
                "type": "thin_evidence",
                "what": recommendation["uncertainty"],
            })

        # Always flag if depth was low
        if research.get("depth") == "low":
            uncertainties.append({
                "type": "shallow_search",
                "what": "Research was shallow (low depth). A deeper search may surface information that changes the recommendation.",
            })

        return uncertainties

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_report(self, report):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in report["question"][:60])
        path = self.reports_dir / f"decision_{timestamp}_{safe_name}.json"
        with open(path, "w") as f:
            json.dump(report, f, indent=2)
        report["_saved_to"] = str(path)

    # ------------------------------------------------------------------
    # Human-readable output
    # ------------------------------------------------------------------

    def format_report(self, report: dict) -> str:
        """Format a decision report as a readable message."""

        lines = []
        lines.append(f"## Deciding: {report['question']}")
        lines.append("")

        # Recommendation first
        rec = report.get("recommendation", {})
        status = rec.get("status", "unknown")

        if status == "needs_clarification":
            lines.append("**I need more information before I can recommend.**")
            lines.append("")
            for q in rec.get("questions", []):
                lines.append(f"- {q}")
            return "\n".join(lines)

        if status in ("no_data", "no_winner", "uncertain"):
            lines.append(f"**I can't make a confident recommendation yet.**")
            lines.append("")
            lines.append(rec.get("reason", ""))
            if rec.get("tiebreaker_needed"):
                lines.append("")
                lines.append("**To break the deadlock, answer:**")
                lines.append(f"- {rec.get('tiebreaker_question', 'What matters more to you?')}")
            return "\n".join(lines)

        if status in ("clear_winner", "narrow_winner"):
            lines.append(f"**Recommendation: {rec.get('recommendation')}**")
            lines.append("")
            lines.append(f"**Why:** {rec.get('reason')}")
            lines.append("")
            if rec.get("trade_off"):
                lines.append(f"**The trade-off you're making:** {rec['trade_off']}")
                lines.append("")
            if rec.get("when_wrong"):
                lines.append(f"**When this would be wrong:** {rec['when_wrong']}")
                lines.append("")
            if rec.get("runner_up"):
                lines.append(f"**Runner-up:** {rec['runner_up']} — didn't win because: {rec.get('reason', '')}")
                lines.append("")
            if rec.get("uncertainty"):
                lines.append(f"**Uncertainty:** {rec['uncertainty']}")
                lines.append("")

        if status == "tied":
            lines.append("**No clear winner — these are tied:**")
            lines.append("")
            for o in rec.get("tied_options", []):
                lines.append(f"- {o}")
            lines.append("")
            lines.append(f"**Tiebreaker question:** {rec.get('tiebreaker_question', '')}")

        # Uncertainty section
        uncertainties = report.get("uncertainty", [])
        if uncertainties:
            lines.append("")
            lines.append("## What I don't know")
            lines.append("")
            for u in uncertainties:
                lines.append(f"- **{u['type']}:** {u['what']}")
                if u.get("what_would_change"):
                    lines.append(f"  - *Would change my mind if:* {u['what_would_change']}")

        # Research summary
        steps = report.get("steps", {})
        research = steps.get("research", {})
        per_option = research.get("per_option", {})

        if per_option:
            lines.append("")
            lines.append("## What I found")
            lines.append("")
            for option, data in per_option.items():
                sources = data.get("sources", [])
                lines.append(f"### {option}")
                lines.append("")
                if sources:
                    for s in sources[:5]:
                        lines.append(f"- [{s.get('title', 'Unknown')}]({s.get('url', '')})")
                else:
                    lines.append("- No sources found.")
                lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Decision Agent — research and recommend")
    parser.add_argument("--question", required=True, help="The decision question")
    parser.add_argument("--options", nargs="+", required=True, help="Options to compare")
    parser.add_argument("--criteria", nargs="+", required=True, help="Criteria that matter")
    parser.add_argument("--context", default="", help="Extra context")
    parser.add_argument("--depth", default="medium", choices=["low", "medium", "high"])
    parser.add_argument("--output", help="Save report to specific path")
    args = parser.parse_args()

    agent = DecisionAgent()
    report = agent.decide(
        question=args.question,
        options=args.options,
        criteria=args.criteria,
        context=args.context,
        max_depth=args.depth,
    )

    print(agent.format_report(report))

    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nFull report saved to: {args.output}")
