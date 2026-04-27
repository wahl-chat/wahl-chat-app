"""Prompt templates for quiz generator agent."""

# Designed cross-party overlaps. These are the six positions where the
# study deliberately broke the clean left/right alignment by giving two
# parties the same direction with different framings — testing whether
# participants engaged with the *reasoning* rather than relying on a
# left/right heuristic.
OVERLAP_THEMES = [
    {
        "name": "Direktes Klimageld / Pro-Kopf-Rückzahlung der CO2-Einnahmen",
        "parties": ["venus", "mars"],
        "frame": "Venus: soziale Gerechtigkeit; Mars: Markt-Akzeptanz in der Mitte.",
    },
    {
        "name": "CO2-Grenzausgleich (CBAM) / Schutz deutscher Industrie vor Importen",
        "parties": ["mars", "saturn"],
        "frame": "Mars: industriepolitische Notwendigkeit; Saturn: Schutz deutscher Arbeitsplätze.",
    },
    {
        "name": "Beamte und Abgeordnete in die gesetzliche Rente einbeziehen",
        "parties": ["venus", "saturn"],
        "frame": "Venus: egalitär/Privilegien beenden; Saturn: anti-elite Volk-vs-Politik.",
    },
    {
        "name": "Erziehungs- und Pflegezeiten in der Rente voll anerkennen (Sorgearbeit)",
        "parties": ["venus", "mars"],
        "frame": "Venus: Geschlechtergerechtigkeit; Mars: Familie als Leistung.",
    },
    {
        "name": "Eigenständige Kindergrundsicherung außerhalb des Bürgergelds",
        "parties": ["venus", "mars"],
        "frame": "Venus: Kinderarmut bekämpfen; Mars: Bürokratieabbau und Bildungschancen.",
    },
    {
        "name": "Höherer Bürgergeld-Regelsatz",
        "parties": ["venus", "saturn"],
        "frame": "Venus: für alle (+50€ Anhebung); Saturn: nur für Beitragszahler ab 15 Jahren.",
    },
]


def _format_overlap_themes() -> str:
    lines = []
    for i, t in enumerate(OVERLAP_THEMES, 1):
        parties = " + ".join(f"[PARTY_BADGE:{p}]" for p in t["parties"])
        lines.append(f'{i}. **{t["name"]}** — {parties}\n   Frames: {t["frame"]}')
    return "\n".join(lines)


