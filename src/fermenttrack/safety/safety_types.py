"""Minimal vendored slice of fermentation.transform.validators — only the
types the safety rule engine needs (RiskRule, RuleAction, FermentationScheme).

The upstream validators.py is a large domain-wide Pydantic module (ingredients,
nutrients, product enrichment, etc.) unrelated to safety evaluation; vendoring
the whole file would pull in scope FermentTrack doesn't use. See
docs/DEPENDENCIES.md § 1.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RuleAction(str, Enum):
    hard_stop = "hard_stop"
    warning = "warning"
    info = "info"


class FermentationScheme(str, Enum):
    lactic = "lactic"
    enzymatic_koji = "enzymatic_koji"
    alcoholic = "alcoholic"
    acetic = "acetic"


class RiskRule(BaseModel):
    rule_id: str
    name: str
    fermentation_schemes: list[FermentationScheme]
    condition: str
    action: RuleAction
    reason_code: str
    reason_text_fr: str
    reason_text_en: str
    source_citation: str
    source_url: str = ""
    exceptions: list[str] = Field(default_factory=list)
