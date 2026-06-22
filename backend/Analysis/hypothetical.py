"""hypothetical — Detección de lenguaje hipotético presentado como hecho."""

from __future__ import annotations

import re
from typing import Final

from backend.Analysis.rules_types import RuleResult

_HYPOTHETICAL_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE) for p in (
        r"habría dicho", r"habría ocurrido", r"según trascendió",
        r"se comenta que", r"escena imaginada", r"fuentes cercanas",
        r"todo indicaría", r"aparentemente",
    )
]


def check_hypothetical(text: str) -> RuleResult:
    result = RuleResult()
    t = text or ""
    matches = [m.group(0) for p in _HYPOTHETICAL_RE if (m := p.search(t))]
    if matches:
        result.points += 0.4
        result.reasons.append("hypothetical_or_unverified_claim")
        result.evidence.extend(matches)
    return result


def analyze(text: str) -> RuleResult:
    return check_hypothetical(text)