SYSTEM_PROMPT = f"""Du bist ein Experte für die Erstellung von Multiple-Choice-Fragen zur Überprüfung des Wissenserwerbs.

**Studienkontext:**
Die Fragen sind Teil einer wissenschaftlichen Studie zur politischen Informationsvermittlung. Teilnehmende haben zuvor mit einem Chatbot über die Positionen dreier (fiktiver) Parteien gesprochen und werden nun in einem Quiz auf ihren Wissenserwerb getestet. Als Anreiz wird unter den Teilnehmenden mit den besten Quiz-Ergebnissen ein **20 € Amazon-Gutschein** verlost — die Antworten werden also bewusst und konzentriert gegeben. Das Quiz muss daher fair, eindeutig und gut diskriminierend sein, weil es echte Belohnungs-Konsequenzen für die Teilnehmenden hat.

**Antwortformat:**
Jede Frage ist **Single Choice** — es gibt genau **eine richtige Antwort** unter den vier inhaltlichen Optionen. Die Teilnehmenden können zusätzlich "Weiß ich nicht" wählen (wird vom System angefügt, nicht von dir). Mehrfachauswahl ist nicht möglich. Formuliere Frage und Optionen so, dass für eine informierte Person genau eine Option eindeutig korrekt ist und die anderen drei eindeutig falsch sind.

**Aufgabe:**
Erstelle basierend auf einer Chat-Konversation über politische Themen Multiple-Choice-Fragen, die testen, ob jemand die **grobe Ausrichtung der Parteien** sowie deren **Position zu einzelnen Themen** verstanden hat — also sowohl die generelle Grundhaltung ("pro/contra", "mehr Staat/mehr Markt", "Ausbau/Rückbau") als auch, ob eine Partei ein konkretes Thema (z. B. Klimageld, CBAM, Beamte in die Rente) befürwortet oder ablehnt. Was NICHT getestet wird, sind Detail-Mechaniken: Zahlen, Eurobeträge, Jahre, exakte Instrumenten-Ausgestaltung oder genaue Formulierungen.

**Richtlinien für gute Fragen:**

1. **Allgemeine Ausrichtung ODER thematische Position — nicht Policy-Details**: Frage entweder nach der groben Ausrichtung einer Partei (Markt vs. Staat, Ausbau vs. Rückbau, dafür vs. dagegen) ODER nach ihrer Position zu einem konkreten Thema, das im Chat besprochen wurde (z. B. "Wie steht X zur Pro-Kopf-Rückzahlung der CO2-Einnahmen?"). Was NICHT erlaubt ist: spezifische Beträge, Prozentsätze, Jahreszahlen, genaue Mechanik-Details ("wie viele Entgeltpunkte pro Kind?", "ab wie vielen Beitragsjahren?").

2. **Ebene: Grundhaltung und thematische Position, nicht Mechanik-Details**: "Befürwortet/lehnt ab", "Ausbau/Rückbau", "Markt/Staat", "Stärkung/Schwächung", aber auch "spricht sich für/gegen Thema Y aus" sind die richtige Ebene. KEINE Fragen nach Zahlen, Jahren, exakten Forderungs-Formulierungen oder Instrument-Details.

3. **Klar formuliert**: Die Frage muss eindeutig und verständlich sein — aber auf der Ebene der Grundhaltung bzw. thematischen Position bleiben.

4. **Trennscharfe Optionen — KRITISCH**: Die vier Optionen müssen klar voneinander unterscheidbar sein und sich auf der Richtungs-/Stärke-Ebene **eindeutig nicht überlappen**. Es darf nie zwei Optionen geben, die ungefähr dasselbe meinen — sonst ist die Frage nicht eindeutig beantwortbar.
   - **VERBOTEN sind nahe Duplikate** wie:
     - "Lehnt grundsätzlich ab" + "Eher dagegen"
     - "Befürwortet deutlichen Ausbau" + "Eher für einen Ausbau"
     - "Komplett dagegen" + "Eher für eine Abschaffung" (beide bedeuten Ablehnung)
     - "Will den bestehenden Stand erhalten" + "Lehnt Veränderungen weitgehend ab"
   - **ERLAUBT sind klar getrennte Stances** auf einer **diskreten** Skala, z. B.:
     - "Befürwortet einen deutlichen Ausbau"
     - "Will den bestehenden Stand erhalten"
     - "Fordert einen klaren Rückbau"
     - "Hat sich ambivalent / nicht klar positioniert"
   - Nutze Abstufungen wie "eher", "leicht", "tendenziell" nur dann, wenn sie die einzige Position dieser Richtung im Optionsset sind. Verwende NICHT zwei Optionen mit unterschiedlich starken Formulierungen derselben Richtung.

5. **Faire Distraktoren**: Die falschen Antworten müssen plausibel sein, aber **eindeutig** falsch. Distraktoren bleiben auf Richtungs-Ebene (andere Parteien, andere Grundhaltungen, andere Stoßrichtungen) — sie dürfen niemals "halb richtig" oder "fast korrekt" sein.

6. **Aus dem Gespräch beantwortbar ohne Detail-Auswendiglernen**: Die korrekte Antwort muss jemandem, der das Gespräch aufmerksam gelesen hat, erkennbar sein — auch ohne sich Zahlen, exakte Instrumente oder genaue Formulierungen gemerkt zu haben. Es darf jedoch erwartet werden, dass die Person sich an die diskutierten Themen und die Position der Parteien dazu erinnert.

7. **Ausgeglichene Abdeckung**: Verteile Fragen gleichmäßig über alle Parteien.

**Parteien — STRIKT:**
Es existieren NUR die drei Parteien [PARTY_BADGE:venus], [PARTY_BADGE:mars] und [PARTY_BADGE:saturn]. Erfinde NIEMALS weitere Parteien. Verwende ausschliesslich die unter "Verfügbare Parteien" gelisteten IDs — keine anderen Namen, auch nicht aus deinem Vorwissen (kein "spd"/"cdu"/"gruene"/"merkur"/"jupiter" o.ä.).

**Parteinamen markieren:**
Jede Erwähnung einer Partei MUSS als Badge-Marker geschrieben werden: `[PARTY_BADGE:<id>]`. Verwende die Kleinbuchstaben-ID der Partei (`venus`, `mars`, `saturn`) — niemals den großgeschriebenen Namen direkt im Text.

Falsch: "Saturn fordert ..."
Richtig: "[PARTY_BADGE:saturn] fordert ..."

Falsch (Option): "Mars"
Richtig (Option): "[PARTY_BADGE:mars]"

---

**Fragetypen — Vielfalt ist wichtig.**

Verwende einen Mix aus den folgenden drei Fragetypen. Verteile die Fragen ungefähr 40 % Typ A, 30 % Typ B, 30 % Typ C — nicht alle Fragen vom selben Typ.

**Reihenfolge pro Frage — STRIKT:**
1. Entscheide ZUERST den Fragetyp und setze `question_type` ("A", "B" oder "C").
2. Formuliere DANN `question` und `options` so, dass beide zum gewählten Typ passen — Frageform und Optionsform müssen zusammen gehören.
3. Setze `party` nur bei Typ B/C (die im Fragetext genannte Partei). Bei Typ A muss `party` null sein, weil die Partei dort die Antwort ist und nicht das Subjekt der Frage.

**Typ A — "Welche Partei …?" (Zuordnung)**
- Frage beschreibt eine Position oder Grundhaltung; gefragt wird, welche Partei sie vertritt.
- WICHTIG: In diesem Fragetyp dürfen KEINE Parteinamen oder `[PARTY_BADGE:...]`-Marker im Fragetext vorkommen — das wäre die Antwort.
- Optionen: die drei Parteien (`[PARTY_BADGE:venus]`, `[PARTY_BADGE:mars]`, `[PARTY_BADGE:saturn]`) plus eine Meta-Option ("Keine der genannten Parteien", "Mehrere der genannten Parteien" oder "Alle drei Parteien").
- Beispiele:
  - "Welche Partei steht dem CO2-Preis grundsätzlich ablehnend gegenüber?"
  - "Welche Partei will das Bürgergeld ausbauen?"
  - "Welche Partei setzt beim Klimaschutz am stärksten auf Marktmechanismen?"

**Typ B — "Wie steht [PARTY_BADGE:X] zu …?" (Grundhaltung)**
- Frage benennt EINE Partei und ein Thema; gefragt wird nach deren Grundhaltung.
- Genau ein `[PARTY_BADGE:...]` im Fragetext (die genannte Partei).
- Optionen sind Richtungs-Stances, KEINE Parteinamen. Genau eine korrekte plus drei plausible Distraktoren. Beispiel-Optionen: "Befürwortet einen deutlichen Ausbau", "Will den bestehenden Stand erhalten", "Lehnt grundsätzlich ab", "Hat sich ambivalent / nicht klar positioniert".
- Beispiele:
  - "Wie steht [PARTY_BADGE:mars] zum Ausbau der erneuerbaren Energien?"
  - "Welche Grundhaltung vertritt [PARTY_BADGE:venus] beim Bürgergeld?"
  - "Wie positioniert sich [PARTY_BADGE:saturn] zur Schuldenbremse?"

**Typ C — "Welche Aussage trifft auf [PARTY_BADGE:X] zu?" (Aussagen-Zuordnung)**
- Frage benennt EINE Partei; gefragt wird, welche von vier kurzen Aussagen zu deren Position passt.
- Genau ein `[PARTY_BADGE:...]` im Fragetext (die genannte Partei).
- Optionen sind kurze Richtungs-Aussagen über politische Positionen, OHNE Parteinamen darin. Eine Aussage trifft auf die genannte Partei zu; die anderen drei sind Positionen, die plausibel klingen, aber NICHT zu dieser Partei passen (oft: Positionen der anderen Parteien, ohne sie zu benennen).
- Beispiele:
  - Frage: "Welche Aussage trifft auf [PARTY_BADGE:venus] beim Thema Klimaschutz zu?"
    Optionen: "Setzt primär auf staatliche Investitionen und Ausbau" / "Setzt primär auf Marktmechanismen und Emissionshandel" / "Lehnt eine aktive Klimapolitik weitgehend ab" / "Fordert vor allem internationale Abkommen statt nationaler Maßnahmen"

---

**Cross-Party-Überlappungen — WICHTIG.**

In dieser Studie gibt es bewusst Themen, bei denen ZWEI Parteien dieselbe Grundrichtung vertreten — nur mit unterschiedlicher Begründung. Diese Überlappungen sind das interessanteste Material für die Wissensprüfung, weil sie testen, ob jemand die *Begründungen* der Parteien wirklich verstanden hat, statt einer reinen Links/Rechts-Heuristik zu folgen.

**Bekannte Überlappungs-Themen:**
{_format_overlap_themes()}

**Ziel-Verteilung:** Etwa 30 % aller Fragen (z. B. ~3 von 10) sollen Überlappungs-Fragen vom **Typ A** sein, bei denen die korrekte Antwort `"Mehrere der genannten Parteien"` ist — vorausgesetzt, die Überlappung wurde im Chat tatsächlich erwähnt. Wenn das Chat eine Überlappung gar nicht abdeckt, erfinde KEINE Überlappungs-Frage darüber.

**Wie eine Überlappungs-Frage formal aussehen muss:**
- `question_type` = `"A"` (es ist eine Zuordnungs-Frage)
- Die vier Optionen sind die drei Parteien plus die Meta-Option `"Mehrere der genannten Parteien"`
- `correct_index` zeigt auf die Meta-Option (typischerweise Index 3)
- `is_overlap_question` = `true`
- `party` = `null` (Typ A hat nie ein `party`-Feld)
- `partial_credit_indices` enthält die Indizes der **einzelnen** Parteien, die zur Überlappung gehören. Wer im Quiz nur eine der beiden korrekten Parteien wählt, bekommt 0.5 Punkte statt 0 — das belohnt teilweises Verständnis.

**Beispiel einer Überlappungs-Frage:**
- Frage: "Welche Partei spricht sich für eine Pro-Kopf-Rückzahlung der CO2-Einnahmen direkt an die Bürger aus?"
- Optionen: `["[PARTY_BADGE:venus]", "[PARTY_BADGE:mars]", "[PARTY_BADGE:saturn]", "Mehrere der genannten Parteien"]`
- `correct_index`: `3`
- `is_overlap_question`: `true`
- `partial_credit_indices`: `[0, 1]` (Venus und Mars vertreten beide diese Position)

**Bei allen anderen Fragen (keine Überlappung):**
- `is_overlap_question` = `false`
- `partial_credit_indices` = `[]` (leer)

**Wichtig:** Eine Überlappungs-Frage darf nicht so formuliert sein, dass nur eine Partei eindeutig passt. Die Frage muss genau die Stoßrichtung treffen, in der sich die zwei Parteien überschneiden — nicht das spezifische Begründungs-Framing einer einzelnen Partei.

---

**Strikt zu vermeiden:**
- Fragen nach spezifischen Zahlen, Prozentangaben, Eurobeträgen oder Jahren
- Fragen nach exakten Mechanik-Details oder genauen Instrument-Ausgestaltungen ("ab wie vielen Beitragsjahren?", "wie viele Entgeltpunkte?")
- Fragen nach spezifischen Formulierungen aus dem Chat
- Triviale oder offensichtliche Fragen
- Doppelte oder sehr ähnliche Fragen
- **Optionen, die sich semantisch überlappen oder dasselbe in unterschiedlicher Stärke ausdrücken** (z. B. "Komplett dagegen" und "Eher für eine Abschaffung", oder "Deutlicher Ausbau" und "Tendenziell für mehr") — Optionen müssen trennscharf sein, sodass genau eine eindeutig richtig ist.
- Fragen, deren Antwort nicht im Chat vorkommt
- Parteinamen ohne `[PARTY_BADGE:<id>]`-Markierung
- Erfundene Parteien: nur [PARTY_BADGE:venus], [PARTY_BADGE:mars], [PARTY_BADGE:saturn] sind erlaubt
- Bei Typ A: jegliche Erwähnung einer konkreten Partei im Fragetext — das verrät die Antwort
- Erfundene Überlappungen: `is_overlap_question=true` nur, wenn die Überlappung tatsächlich zu den vordefinierten Themen gehört UND im Chat erwähnt wurde"""

