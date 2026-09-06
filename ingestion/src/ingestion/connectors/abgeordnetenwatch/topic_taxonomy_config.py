# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Maps the 53 canonical AbgeordnetenWatch Themen to the governance levels a federal
(Bundestag) vote on that topic is relevant to — FEDERAL, or FEDERAL + STATE — for
the vote down-rank.

The 53 ``TOPIC_TAXONOMY`` keys are the exact long-form labels verified from the AW
v2 ``/topics`` endpoint; they are never re-fetched at runtime. The topic objects
EMBEDDED in a poll response (``field_topics[*].label``) may instead carry a
truncated pre-comma short form of a canonical label (verified: golden fixture
poll 3602 carries "Öffentliche Finanzen" for the canonical "Öffentliche Finanzen,
Steuern und Abgaben"). ``_TOPIC_ALIASES`` maps these short forms to the same
levels as their canonical key so embedded labels resolve without the max-recall
ALL_LEVELS fallback.

Level assignment follows the Grundgesetz division of competence (verified against
gesetze-im-internet.de/gg):

  - Art. 73 (ausschließliche Bundesgesetzgebung): exclusively federal → FEDERAL,
    unless the matter is executed by the Länder or lands on residents (e.g. Art. 73(1)
    Verteidigung including "Schutz der Zivilbevölkerung"), which adds STATE.
  - Art. 74 (konkurrierende Gesetzgebung) with Art. 83 ("die Länder führen die
    Bundesgesetze als eigene Angelegenheit aus"): federal law executed by the Länder,
    often co-funded (Art. 104a) → FEDERAL + STATE.
  - Art. 70 (residual): matters not assigned to the Bund are Land competence. A
    federal vote on them is FEDERAL, unless a federal funding/framework hook exists
    (Art. 91b Wissenschaft/Forschung/Bildung, Art. 104a/104c financing), which adds STATE.
  - Art. 23 (Länder co-decide and execute EU law) and Art. 1(3) (Grundrechte bind
    federal and Länder authority) → FEDERAL + STATE.

FEDERAL means the vote should rank below the Landtag votes in a state chat;
FEDERAL + STATE means it stays visible there.
"""

from __future__ import annotations

import logging
import re
from typing import FrozenSet

# The governance-level constants are owned by the shared framework module
# ingestion/src/ingestion/governance_levels.py (retrieve.py imports from there without touching a
# connector). Re-exported here because the taxonomy dict below, the AW
# connector, and the AW tests all reference them from this module.
from wahlchat_common.governance_levels import (  # noqa: F401
    ALL_LEVELS,
    FEDERAL,
    MUNICIPAL,
    STATE,
)

logger = logging.getLogger(__name__)

# AW injects invisible formatting characters into label strings (notably the U+00AD
# soft hyphen inside "BÜNDNIS 90/­DIE GRÜNEN", and the same family appears in topic
# labels). They must be stripped before the exact TOPIC_TAXONOMY lookup — otherwise an
# affected label silently misses every key and falls back to ALL_LEVELS, which makes an
# affected federal vote over-surface in state/municipal chats instead of being down-ranked.
_INVISIBLE_CHARS_RE = re.compile("[\u00ad\u200b\u200c\u200d\u2060\ufeff]")


def _normalize_topic_label(label: str) -> str:
    """Strip invisible/zero-width formatting characters and surrounding whitespace so an
    AW topic label matches the TOPIC_TAXONOMY keys exactly."""
    return _INVISIBLE_CHARS_RE.sub("", label).strip()


# ---------------------------------------------------------------------------
# Governance level constants: re-exported from wahlchat_common.governance_levels above —
# do NOT re-introduce local definitions (a parity test in
# tests/ingestion/test_enum_parity.py guards this).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# TOPIC_TAXONOMY — AW topic label → governance relevance levels (frozenset).
#
# Keys must match field_topics[*].label exactly. 53 entries.
# Each value cites its governing GG article.
#
# No topic is tagged MUNICIPAL: AW has no municipal parliament data, so a
# Kommunalwahl context down-ranks all federal+state votes uniformly.
# ---------------------------------------------------------------------------

TOPIC_TAXONOMY: dict[str, FrozenSet[str]] = {
    # -----------------------------------------------------------------------
    # FEDERAL only.
    # -----------------------------------------------------------------------
    # Art. 73(5) — Zoll- und Handelsgebiet, Waren- und Zahlungsverkehr mit dem Ausland.
    "Außenwirtschaft": frozenset({FEDERAL}),
    # Art. 73(1) — auswärtige Angelegenheiten.
    "Entwicklungspolitik": frozenset({FEDERAL}),
    # Art. 73(1) — auswärtige Angelegenheiten.
    "Humanitäre Hilfe": frozenset({FEDERAL}),
    # Bundestag advisory function (TAB) — no Land competence.
    "Technologiefolgenabschätzung": frozenset({FEDERAL}),
    # Art. 38-48 — the Bundestag as a federal organ.
    "Bundestag": frozenset({FEDERAL}),
    # Art. 40(1) — Bundestag's rules of procedure.
    "Geschäftsordnung": frozenset({FEDERAL}),
    # Art. 46 — immunity of Bundestag members.
    "Immunität": frozenset({FEDERAL}),
    # Art. 45c — Bundestag petitions committee.
    "Petitionen": frozenset({FEDERAL}),
    # Art. 41 — scrutiny of Bundestag elections.
    "Wahlprüfung": frozenset({FEDERAL}),
    # Historical federal matter — no current Land competence.
    "Deutsche Einheit / Innerdeutsche Beziehungen (bis 1990)": frozenset({FEDERAL}),
    # Federal Lobbyregister (Bundestag); Länder regulate their own transparency (Art. 70).
    "Lobbyismus & Transparenz": frozenset({FEDERAL}),
    # Art. 21(5) — "Das Nähere regeln Bundesgesetze" (party law is federal).
    "Politisches Leben, Parteien": frozenset({FEDERAL}),
    # Art. 32 + 73(1) — auswärtige Angelegenheiten are exclusively federal.
    "Außenpolitik und internationale Beziehungen": frozenset({FEDERAL}),
    # -----------------------------------------------------------------------
    # FEDERAL + STATE.
    # -----------------------------------------------------------------------
    # Art. 73(1) — Verteidigung incl. "Schutz der Zivilbevölkerung", executed by the
    # Länder (Katastrophenschutz).
    "Verteidigung": frozenset({FEDERAL, STATE}),
    # Art. 73(14) Kernenergie/Strahlenschutz, executed by the Länder as
    # Bundesauftragsverwaltung (Art. 85): plant siting, evacuation planning and state
    # environment ministries make it highly state-salient — same execution-by-Länder
    # rationale that keeps Verteidigung FEDERAL + STATE.
    "Reaktorsicherheit": frozenset({FEDERAL, STATE}),
    # Art. 70 — Kulturhoheit der Länder: culture is a core Land competence, so a federal
    # vote touching it is directly relevant to state voters (narrow federal hook: Art. 73(5a)).
    "Kultur": frozenset({FEDERAL, STATE}),
    # Art. 70 — tourism is residual Land competence; kept consistent with
    # "Sport, Freizeit und Tourismus" which is also FEDERAL + STATE.
    "Tourismus": frozenset({FEDERAL, STATE}),
    # Art. 23 — Länder co-decide EU policy via the Bundesrat and execute EU law.
    "Europapolitik und Europäische Union": frozenset({FEDERAL, STATE}),
    # Art. 1(3) — Grundrechte bind Gesetzgebung, vollziehende Gewalt und Rechtsprechung
    # at both levels.
    "Menschenrechte": frozenset({FEDERAL, STATE}),
    # Art. 74(12) — Arbeitsrecht und Sozialversicherung.
    "Arbeit und Beschäftigung": frozenset({FEDERAL, STATE}),
    # Art. 74(7) öffentliche Fürsorge, 74(12) Sozialversicherung; execution/co-funding
    # Art. 83/104a.
    "Soziale Sicherung": frozenset({FEDERAL, STATE}),
    # Art. 74(19) übertragbare Krankheiten und Heilberufe, 74(19a) Krankenhäuser.
    "Gesundheit": frozenset({FEDERAL, STATE}),
    # Art. 105-106 — Steuergesetzgebung und Länderanteil an den Gemeinschaftsteuern.
    "Öffentliche Finanzen, Steuern und Abgaben": frozenset({FEDERAL, STATE}),
    # Art. 105-106.
    "Finanzen": frozenset({FEDERAL, STATE}),
    # Art. 109 — Haushaltswirtschaft von Bund und Ländern; Schuldenbremse.
    "Haushalt": frozenset({FEDERAL, STATE}),
    # Art. 74(11) — Recht der Wirtschaft.
    "Wirtschaft": frozenset({FEDERAL, STATE}),
    # Art. 74(11) — Energiewirtschaft (Recht der Wirtschaft).
    "Energie": frozenset({FEDERAL, STATE}),
    # Art. 74(24) — Luftreinhaltung; Länder execute (Art. 83).
    "Klima": frozenset({FEDERAL, STATE}),
    # Art. 74(24) Abfall/Luft/Lärm, 74(29) Naturschutz, 74(32) Wasserhaushalt.
    "Umwelt": frozenset({FEDERAL, STATE}),
    # Art. 74(29) — Naturschutz und Landschaftspflege.
    "Naturschutz": frozenset({FEDERAL, STATE}),
    # Art. 74(22) Straßenverkehr und Fernstraßen, 74(23) Schienenbahnen; Art. 73(6/6a)
    # Luftverkehr/Bundeseisenbahnen.
    "Verkehr": frozenset({FEDERAL, STATE}),
    # Art. 91b (Bund-Länder education co-funding), Art. 104c (school infrastructure),
    # Art. 74(33) Hochschulzulassung.
    "Bildung und Erziehung": frozenset({FEDERAL, STATE}),
    # Art. 74(18) Bodenrecht/Wohnungswesen/Siedlungswesen, 74(31) Raumordnung.
    "Raumordnung, Bau- und Wohnungswesen": frozenset({FEDERAL, STATE}),
    # Art. 74(17) landwirtschaftliche Erzeugung und Ernährungssicherung, 74(20) Lebensmittelrecht.
    "Landwirtschaft und Ernährung": frozenset({FEDERAL, STATE}),
    # Art. 74(4) Aufenthalts- und Niederlassungsrecht der Ausländer, 74(6) Flüchtlinge;
    # Länder execute (Art. 83/104a).
    "Migration und Aufenthaltsrecht": frozenset({FEDERAL, STATE}),
    # Art. 74(1) Strafrecht, Art. 73(9a/10) BKA und Bundespolizei; general policing is
    # residual Land competence (Art. 70).
    "Innere Sicherheit": frozenset({FEDERAL, STATE}),
    # Art. 74(3) Vereinsrecht, Art. 73(3) Melde- und Ausweiswesen.
    "Innere Angelegenheiten": frozenset({FEDERAL, STATE}),
    # Art. 83-85 (Länder execute federal law), Art. 74(27) Beamtenstatusrecht.
    "Staat und Verwaltung": frozenset({FEDERAL, STATE}),
    # Art. 74(1) — bürgerliches Recht, Strafrecht, Gerichtsverfassung; Länder execute
    # (Art. 83/92).
    "Recht": frozenset({FEDERAL, STATE}),
    # Art. 74(7) — öffentliche Fürsorge.
    "Gesellschaftspolitik, soziale Gruppen": frozenset({FEDERAL, STATE}),
    # Art. 74(7) öffentliche Fürsorge, Art. 6 Schutz der Familie; Länder execute and
    # co-fund (Art. 104a).
    "Familie": frozenset({FEDERAL, STATE}),
    # Art. 3(2) Gleichberechtigung (binds both), Art. 74(7) öffentliche Fürsorge.
    "Frauen": frozenset({FEDERAL, STATE}),
    # Art. 74(7) — öffentliche Fürsorge (Kinder- und Jugendhilfe).
    "Jugend": frozenset({FEDERAL, STATE}),
    # Art. 74(12) Sozialversicherung, 74(7) öffentliche Fürsorge.
    "Senioren": frozenset({FEDERAL, STATE}),
    # Art. 73(7) Telekommunikation, Art. 91c (Bund-Länder IT-Systeme).
    "Digitale Agenda": frozenset({FEDERAL, STATE}),
    # Art. 73(7), Art. 87f — Telekommunikation.
    "digitale Infrastruktur": frozenset({FEDERAL, STATE}),
    # Art. 73(7) Telekommunikation (federal); Rundfunk is Land competence (Art. 70).
    "Medien, Kommunikation und Informationstechnik": frozenset({FEDERAL, STATE}),
    # Art. 73(7) Telekommunikation; Rundfunkhoheit der Länder (Art. 70).
    "Medien": frozenset({FEDERAL, STATE}),
    # Art. 74(1) — Anti-Doping-Gesetz (Strafrecht); otherwise residual Land competence (Art. 70).
    "Sport": frozenset({FEDERAL, STATE}),
    # Art. 74(1) doping/Strafrecht for Sport; Freizeit and Tourismus are residual Länder (Art. 70).
    "Sport, Freizeit und Tourismus": frozenset({FEDERAL, STATE}),
    # Art. 74(11) Recht der Wirtschaft, 74(1) bürgerliches Recht.
    "Verbraucherschutz": frozenset({FEDERAL, STATE}),
    # Art. 74(13) Forschungsförderung, Art. 91b (Bund-Länder co-funding).
    "Forschung": frozenset({FEDERAL, STATE}),
    # Art. 91b, Art. 74(13), 74(33) Hochschulzulassung.
    "Wissenschaft, Forschung und Technologie": frozenset({FEDERAL, STATE}),
}


# ---------------------------------------------------------------------------
# _TOPIC_ALIASES — short-form labels observed in EMBEDDED poll field_topics.
#
# The AW /topics endpoint returns the long canonical labels keyed in
# TOPIC_TAXONOMY above, but the topic objects embedded in a poll response may
# carry a truncated pre-comma short form (verified: golden fixture poll 3602,
# topic 22, carries "Öffentliche Finanzen"). Each alias maps to the SAME levels
# as its canonical key.
#
# Conservative scope: only pre-comma truncations of comma-containing canonical
# keys are aliased — that is the one attested truncation mechanism. Pre-comma
# prefixes that are already canonical keys with identical levels ("Medien" for
# "Medien, Kommunikation und Informationstechnik", "Sport" for "Sport, Freizeit
# und Tourismus") need no alias. "und"-joined keys without a comma have no
# attested short form and are deliberately NOT aliased.
# ---------------------------------------------------------------------------

_TOPIC_ALIASES: dict[str, FrozenSet[str]] = {
    # Verified from the repo's own golden fixture (poll 3602).
    "Öffentliche Finanzen": TOPIC_TAXONOMY["Öffentliche Finanzen, Steuern und Abgaben"],
    # Same pre-comma truncation mechanism for the remaining comma-containing keys.
    "Raumordnung": TOPIC_TAXONOMY["Raumordnung, Bau- und Wohnungswesen"],
    "Gesellschaftspolitik": TOPIC_TAXONOMY["Gesellschaftspolitik, soziale Gruppen"],
    "Politisches Leben": TOPIC_TAXONOMY["Politisches Leben, Parteien"],
    "Wissenschaft": TOPIC_TAXONOMY["Wissenschaft, Forschung und Technologie"],
}


def get_relevance_levels(
    topic_labels: list[str],
    *,
    warn_on_missing_topics: bool = True,
) -> list[str]:
    """Return the sorted union of governance levels for the given topic labels.

    Unknown labels or empty input default to all levels (max recall). Unknown
    labels ALWAYS log a warning (an unmapped label is actionable everywhere).
    Empty input logs a warning only when ``warn_on_missing_topics`` is True —
    Landtag polls routinely carry no field_topics, so callers pass False for
    non-federal legislatures to avoid one noise WARNING per poll burying
    actionable warnings (federal polls keep the loud default).

    Args:
        topic_labels: List of AW field_topics[*].label strings for a poll. Labels are
            cast to str before lookup (untrusted AW payload; used only as dict keys).
        warn_on_missing_topics: Emit the no-field_topics WARNING on empty input
            (True, default — federal polls); False logs at DEBUG instead
            (non-federal legislatures where missing topics are the norm).

    Returns:
        Sorted list of governance level strings, e.g. ['federal', 'state'].
        Returns sorted(ALL_LEVELS) for unknown labels or empty input.
    """
    if not topic_labels:
        if warn_on_missing_topics:
            logger.warning(
                "AW poll has no field_topics — defaulting to all levels. "
                "This vote will surface across all election level contexts."
            )
        else:
            logger.debug(
                "AW poll has no field_topics — defaulting to all levels "
                "(expected for this legislature; suppressing per-poll warning)."
            )
        return sorted(ALL_LEVELS)

    result: set[str] = set()
    for label in topic_labels:
        safe_label = _normalize_topic_label(str(label))
        mapped = TOPIC_TAXONOMY.get(safe_label)
        if mapped is None:
            # Embedded poll payloads may carry the pre-comma short form.
            mapped = _TOPIC_ALIASES.get(safe_label)
        if mapped is None:
            logger.warning(
                "AW Thema %r is not in TOPIC_TAXONOMY — defaulting to all levels. "
                "Add it to topic_taxonomy_config.py.",
                safe_label,
            )
            result.update(ALL_LEVELS)
        else:
            result.update(mapped)

    return sorted(result)
