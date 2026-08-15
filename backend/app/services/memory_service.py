from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import AgentDecision, DecisionEvaluation, TradeJournalEntry


class MemoryService:
    """Summarize recent agent outcomes for future strategy feedback."""

    def get_summary(self, db: Session, limit: int = 100) -> dict[str, Any]:
        safe_limit = min(max(limit, 1), 500)
        journal_entries = (
            db.query(TradeJournalEntry)
            .order_by(TradeJournalEntry.created_at.desc())
            .limit(safe_limit)
            .all()
        )
        # Operational guard audits remain visible in journal history, while
        # strategy memory reads its own outcome-backed window so a busy day of
        # skipped cycles cannot push older executed evidence out of context.
        strategy_entries = (
            db.query(TradeJournalEntry)
            .filter(TradeJournalEntry.symbol != "NONE")
            .filter(TradeJournalEntry.outcome_label != "SKIPPED_GUARD")
            .filter(
                or_(
                    TradeJournalEntry.order_id.is_not(None),
                    TradeJournalEntry.evaluation_id.is_not(None),
                )
            )
            .order_by(TradeJournalEntry.created_at.desc())
            .limit(safe_limit)
            .all()
        )
        decision_ids = [entry.decision_id for entry in strategy_entries]
        decisions = self._decisions_by_id(db, decision_ids)
        evaluations = self._latest_evaluations_by_decision_id(db, decision_ids)

        return {
            "lookback_journal_entries": len(journal_entries),
            "strategy_entry_count": len(strategy_entries),
            "evaluated_entry_count": sum(1 for entry in strategy_entries if entry.evaluation_id),
            "average_reward_score": self._average_reward(strategy_entries),
            "win_rate_percent": self._win_rate_percent(strategy_entries),
            "action_stats": self._action_stats(strategy_entries),
            "symbol_stats": self._symbol_stats(strategy_entries),
            "model_stats": self._model_stats(strategy_entries, decisions),
            "prompt_stats": self._prompt_stats(strategy_entries, decisions),
            "common_mistakes": self._common_mistakes(evaluations),
            "recent_lessons": self._recent_lessons(strategy_entries),
            "memory_notes": self._memory_notes(strategy_entries, evaluations),
            "data_gaps": self._data_gaps(strategy_entries, decisions),
        }

    @staticmethod
    def _decisions_by_id(db: Session, decision_ids: list[int]) -> dict[int, AgentDecision]:
        if not decision_ids:
            return {}
        rows = db.query(AgentDecision).filter(AgentDecision.id.in_(decision_ids)).all()
        return {row.id: row for row in rows}

    @staticmethod
    def _latest_evaluations_by_decision_id(
        db: Session,
        decision_ids: list[int],
    ) -> dict[int, DecisionEvaluation]:
        if not decision_ids:
            return {}
        rows = (
            db.query(DecisionEvaluation)
            .filter(DecisionEvaluation.decision_id.in_(decision_ids))
            .order_by(DecisionEvaluation.evaluated_at.desc())
            .all()
        )
        evaluations: dict[int, DecisionEvaluation] = {}
        for row in rows:
            evaluations.setdefault(row.decision_id, row)
        return evaluations

    @staticmethod
    def _average_reward(entries: list[TradeJournalEntry]) -> float:
        if not entries:
            return 0
        return round(sum(entry.reward_score for entry in entries) / len(entries), 6)

    @staticmethod
    def _win_rate_percent(entries: list[TradeJournalEntry]) -> float:
        evaluated = [entry for entry in entries if entry.outcome_label in {"PROFITABLE", "UNPROFITABLE"}]
        if not evaluated:
            return 0
        wins = sum(1 for entry in evaluated if entry.outcome_label == "PROFITABLE")
        return round(wins / len(evaluated) * 100, 2)

    def _action_stats(self, entries: list[TradeJournalEntry]) -> list[dict[str, Any]]:
        grouped: dict[str, list[TradeJournalEntry]] = defaultdict(list)
        for entry in entries:
            grouped[entry.action.value].append(entry)
        return [
            self._entry_group_stats(action, action_entries)
            for action, action_entries in sorted(grouped.items())
        ]

    def _symbol_stats(self, entries: list[TradeJournalEntry]) -> list[dict[str, Any]]:
        grouped: dict[str, list[TradeJournalEntry]] = defaultdict(list)
        for entry in entries:
            grouped[entry.symbol].append(entry)
        stats = [self._entry_group_stats(symbol, symbol_entries) for symbol, symbol_entries in grouped.items()]
        return sorted(stats, key=lambda item: (item["count"], item["average_reward_score"]), reverse=True)[:20]

    def _model_stats(
        self,
        entries: list[TradeJournalEntry],
        decisions: dict[int, AgentDecision],
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[TradeJournalEntry]] = defaultdict(list)
        for entry in entries:
            decision = decisions.get(entry.decision_id)
            model = decision.llm_model if decision and decision.llm_model else "unknown"
            grouped[model].append(entry)
        return [
            self._entry_group_stats(model, model_entries)
            for model, model_entries in sorted(grouped.items())
        ]

    def _prompt_stats(
        self,
        entries: list[TradeJournalEntry],
        decisions: dict[int, AgentDecision],
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[TradeJournalEntry]] = defaultdict(list)
        for entry in entries:
            decision = decisions.get(entry.decision_id)
            prompt_key = self._prompt_key(decision)
            grouped[prompt_key].append(entry)
        return [
            self._entry_group_stats(prompt_key, prompt_entries)
            for prompt_key, prompt_entries in sorted(grouped.items())
        ]

    def _entry_group_stats(self, key: str, entries: list[TradeJournalEntry]) -> dict[str, Any]:
        return {
            "key": key,
            "count": len(entries),
            "win_rate_percent": self._win_rate_percent(entries),
            "average_reward_score": self._average_reward(entries),
        }

    @staticmethod
    def _common_mistakes(evaluations: dict[int, DecisionEvaluation]) -> list[dict[str, Any]]:
        counter = Counter(
            evaluation.mistake_type
            for evaluation in evaluations.values()
            if evaluation.mistake_type
        )
        return [
            {"mistake_type": mistake_type, "count": count}
            for mistake_type, count in counter.most_common(10)
        ]

    @staticmethod
    def _recent_lessons(entries: list[TradeJournalEntry]) -> list[dict[str, Any]]:
        lessons = []
        for entry in entries:
            if not entry.lesson:
                continue
            lessons.append(
                {
                    "journal_id": entry.id,
                    "symbol": entry.symbol,
                    "action": entry.action.value,
                    "reward_score": entry.reward_score,
                    "lesson": entry.lesson,
                }
            )
            if len(lessons) >= 10:
                break
        return lessons

    @staticmethod
    def _memory_notes(
        entries: list[TradeJournalEntry],
        evaluations: dict[int, DecisionEvaluation],
    ) -> list[str]:
        notes = []
        if not entries:
            return ["No executed or evaluated strategy entries are available yet."]
        if len(evaluations) < max(len(entries) // 2, 1):
            notes.append("Evaluation coverage is still thin; treat memory stats as directional only.")
        if not any(entry.lesson for entry in entries):
            notes.append("No explicit lessons recorded yet. Add lesson text to make Memory Agent more useful.")
        if not notes:
            notes.append("Memory summary is ready for strategy review.")
        return notes

    @staticmethod
    def _data_gaps(
        entries: list[TradeJournalEntry],
        decisions: dict[int, AgentDecision],
    ) -> list[str]:
        gaps = []
        if entries and not any(decision.llm_model for decision in decisions.values()):
            gaps.append("LLM model coverage is missing for recent journaled decisions.")
        if entries and not any(MemoryService._prompt_key(decision) != "unknown" for decision in decisions.values()):
            gaps.append("Prompt version is not tracked yet, so prompt-level win rate is unavailable.")
        gaps.append("News source/type is not tracked yet, so news-pattern success rate is unavailable.")
        return gaps

    @staticmethod
    def _prompt_key(decision: AgentDecision | None) -> str:
        if not decision:
            return "unknown"
        prompt_metadata = decision.agent_response_json.get("prompt_metadata") or decision.input_snapshot_json.get("prompt_metadata") or {}
        version = prompt_metadata.get("version")
        strategy_name = prompt_metadata.get("strategy_name")
        if version and strategy_name:
            return f"{strategy_name}:{version}"
        if version:
            return str(version)
        return "unknown"
