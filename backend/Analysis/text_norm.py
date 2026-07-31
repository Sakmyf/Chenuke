"""text_norm — Normalización de texto para matcheo determinístico.

Chenuke v15.26

El matcheo por regex no debe depender de tildes: en mensajería informal
(WhatsApp, redes sociales) la acentuación es irregular o inexistente, y
ahí es donde vive el caso de uso principal de Chénuke.

Se normaliza para MATCHEAR, pero la evidencia se extrae del texto
ORIGINAL: el usuario tiene que ver la cita tal como está escrita.

La tabla es char-a-char (no NFKD) para garantizar que la longitud se
preserve. Eso hace que los offsets de un match sobre el texto normalizado
sean válidos sobre el texto original. La ñ/Ñ se preserva: no es un acento,
es una letra distinta.
"""

from __future__ import annotations

_ACCENT_MAP = str.maketrans(
    "áàäâãÁÀÄÂÃéèëêÉÈËÊíìïîÍÌÏÎóòöôõÓÒÖÔÕúùüûÚÙÜÛýÝ",
    "aaaaaAAAAAeeeeEEEEiiiiIIIIoooooOOOOOuuuuUUUUyY",
)


def strip_accents(text: str) -> str:
    """Quita tildes preservando longitud y ñ."""
    return (text or "").translate(_ACCENT_MAP)


def norm_for_match(text: str) -> str:
    """Texto listo para regex. Misma longitud que el original."""
    return strip_accents(text)


def evidence_from(original: str, match) -> str:
    """Extrae la cita del texto ORIGINAL usando los offsets de un match
    hecho sobre el texto normalizado."""
    try:
        return (original or "")[match.start():match.end()].strip()
    except Exception:
        return match.group(0)