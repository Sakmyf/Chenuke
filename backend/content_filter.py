"""content_filter.py — Filtro de contenido explícito (privacidad por diseño).

Propósito ético (ETHICS.md §2.4 — Privacidad como derecho):
Cuando el usuario navega contenido sexual/adulto, SignalCheck NO debe analizarlo,
NO debe almacenar la URL en cache ni en logs, ni dejar rastro alguno de esa visita.
La minimización de datos prima sobre la cobertura del análisis.

Esto NO es censura ni juicio moral sobre el contenido: el sistema simplemente se
abstiene de procesar y registrar páginas íntimas del usuario. Devuelve un estado
neutral de "no analizado" sin score de riesgo.

Decisión deliberada: dominio O señales léxicas. No basta whitelist de dominios
porque hay miles; las señales léxicas cubren el resto sin guardar la URL.
"""

from __future__ import annotations

import re
from typing import Final
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Dominios adultos frecuentes (LATAM + internacionales).
# Lista no exhaustiva: el detector léxico cubre el resto.
# Solo se usa el host, nunca se loguea la URL.
# ---------------------------------------------------------------------------

_ADULT_DOMAINS: Final[frozenset[str]] = frozenset({
    "pornhub.com", "xvideos.com", "xn