"""Safety rule engine — evaluates DSL conditions against twin state.

Vendored from fermentation/src/fermentation/safety/rule_engine.py
(see docs/DEPENDENCIES.md § 1). Adapted: imports point at fermenttrack.safety
instead of fermentation.safety / fermentation.transform.validators; logic
unchanged.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from fermenttrack.safety.ast_evaluator import SafetyDSLParseError, evaluate_condition
from fermenttrack.safety.rule_catalog import RuleCatalog
from fermenttrack.safety.safety_types import RiskRule, RuleAction

logger = logging.getLogger(__name__)


# ── Verdict data class ────────────────────────────────────────────────────

@dataclass
class RuleVerdict:
    """Result of evaluating a single rule."""
    rule_id: str
    triggered: bool
    action: RuleAction
    reason_code: str
    reason_text_en: str
    reason_text_fr: str
    source_citation: str = ""


@dataclass
class SafetyReport:
    """Aggregated safety assessment for a twin state snapshot."""
    safe: bool
    hard_stops: list[RuleVerdict] = field(default_factory=list)
    warnings: list[RuleVerdict] = field(default_factory=list)
    rules_evaluated: int = 0
    rules_triggered: int = 0

    @property
    def summary_en(self) -> str:
        if self.safe:
            return "All safety checks passed."
        stops = [v.reason_text_en for v in self.hard_stops]
        return "SAFETY ALERT: " + " | ".join(stops)

    @property
    def summary_fr(self) -> str:
        if self.safe:
            return "Tous les contrôles de sécurité sont passés."
        stops = [v.reason_text_fr for v in self.hard_stops]
        return "ALERTE SÉCURITÉ : " + " | ".join(stops)


def _auto_quote_identifiers(condition: str, known_vars: dict[str, Any]) -> str:
    """Quote bare identifier values on the RHS of == / != comparisons.

    Converts ``oxygen_proxy == anaerobic`` → ``oxygen_proxy == "anaerobic"``
    so that string-valued state variables compare correctly.  Numbers, Python
    literals (True/False/None), and known state-variable names are left as-is.
    """
    _python_literals = frozenset(("True", "False", "None"))

    def _replacer(match: re.Match) -> str:
        op, val = match.group(1), match.group(2)
        # Already explicitly quoted
        if val and val[0] in ('"', "'"):
            return f" {op} {val}"
        # Numeric literal
        try:
            float(val)
            return f" {op} {val}"
        except ValueError:
            pass
        # Python built-in literal
        if val in _python_literals:
            return f" {op} {val}"
        # A known variable name — treat as variable reference
        if val in known_vars:
            return f" {op} {val}"
        # Bare word: treat as a string literal and quote it
        return f' {op} "{val}"'

    return re.sub(r" (==|!=) ([A-Za-z_]\w*)", _replacer, condition)


class SafetyRuleEngine:

    def __init__(self, catalog: RuleCatalog | None = None):
        self.catalog = catalog or RuleCatalog()

    def evaluate(
        self,
        state_vars: dict[str, Any],
        scheme: str | None = None,
    ) -> SafetyReport:
        """Run all applicable rules against state variables.

        Parameters
        ----------
        state_vars : dict
            Current experiment state, e.g.:
            ``{"ph": 4.2, "temperature_c": 28, "salt_pct": 3.0,
              "time_hours": 24, "oxygen_proxy": "anaerobic",
              "water_activity": 0.92}``
        scheme : str | None
            Filter rules to this fermentation scheme.

        Returns
        -------
        SafetyReport
        """
        report = SafetyReport(safe=True)
        rules = self.catalog.rules if scheme is None else self.catalog._filtered(scheme)

        for rule in rules:
            report.rules_evaluated += 1
            verdict = self._eval_rule(rule, state_vars)
            if verdict.triggered:
                report.rules_triggered += 1
                if verdict.action == RuleAction.hard_stop:
                    report.hard_stops.append(verdict)
                    report.safe = False
                else:
                    report.warnings.append(verdict)

        return report

    def evaluate_single(
        self, rule_id: str, state_vars: dict[str, Any]
    ) -> RuleVerdict | None:
        rule = self.catalog.get_rule(rule_id)
        if rule is None:
            return None
        return self._eval_rule(rule, state_vars)

    # ── internal ─────────────────────────────────────────────────────────

    def _eval_rule(self, rule: RiskRule, state_vars: dict[str, Any]) -> RuleVerdict:
        triggered = False
        try:
            triggered = self._eval_condition(rule.condition, state_vars)
        except Exception as exc:
            logger.warning(
                "Rule %s condition evaluation error: %s", rule.rule_id, exc
            )

        return RuleVerdict(
            rule_id=rule.rule_id,
            triggered=triggered,
            action=rule.action,
            reason_code=rule.reason_code,
            reason_text_en=rule.reason_text_en,
            reason_text_fr=rule.reason_text_fr,
            source_citation=rule.source_citation,
        )

    @staticmethod
    def _eval_condition(condition: str, state_vars: dict[str, Any]) -> bool:
        """Evaluate a DSL condition string with an allow-listed AST interpreter.

        The DSL supports:
        - Variable names from state_vars
        - Comparison operators: ==, !=, <, >, <=, >=
        - Logical operators: AND, OR, NOT (converted to Python)
        - Arithmetic operators: +, -, *, /
        - Safe calls to abs, min, max, and round
        - Parentheses for grouping

        Bare identifiers on the RHS of == / != that are not numbers, Python
        literals, or known state-variable names are auto-quoted as strings.
        This ensures conditions like ``oxygen_proxy == anaerobic`` match
        correctly against string state variables without requiring explicit
        quotes in the rule YAML.
        """
        # Auto-quote bare string identifiers in == / != comparisons
        expr = _auto_quote_identifiers(condition, state_vars)

        # Convert DSL operators to Python
        expr = re.sub(
            r"\b(AND|OR|NOT)\b",
            lambda match: match.group(1).lower(),
            expr,
        )

        try:
            return evaluate_condition(expr, state_vars)
        except SafetyDSLParseError:
            raise
        except Exception:
            return False
