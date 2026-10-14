"""The constants the frontend copies from the backend, pinned verbatim. The frontend cannot import
them, so B12 copied them; a change on one side fails here until the other side follows:
- frontend/src/tastings/tasting.js: the stop-by reminder's pH line ("Before tasting: " +
  gate.PH_DEADLINE_LINE), gate.ACID_SAFETY_TYPES, routers/tastings.FUTURE_SKEW;
- frontend/src/community/community.js: community.PRIVACY_NOTICE and the schemas.Pseudonym rule
  (its length bounds and pattern);
- frontend/src/ideas/ideas.js: the calibrated trust label (service.CALIBRATED_LABEL) and the
  calibration gate's batch count, display period and "too few" reason;
- the forms' length limits: a community title and a rejection reason, tasting notes, and the
  USDA foods of an Experimental request (the API's maxLength / maxItems).

The sources are read as text: each constant is a one-line `const NAME = value;`.
"""

from __future__ import annotations

import json
import math
import re
import typing
from datetime import timedelta
from pathlib import Path

from pydantic import BaseModel, StringConstraints

from fermenttrack.recommender import calibration, community, gate, service
from fermenttrack.routers.recommendations import TASTING_AFTER_PH
from fermenttrack.routers.tastings import FUTURE_SKEW
from fermenttrack.schemas import (
    CommunityPublishIn,
    CommunityReviewIn,
    Pseudonym,
    RecommendationRequest,
    TastingIn,
)

FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "src"


def _source(relative: str) -> str:
    return (FRONTEND / relative).read_text(encoding="utf-8")


def _const(source: str, name: str) -> str:
    """The value of `[export] const NAME = value;` (a trailing // comment allowed)."""
    found = re.search(
        rf"^(?:export )?const {name} = (.+);(?:\s*//.*)?$", source, flags=re.MULTILINE
    )
    assert found is not None, f"const {name} not found"
    return found.group(1)


def _string(source: str, name: str) -> str:
    """A double-quoted JS string constant (no escapes but JSON's)."""
    raw = _const(source, name)
    assert raw.startswith('"') and raw.endswith('"'), raw
    value = json.loads(raw)
    assert isinstance(value, str)
    return value


def _product(source: str, name: str) -> int:
    """An integer constant written as a product, e.g. `10 * 60 * 1000`."""
    return math.prod(int(x) for x in _const(source, name).split("*"))


def _ms(delta: timedelta) -> int:
    return int(delta.total_seconds() * 1000)


def _limit(model: type[BaseModel], field: str, key: str) -> int:
    """A field's maxLength / maxItems in the model's JSON schema (an optional one's too)."""
    prop = model.model_json_schema()["properties"][field]
    found = [s[key] for s in (prop, *prop.get("anyOf", ())) if key in s]
    assert len(found) == 1, prop
    return int(found[0])


def test_the_form_limits() -> None:
    """The lengths the forms check before sending: the API's own limits."""
    community_js, tasting_js = _source("community/community.js"), _source("tastings/tasting.js")
    assert int(_const(community_js, "TITLE_MAX")) == _limit(
        CommunityPublishIn, "title", "maxLength"
    ) == 120  # fmt: skip
    assert int(_const(community_js, "REASON_MAX")) == _limit(
        CommunityReviewIn, "reason", "maxLength"
    ) == 500  # fmt: skip
    assert int(_const(tasting_js, "NOTES_MAX")) == _limit(TastingIn, "notes", "maxLength") == 1000
    assert int(_const(_source("ideas/ideas.js"), "MAX_USDA")) == _limit(
        RecommendationRequest, "usda_fdc_ids", "maxItems"
    ) == 5  # fmt: skip


def test_the_tasting_form_s_ph_line_and_acid_safety_types() -> None:
    js = _source("tastings/tasting.js")
    ph_line = _string(js, "PH_BEFORE_TASTING")
    assert ph_line == TASTING_AFTER_PH == f"Before tasting: {gate.PH_DEADLINE_LINE}"
    # phLine keeps a reminder's own text from its "Before tasting:" prefix on
    assert 'indexOf("Before tasting:")' in js and ph_line.startswith("Before tasting:")
    found = re.fullmatch(r"new Set\((\[.*\])\)", _const(js, "ACID_SAFETY_TYPES"))
    assert found is not None
    assert set(json.loads(found.group(1))) == gate.ACID_SAFETY_TYPES
    assert _product(js, "FUTURE_SKEW_MS") == _ms(FUTURE_SKEW)


def test_the_community_privacy_notice_and_pseudonym_rule() -> None:
    js = _source("community/community.js")
    assert _string(js, "PRIVACY_NOTICE") == community.PRIVACY_NOTICE
    rule = next(m for m in typing.get_args(Pseudonym)[1:] if isinstance(m, StringConstraints))
    assert rule.strip_whitespace  # pseudonymError trims too
    assert "String(raw ?? \"\").trim()" in js
    assert int(_const(js, "PSEUDONYM_MIN")) == rule.min_length
    assert int(_const(js, "PSEUDONYM_MAX")) == rule.max_length
    # The frontend spells pydantic's (Unicode) \w as the character class W: put \w back.
    found = re.fullmatch(r'new RegExp\(`(.+)`, "u"\)', _const(js, "PSEUDONYM"))
    assert found is not None
    assert found.group(1).replace("[${W}]", r"\w").replace("${W}", r"\w") == rule.pattern
    assert f"`{rule.pattern}`" in js  # the comment that names the rule it copies


def test_the_calibration_constants() -> None:
    js = _source("ideas/ideas.js")
    label = _const(js, "CALIBRATED_LABEL")
    assert label.startswith("/") and label.endswith("/")
    for n in (1, 30, 34, 1234):
        assert re.fullmatch(label[1:-1], service.CALIBRATED_LABEL.format(n=n))
    assert int(_const(js, "GATE_BATCHES")) == calibration.MIN_BATCHES
    assert _product(js, "DISPLAY_FOR_MS") == _ms(calibration.DISPLAY_FOR)
    too_few = _const(js, "TOO_FEW")
    assert too_few == "`fewer than ${GATE_BATCHES} tasted batches`"
    assert too_few.strip("`").replace("${GATE_BATCHES}", str(calibration.MIN_BATCHES)) == (
        calibration.TOO_FEW
    )
