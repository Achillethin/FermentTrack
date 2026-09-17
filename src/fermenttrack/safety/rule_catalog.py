"""Safety rule catalog — loads persisted rules and provides lookup.

Vendored from fermentation/src/fermentation/safety/rule_catalog.py
(see docs/DEPENDENCIES.md § 1). Adapted: default rules path now points at
the risk_rules.yaml co-located in this package instead of fermentation's
data/curated/ directory; RiskRule/RuleAction now come from safety_types.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from fermenttrack.safety.safety_types import RiskRule, RuleAction

logger = logging.getLogger(__name__)

_DEFAULT_RULES_PATH = Path(__file__).resolve().parent / "risk_rules.yaml"


class RuleCatalog:
    """Loads and indexes safety rules from YAML."""

    def __init__(self, rules_path: Path | None = None):
        self._path = rules_path or _DEFAULT_RULES_PATH
        self._rules: list[RiskRule] = []
        self._load()

    # ── public API ────────────────────────────────────────────────────────

    @property
    def rules(self) -> list[RiskRule]:
        return list(self._rules)

    def hard_stops(self, scheme: str | None = None) -> list[RiskRule]:
        return [r for r in self._filtered(scheme) if r.action == RuleAction.hard_stop]

    def warnings(self, scheme: str | None = None) -> list[RiskRule]:
        return [r for r in self._filtered(scheme) if r.action == RuleAction.warning]

    def get_rule(self, rule_id: str) -> RiskRule | None:
        for r in self._rules:
            if r.rule_id == rule_id:
                return r
        return None

    def reload(self) -> None:
        self._rules.clear()
        self._load()

    # ── internal ─────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.exists():
            logger.warning("Rule catalog not found at %s", self._path)
            return
        with open(self._path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        raw_rules = data.get("rules", [])
        for raw in raw_rules:
            try:
                self._rules.append(RiskRule(**raw))
            except Exception as exc:
                logger.warning("Skipping invalid rule %s: %s", raw.get("rule_id"), exc)
        logger.info("Loaded %d rules from %s", len(self._rules), self._path)

    def _filtered(self, scheme: str | None) -> list[RiskRule]:
        if scheme is None:
            return self._rules
        return [r for r in self._rules if scheme in r.fermentation_schemes]
