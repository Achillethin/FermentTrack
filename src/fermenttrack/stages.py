"""Multi-substrate stage state machines (docs/ARCHITECTURE.md § Stage State Machines).

Kombucha: brew_sweet_tea -> 1F (7-14 days) -> 2F_flavoring (2-4 days) -> bottling
          -> conditioning (2-5 days) -> ready
Sourdough: feed_starter -> bulk_ferment (4-12h) -> shape -> cold_retard (8-24h)
           -> bake -> done
Koji: soak -> steam -> inoculate -> incubate (36-48h) -> harvest -> done
Cheese: heat_milk -> culture -> rennet -> cut_curd -> cook -> press -> salt
        -> age -> ready
Lacto-ferment (kimchi, sauerkraut, chilies, general veg ferments):
        prep_and_salt -> ferment (~7 days) -> ready
Miso: cook_soybeans -> mix_koji_salt -> ferment (~90 days) -> ready
Garum (fermented fish sauce): salt_fish -> ferment (~180 days) -> strain -> ready

Kefir and vinegar have Ingredient/BatchIngredient recipe-logging support
(see models.py) but no stage machine here yet. Batches for those
substrates get a single "in_progress" pseudo-stage with no reminder
automation until a real state machine is documented for them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class StageDef:
    name: str
    next_stage: str | None
    expected_duration: timedelta | None  # None = no timer-based reminder (e.g. terminal stage)
    reminder_action: str | None
    urgency: str  # low | medium | high | critical


# Bottling carries the over-carbonation / glass-explosion risk called out in
# ARCHITECTURE.md -> critical urgency.
KOMBUCHA_STAGES: dict[str, StageDef] = {
    "brew_sweet_tea": StageDef(
        name="brew_sweet_tea",
        next_stage="1F",
        expected_duration=timedelta(hours=1),
        reminder_action="cool tea to room temp, add SCOBY, start 1F",
        urgency="low",
    ),
    "1F": StageDef(
        name="1F",
        next_stage="2F_flavoring",
        expected_duration=timedelta(days=10),  # midpoint of 7-14 day range
        reminder_action="taste test — check for readiness to move to 2F",
        urgency="medium",
    ),
    "2F_flavoring": StageDef(
        name="2F_flavoring",
        next_stage="bottling",
        expected_duration=timedelta(days=3),  # midpoint of 2-4 day range
        reminder_action="check carbonation before bottling",
        urgency="medium",
    ),
    "bottling": StageDef(
        name="bottling",
        next_stage="conditioning",
        expected_duration=timedelta(days=1),
        reminder_action="burp bottles — over-carbonation risk (glass explosion) after day 5",
        urgency="critical",
    ),
    "conditioning": StageDef(
        name="conditioning",
        next_stage="ready",
        expected_duration=timedelta(days=3),  # midpoint of 2-5 day range
        reminder_action="check conditioning progress, move to fridge when ready",
        urgency="high",
    ),
    "ready": StageDef(
        name="ready",
        next_stage=None,
        expected_duration=None,
        reminder_action=None,
        urgency="low",
    ),
}

SOURDOUGH_STAGES: dict[str, StageDef] = {
    "feed_starter": StageDef(
        name="feed_starter",
        next_stage="bulk_ferment",
        expected_duration=timedelta(hours=1),
        reminder_action="starter fed — watch for peak activity before mixing dough",
        urgency="low",
    ),
    "bulk_ferment": StageDef(
        name="bulk_ferment",
        next_stage="shape",
        expected_duration=timedelta(hours=8),  # midpoint of 4-12h range
        reminder_action="check dough rise — shape when doubled",
        urgency="medium",
    ),
    "shape": StageDef(
        name="shape",
        next_stage="cold_retard",
        expected_duration=timedelta(hours=1),
        reminder_action="dough shaped — move to fridge for cold retard",
        urgency="low",
    ),
    "cold_retard": StageDef(
        name="cold_retard",
        next_stage="bake",
        expected_duration=timedelta(hours=16),  # midpoint of 8-24h range
        reminder_action="cold retard complete — preheat oven and bake",
        urgency="medium",
    ),
    "bake": StageDef(
        name="bake",
        next_stage="done",
        expected_duration=timedelta(minutes=45),
        reminder_action="check internal temp / crust color — pull when done",
        urgency="high",
    ),
    "done": StageDef(
        name="done",
        next_stage=None,
        expected_duration=None,
        reminder_action=None,
        urgency="low",
    ),
}

KOJI_STAGES: dict[str, StageDef] = {
    "soak": StageDef(
        name="soak",
        next_stage="steam",
        expected_duration=timedelta(hours=8),
        reminder_action="soak complete — drain and steam",
        urgency="low",
    ),
    "steam": StageDef(
        name="steam",
        next_stage="inoculate",
        expected_duration=timedelta(hours=1),
        reminder_action="steaming complete — cool to inoculation temp and add spores",
        urgency="medium",
    ),
    "inoculate": StageDef(
        name="inoculate",
        next_stage="incubate",
        expected_duration=timedelta(hours=1),
        reminder_action="spores mixed in — move to incubation",
        urgency="low",
    ),
    "incubate": StageDef(
        name="incubate",
        next_stage="harvest",
        expected_duration=timedelta(hours=42),  # midpoint of 36-48h range
        reminder_action="check for even white mycelium coverage — harvest when ready",
        urgency="high",
    ),
    "harvest": StageDef(
        name="harvest",
        next_stage="done",
        expected_duration=timedelta(hours=1),
        reminder_action="koji harvested — cool and use or store",
        urgency="medium",
    ),
    "done": StageDef(
        name="done",
        next_stage=None,
        expected_duration=None,
        reminder_action=None,
        urgency="low",
    ),
}

CHEESE_STAGES: dict[str, StageDef] = {
    "heat_milk": StageDef(
        name="heat_milk",
        next_stage="culture",
        expected_duration=timedelta(minutes=30),
        reminder_action="milk at temp — add starter culture",
        urgency="low",
    ),
    "culture": StageDef(
        name="culture",
        next_stage="rennet",
        expected_duration=timedelta(hours=1),
        reminder_action="culture ripening complete — add rennet",
        urgency="medium",
    ),
    "rennet": StageDef(
        name="rennet",
        next_stage="cut_curd",
        expected_duration=timedelta(hours=1),
        reminder_action="check for clean break — cut the curd",
        urgency="medium",
    ),
    "cut_curd": StageDef(
        name="cut_curd",
        next_stage="cook",
        expected_duration=timedelta(minutes=15),
        reminder_action="curd cut — begin cooking",
        urgency="low",
    ),
    "cook": StageDef(
        name="cook",
        next_stage="press",
        expected_duration=timedelta(hours=1),
        reminder_action="cooking complete — drain whey and press",
        urgency="medium",
    ),
    "press": StageDef(
        name="press",
        next_stage="salt",
        expected_duration=timedelta(hours=6),
        reminder_action="pressing complete — salt or brine the cheese",
        urgency="medium",
    ),
    "salt": StageDef(
        name="salt",
        next_stage="age",
        expected_duration=timedelta(hours=12),
        reminder_action="salting complete — move to aging",
        urgency="low",
    ),
    "age": StageDef(
        name="age",
        next_stage="ready",
        expected_duration=timedelta(days=14),
        reminder_action="check rind development and turn the wheel",
        urgency="medium",
    ),
    "ready": StageDef(
        name="ready",
        next_stage=None,
        expected_duration=None,
        reminder_action=None,
        urgency="low",
    ),
}

LACTO_FERMENT_STAGES: dict[str, StageDef] = {
    "prep_and_salt": StageDef(
        name="prep_and_salt",
        next_stage="ferment",
        expected_duration=timedelta(hours=1),
        reminder_action="salted/brined — ensure vegetables stay fully submerged to avoid mold",
        urgency="medium",
    ),
    "ferment": StageDef(
        name="ferment",
        next_stage="ready",
        expected_duration=timedelta(days=7),
        reminder_action="taste test — continue fermenting or move to the fridge",
        urgency="medium",
    ),
    "ready": StageDef(
        name="ready",
        next_stage=None,
        expected_duration=None,
        reminder_action=None,
        urgency="low",
    ),
}

MISO_STAGES: dict[str, StageDef] = {
    "cook_soybeans": StageDef(
        name="cook_soybeans",
        next_stage="mix_koji_salt",
        expected_duration=timedelta(hours=3),
        reminder_action="soybeans cooked and cooled — mix with koji and salt",
        urgency="low",
    ),
    "mix_koji_salt": StageDef(
        name="mix_koji_salt",
        next_stage="ferment",
        expected_duration=timedelta(hours=1),
        reminder_action="mixed and packed into the vessel — begin fermentation",
        urgency="low",
    ),
    "ferment": StageDef(
        name="ferment",
        next_stage="ready",
        expected_duration=timedelta(days=90),
        reminder_action="check for surface mold, press down, taste periodically",
        urgency="medium",
    ),
    "ready": StageDef(
        name="ready",
        next_stage=None,
        expected_duration=None,
        reminder_action=None,
        urgency="low",
    ),
}

GARUM_STAGES: dict[str, StageDef] = {
    "salt_fish": StageDef(
        name="salt_fish",
        next_stage="ferment",
        expected_duration=timedelta(hours=1),
        reminder_action="fish salted and packed — begin fermentation",
        urgency="low",
    ),
    "ferment": StageDef(
        name="ferment",
        next_stage="strain",
        expected_duration=timedelta(days=180),
        reminder_action="check color and aroma development",
        urgency="medium",
    ),
    "strain": StageDef(
        name="strain",
        next_stage="ready",
        expected_duration=timedelta(hours=1),
        reminder_action="strain liquid from solids — garum is ready to bottle",
        urgency="low",
    ),
    "ready": StageDef(
        name="ready",
        next_stage=None,
        expected_duration=None,
        reminder_action=None,
        urgency="low",
    ),
}

STAGE_MACHINES: dict[str, dict[str, StageDef]] = {
    "kombucha": KOMBUCHA_STAGES,
    "sourdough": SOURDOUGH_STAGES,
    "koji": KOJI_STAGES,
    "cheese": CHEESE_STAGES,
    "lacto_ferment": LACTO_FERMENT_STAGES,
    "miso": MISO_STAGES,
    "garum": GARUM_STAGES,
}

STAGE_ORDER: dict[str, list[str]] = {
    "kombucha": ["brew_sweet_tea", "1F", "2F_flavoring", "bottling", "conditioning", "ready"],
    "sourdough": ["feed_starter", "bulk_ferment", "shape", "cold_retard", "bake", "done"],
    "koji": ["soak", "steam", "inoculate", "incubate", "harvest", "done"],
    "cheese": ["heat_milk", "culture", "rennet", "cut_curd", "cook", "press", "salt", "age", "ready"],
    "lacto_ferment": ["prep_and_salt", "ferment", "ready"],
    "miso": ["cook_soybeans", "mix_koji_salt", "ferment", "ready"],
    "garum": ["salt_fish", "ferment", "strain", "ready"],
}

# Pseudo-stage for substrates with no registered stage machine (kefir, miso,
# vinegar today, and any future substrate not yet documented in
# ARCHITECTURE.md). No reminder, no progression — recipe logging still
# works via Ingredient/BatchIngredient regardless.
_NO_MACHINE_STAGE = StageDef(
    name="in_progress",
    next_stage=None,
    expected_duration=None,
    reminder_action=None,
    urgency="low",
)


class InvalidStageError(ValueError):
    pass


def get_stage(substrate: str, name: str) -> StageDef:
    machine = STAGE_MACHINES.get(substrate)
    if machine is None:
        if name == _NO_MACHINE_STAGE.name:
            return _NO_MACHINE_STAGE
        raise InvalidStageError(
            f"Substrate {substrate!r} has no stage machine; only "
            f"{_NO_MACHINE_STAGE.name!r} is valid, got {name!r}"
        )
    try:
        return machine[name]
    except KeyError:
        raise InvalidStageError(f"Unknown {substrate} stage: {name!r}") from None


def next_stage_name(substrate: str, current: str) -> str | None:
    return get_stage(substrate, current).next_stage


def first_stage(substrate: str) -> str:
    order = STAGE_ORDER.get(substrate)
    return order[0] if order else _NO_MACHINE_STAGE.name
