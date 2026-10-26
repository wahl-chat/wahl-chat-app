# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt for translating UI messages.

Answers come back as the feed translation's ``TranslationBatch`` (one entry
per numbered segment), the format that keeps the model from running past a
text into translation-tool footers.
"""

from __future__ import annotations

# The same editorial rule the feed's prompts use, so UI text is held to it too.
from src.feed.prompts import _NEUTRALITY_RULE

# Stored per translated key: bumping it re-translates on the next run.
CATALOG_PROMPT_VERSION = "1"

CATALOG_TRANSLATION_PROMPT = f"""\
Du übersetzt die Texte der Benutzeroberfläche von wahl.chat, einer neutralen \
Informationsplattform zu Wahlen und Parlamenten in Deutschland, ins \
{{language}}. Jeder Abschnitt ist ein eigener Text der Oberfläche: Knöpfe, \
Überschriften, Hinweise, Fehlermeldungen.

Regeln:
- Übersetze treu und im Ton der Oberfläche: knapp, freundlich, die Leserin \
direkt und informell ansprechen (wie das deutsche „du“). Nichts hinzufügen, \
nichts weglassen.
- {_NEUTRALITY_RULE}
- Platzhalter in geschweiften Klammern ({{{{name}}}}, {{{{count}}}}) unverändert und \
unübersetzt übernehmen. In ICU-Ausdrücken wie {{{{count, plural, one {{{{…}}}} \
other {{{{…}}}}}}}} bleiben Schlüsselwörter (plural, select, one, other, =0, #) \
unverändert; nur die Texte in den Zweigen werden übersetzt.
- Markierungen wie <link>…</link> oder <strong>…</strong> bleiben mit \
demselben Namen erhalten; nur der Text dazwischen wird übersetzt.
- wahl.chat, Parteinamen, Personennamen und Eigennamen deutscher \
Institutionen (z. B. Bundestag, Landtag) bleiben unverändert, wenn es keine \
übliche Übersetzung gibt.
- Jeder Abschnitt wird für sich übersetzt: genau ein Eintrag je Abschnitt, \
mit seiner Kennung, und nur der übersetzte Text, ohne Anmerkungen.
- Die Kennungen (S1, S2, …) gehören NUR in ref, nie in die übersetzten Texte.

Abschnitte:
{{segments}}
"""

# How the prompt names each target language ("ins …"). A language missing
# here falls back to its code.
LANGUAGE_NAMES_DE: dict[str, str] = {
    "en": "Englische (britisches Englisch)",
    "fr": "Französische",
    "es": "Spanische",
    "it": "Italienische",
    "pl": "Polnische",
    "tr": "Türkische",
    "uk": "Ukrainische",
    "ar": "Arabische",
}


def format_catalog_prompt(locale: str, segments_block: str) -> str:
    return CATALOG_TRANSLATION_PROMPT.format(
        language=LANGUAGE_NAMES_DE.get(locale, locale), segments=segments_block
    )
