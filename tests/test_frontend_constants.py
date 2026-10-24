"""The card mirrors a few backend bounds: keep both sides in agreement."""

from pathlib import Path
import re

import pytest

from custom_components.naolib import const

_SRC = Path(__file__).parent.parent / "src"


def _js_constant(module: str, name: str) -> int:
    """Read an ``export const NAME = <int>;`` from a card module."""
    source = (_SRC / module).read_text(encoding="utf-8")
    match = re.search(rf"^export const {name} = (\d+);", source, re.MULTILINE)
    assert match, f"{name} not found in src/{module}"
    return int(match.group(1))


@pytest.mark.parametrize(
    ("backend", "module", "frontend"),
    [
        ("MAX_TIMETABLE_DAY_OFFSET", "constants.js", "MAX_DAY_OFFSET"),
        ("SERVICE_DAY_CUTOFF_HOUR", "constants.js", "SERVICE_DAY_CUTOFF_HOUR"),
        ("MAX_WALK_TIME", "config.js", "MAX_WALK_TIME"),
        ("MIN_AROUND_RADIUS", "around/config.js", "MIN_RADIUS"),
        ("MAX_AROUND_RADIUS", "around/config.js", "MAX_RADIUS"),
        ("MAX_AROUND_MAX_STOPS", "around/config.js", "MAX_STOPS"),
        ("BIKE_NEARBY_LIMIT", "bike/config.js", "MAX_NEARBY_COUNT"),
        ("BIKE_NEARBY_RADIUS_M", "bike/config.js", "MAX_NEARBY_RADIUS"),
    ],
)
def test_the_card_mirrors_the_backend_bounds(
    backend: str, module: str, frontend: str
) -> None:
    """A bound the card enforces matches the one the backend applies."""
    assert _js_constant(module, frontend) == getattr(const, backend)