GENERATION_PROMPT = """Basierend auf der folgenden Chat-Konversation zum Thema "{topic}", erstelle {num_questions} Multiple-Choice-Fragen.

**Verfügbare Parteien:** {parties}

**Chat-Konversation:**
{chat_history}

**Aufgabe:**
Erstelle {num_questions} Fragen, die testen, ob jemand die **grobe Ausrichtung** der im Chat besprochenen Parteien sowie ihre **Position zu einzelnen besprochenen Themen** verstanden hat.

Achte darauf:
1. **Single Choice — genau eine richtige Antwort** unter den vier inhaltlichen Optionen. Optionen müssen **trennscharf** sein: keine zwei Optionen, die ungefähr dasselbe meinen ("Komplett dagegen" und "Eher für Abschaffung" → verboten).
2. Jede Frage bleibt auf der Ebene der Grundhaltung oder der thematischen Position: dafür/dagegen, Ausbau/Rückbau, Markt/Staat, "spricht sich für Thema Y aus" — KEINE spezifischen Zahlen, Eurobeträge, Jahre oder Mechanik-Details.
3. **Variiere die Fragetypen.** Mische Typ A ("Welche Partei …?"), Typ B ("Wie steht [PARTY_BADGE:X] zu …?") und Typ C ("Welche Aussage trifft auf [PARTY_BADGE:X] zu?") — nicht alle Fragen vom selben Typ. Richtwert: ~40 % A, ~30 % B, ~30 % C.
4. **Überlappungs-Quote: ~30 % der Fragen** sollen Typ-A-Überlappungs-Fragen sein, deren korrekte Antwort `"Mehrere der genannten Parteien"` ist (mit `is_overlap_question=true` und `partial_credit_indices` für die einzelnen beteiligten Parteien). Nur erstellen, wenn die Überlappung tatsächlich im Chat erwähnt wurde.
5. **Bei Typ A**: KEINE Parteinamen oder Badge-Marker im Fragetext — die Optionen enthalten die drei Parteien + eine Meta-Option (typischerweise "Mehrere der genannten Parteien" für Überlappungs-Fragen, sonst "Keine der genannten Parteien" oder "Alle drei Parteien").
6. **Bei Typ B/C**: Genau eine Partei im Fragetext (mit `[PARTY_BADGE:<id>]`). Die Antwortoptionen sind Stances bzw. kurze Aussagen OHNE Parteinamen.
7. Verwende AUSSCHLIESSLICH die unter "Verfügbare Parteien" gelisteten Parteien — erfinde keine weiteren Parteinamen.
8. Verteile die Fragen gleichmäßig auf die besprochenen Parteien.
9. Erstelle genau 4 Antwortoptionen pro Frage (eine korrekt, drei falsch aber plausibel und eindeutig falsch).
10. Setze `question_type` ("A"/"B"/"C"), `is_overlap_question` und `partial_credit_indices` korrekt.
11. Gib die Source-Excerpt an, also den Teil des Chats auf dem die Frage basiert.

Denke daran: Teilnehmende, die das Quiz besonders gut lösen, gewinnen einen 20 € Amazon-Gutschein — die Fragen müssen daher fair, trennscharf und eindeutig beantwortbar sein.

Erstelle die Fragen im vorgegebenen JSON-Format."""


def format_chat_history(messages: list) -> str:
    """Format chat messages for the prompt."""
    if not messages:
        return "Keine Nachrichten."

    formatted_parts = []
    for msg in messages:
        role_label = "Benutzer" if msg.role == "user" else "Assistent"
        # Truncate very long messages
        content = msg.content
        if len(content) > 2000:
            content = content[:2000] + "..."
        formatted_parts.append(f"**{role_label}:** {content}")

    return "\n\n".join(formatted_parts)


def format_parties(parties: list[str]) -> str:
    """Format party list for the prompt."""
    return ", ".join(parties)
