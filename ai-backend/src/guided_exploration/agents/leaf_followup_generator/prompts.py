# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt templates for the leaf follow-up generator.

Keeps the in-leaf scope rule, examples, closure spec, and topic-switch
spec verbatim from the previous suggested-questions prompt — the
language was correct; the bug was the input set, which the new agent
fixes by passing the full leaf conversation and full available
knowledge.
"""

from pydantic import BaseModel, Field

from src.guided_exploration.agents._shared import EXPLORATION_GOALS


class TopicSwitchProposalLLM(BaseModel):
    """LLM output schema for an optional topic-switch proposal.

    Set only when the user's last question fits one of the listed
    Nachbar-Unterthemen clearly better than the current leaf. The
    `target_node_id` MUST be one of the IDs from the
    "Andere Unterthemen dieses Baums" list — never invented, never the
    current leaf. The leaf handler validates the ID and drops the
    proposal silently if it doesn't match a real sibling.
    """

    target_node_id: str = Field(
        ...,
        description=(
            "ID des Nachbar-Unterthemas, das besser zur letzten Frage "
            "passt — exakt aus der Liste 'Andere Unterthemen dieses "
            "Baums' kopiert (zwischen den Backticks). Niemals die "
            "aktuelle Leaf-ID, niemals erfunden."
        ),
    )
    target_node_name: str = Field(
        ...,
        description=(
            "Anzeigename des Nachbar-Unterthemas — exakt der **fett** "
            "geschriebene Name aus der Liste."
        ),
    )
    reason: str = Field(
        ...,
        description=(
            "Ein kurzer deutscher Satz (max ~15 Worte), der erklärt, "
            "warum das Nachbar-Unterthema besser passt. Wird in der "
            "Switch-UI angezeigt. Du-Form, neutral. Keine Floskeln "
            "wie 'willst du wechseln?'."
        ),
    )


class LeafFollowUpLLMOutput(BaseModel):
    """LLM output schema for the leaf follow-up generator."""

    questions: list[str] = Field(
        ...,
        description=(
            "0-3 kurze Folgefragen zur Vertiefung des Themas. "
            "Lieber leere Liste als schwache, generische oder themenfremde "
            "Vorschläge. Jede Frage maximal 7 Worte."
        ),
    )
    closure_ready: bool = Field(
        default=False,
        description=(
            "True, wenn die zentralen Positionen des Leafs, ihr Verhältnis "
            "zueinander und die Stance jeder Partei besprochen wurden und "
            "die verfügbaren Quellen substanziell nichts Neues mehr "
            "hergeben. Dann zeigt das Frontend dem Nutzer einen "
            "Abschluss-Hinweis mit Buttons. Bei false läuft die "
            "Erkundung weiter — der Default."
        ),
    )
    topic_switch_proposal: TopicSwitchProposalLLM | None = Field(
        default=None,
        description=(
            "Optional: Wenn die letzte Nutzerfrage eindeutig besser zu "
            "einem der gelisteten Nachbar-Unterthemen passt, setze "
            "diesen Block. Sonst null. Niemals auf das aktuelle Leaf "
            "verweisen, niemals eine ID erfinden."
        ),
    )


_SCOPE_RULE_IN_LEAF = """4. **Im Geltungsbereich dieses Unterthemas bleiben — die Erkundung in einer klaren Reihenfolge weiterdrehen.** Du begleitest die Nutzerin durch genau dieses Unterthema. Das übergreifende Ziel: Sie soll am Ende verstehen, **welche Aspekte dieses Themas die Parteien diskutieren**, **wie ihre Positionen zueinander stehen**, und **warum jede Partei will, was sie will**. Folge dabei dieser Progression — gehe erst zur nächsten Stufe, wenn die vorherige im Gespräch substantiell besprochen ist:

   1. **Subtopic erschließen — was sind die Aspekte?** Solange noch
      ungenutzte Aspekte des Leafs in der Wissensbasis stehen, frag
      nach einem davon (z.B. innerhalb eines Bürgergeld-Leafs: nach
      Regelsatzhöhe → Sanktionen / Hinzuverdienst / Zugang). Die
      Folgefrage öffnet einen neuen Teilaspekt des **gleichen** Leafs.
   2. **Positionen vergleichen — wer steht wofür?** Sobald die
      zentralen Aspekte benannt sind, hol andere Parteien zum gleichen
      Aspekt dazu, mach Gegensätze und Lücken sichtbar
      ("Was sagt [Y] dazu?", "Wo unterscheiden sich X und Y?",
      "Warum sagt [Z] dazu nichts?").
   3. **Spezifika klären — was bedeutet das konkret?** Erst wenn die
      Positionen kontrastiert sind, Detail-/Begriffs-/Wirkungsfragen
      zur **bereits genannten** Forderung ("Was heißt ‚Aufschlag'
      praktisch?", "Wie wirkt sich das auf …?", "Warum knüpft [X] das
      an Beitragsjahre?"). Keine Wiederholung der Antwort — Einordnung
      einer Aussage, die schon im Verlauf steht.

   Die Stufen sind eine **Voreinstellung**, keine starre Liste: wenn
   eine starke Forderung unwidersprochen im Raum steht, ist ein
   Vergleich (Stufe 2) sofort sinnvoller als ein weiterer neuer Aspekt
   (Stufe 1); wenn ein Begriff offensichtlich offen bleibt, ist
   Stufe 3 zulässig, bevor alle Aspekte abgedeckt sind. Aber **der
   Default ist von oben nach unten**: lieber erst Aspekte öffnen, dann
   vergleichen, dann ins Detail. Es soll nicht wirken, als würden
   krampfhaft alle Quellen abgearbeitet.

   **Off-scope: die Nachbar-Unterthemen dieses Baums.** Folgende
   Unterthemen gehören zum gleichen Themenbaum, sind aber **eigene
   Leafs** mit eigenen Positionen — sie sind für deine Folgefragen
   tabu:

   {neighboring_leaves}

   Tabu bleibt damit jedes Verlassen dieses Unterthemas — sowohl in die
   oben gelisteten Nachbar-Unterthemen als auch in andere Politikfelder
   außerhalb des Baums. Auch wenn die letzte Antwort Brücken nahelegt
   (z.B. CO2-Preis → Verkehr, Bürgergeld → Rente): solche Sprünge
   gehören NICHT in die Folgefragen, sondern in die Leaf-Navigation.
   Eine Frage, deren natürliche Antwort aus einem der oben gelisteten
   Nachbar-Unterthemen käme, ist keine gültige Folgefrage."""

_GOOD_EXAMPLES_IN_LEAF = """- "Warum gibt Venus den Preis zurück?" (vertieft)
- "Wie soll die Auszahlung praktisch funktionieren?" (vertieft)
- "Was sagt Mars zur selben Frage?" (andere Partei im selben Aspekt)
- "Widerspricht Saturns Aufschlag nicht Mars' Linie?" (Interplay)
- "Warum sagen Venus und Mars dazu nichts?" (Interplay — Lücken)
- "Was passiert an der EU-Außengrenze?" (benachbarter Aspekt im selben Leaf — CBAM)"""

_BAD_EXAMPLES_IN_LEAF = """- "Wie hoch ist der CO2-Preis bei Venus?"  ← Antwort steht schon oben
- "Was sagt Venus zur Wirtschaft?"  ← Themenabschweifung (anderes Feld)
- "Wie hängt das mit der Rente zusammen?"  ← anderes Subtopic, nicht in dieses Leaf ziehen
- "Welche Parteien gibt es?"  ← Generisch, nicht im Kontext verankert"""


LEAF_FOLLOWUP_PROMPT = (
    """Generiere 0-2 kurze Folgefragen, die der Nutzer als nächste Frage in diesem Gespräch tatsächlich stellen würde.

"""
    + EXPLORATION_GOALS
    + """

## Bisheriges Gespräch (vollständig)
{conversation}

## Verfügbare Parteipositionen (Wissensbasis dieses Leafs)
{available_context}

## Bereits zitierte Quellen-IDs (in Initial-Content + früheren Antworten)
{already_cited_ids}

## Deine Aufgabe
**Dein Zweck: Verständnis aufbauen, nicht Gespräch verlängern.** Die
Folgefragen sind dein Werkzeug, um die drei Ziele oben für genau dieses
Unterthema voranzutreiben: **Erkunden** (welche Aspekte die Parteien
diskutieren), **Vergleichen** (wie ihre Positionen zueinander stehen)
und **Verstehen** (warum jede Partei will, was sie will). Sie sind
**kein** Mittel, das Gespräch um seiner selbst willen am Leben zu
halten, **kein** Pflichtschritt, **kein** Engagement-Trick. Wenn keine
Frage echtes Verständnis weiter aufbaut: **leere Liste** ausgeben.
Lieber kein Vorschlag als einer, der nur klingt, als würde er
weiterführen.

Zwei No-Gos, die genau das verletzen:
- **Rehash-Fragen** — Fragen, deren Antwort schon irgendwo im Verlauf
  steht (Initial-Content, frühere Antwort, schon gezogene Karte). Sie
  fühlen sich wie Folgefragen an, bringen aber kein neues Verständnis.
- **Scheinintegrierende Fragen** — Fragen, die so klingen, als würden
  sie zwei Aussagen zusammenführen, einen Widerspruch aufdecken oder
  eine Brücke schlagen, obwohl in der Wissensbasis tatsächlich keine
  solche Brücke existiert (z.B. *„Widerspricht X' Forderung Y'
  Vorschlag?"*, wenn Y zum gefragten Aspekt gar nichts sagt). Solche
  Fragen erzeugen die Illusion von Tiefe, ohne dass die Quellen sie
  tragen — der Bot müsste dann improvisieren oder ausweichen, und die
  Nutzerin lernt nichts dazu.

Schlage höchstens 2 Folgefragen vor, die:

1. **An die letzte Antwort oder die abgedeckten Parteipositionen
   anknüpfen.** Eine Frage greift entweder eine konkrete Aussage aus
   der Antwort auf — Forderung, Zahl, Mechanismus — oder einen
   benachbarten Aspekt aus der Wissensbasis, der noch nicht behandelt
   wurde. Generische Fragen wie "Welche Position vertritt Partei X?"
   sind verboten, wenn diese Position oben bereits steht.
2. **Aus den verfügbaren Parteipositionen beantwortbar sind, mit
   substantiell neuem Material.** Eine Folgefrage muss durch mindestens
   eine Quelle in der Wissensbasis gedeckt sein, deren ID **nicht** in
   der Liste der bereits zitierten IDs steht. Wenn die einzige denkbare
   Antwort auf eine vorgeschlagene Frage nur aus bereits zitierten IDs
   käme, würde sie nur das wiederholen, was die Nutzerin schon gesehen
   hat — solche Fragen nicht vorschlagen. Lieber leere Liste.
3. **NICHT eine Aussage wiederholen, die in der Antwort schon steht.**
   Eine Frage, deren Antwort der Nutzer gerade gelesen hat, ist keine
   Folgefrage.
"""
    + _SCOPE_RULE_IN_LEAF
    + """
5. **Im Du-Stil, kurz und natürlich formuliert** (max 7 Worte). Klingt
   wie eine echte Rückfrage im Chat, nicht wie ein FAQ-Eintrag.

## Beispiele

✅ Gute Folgefragen (Beispielkontext: Antwort hat genannt, dass Venus
einen CO2-Preis von 80 €/t fordert und ihn pro Kopf zurückgeben will):
"""
    + _GOOD_EXAMPLES_IN_LEAF
    + """

❌ Schlechte Folgefragen für denselben Kontext:
"""
    + _BAD_EXAMPLES_IN_LEAF
    + """

## Validitäts-Check vor der Ausgabe — STRIKT
Bevor du eine Folgefrage in `questions` aufnimmst, prüfe sie der Reihe
nach gegen alle vier Bedingungen. Wenn auch nur **eine** nicht erfüllt
ist, lass die Frage weg.

1. **Leaf-Scope:** Die Frage liegt eindeutig im aktuellen Unterthema —
   nicht in einem der oben gelisteten Nachbar-Unterthemen, nicht in
   einem anderen Politikfeld.
2. **Aus der Wissensbasis beantwortbar:** Es gibt mindestens eine
   konkrete Quelle in „Verfügbare Parteipositionen", die diese Frage
   substantiell beantworten kann.
3. **Nicht-Rehash:** Diese Quelle ist entweder neu (ihre ID steht
   nicht in den „Bereits zitierten Quellen-IDs") oder enthält einen
   Aspekt, der im Verlauf noch nicht ausgesprochen wurde.
4. **Progression respektiert:** Die Frage passt zur aktuellen Stufe
   der Konversation (siehe Punkt 4 oben — Aspekte → Vergleich →
   Spezifika), wechselt nicht ohne Grund zurück und überspringt keine
   Stufe ohne klaren Anlass.
5. **Nicht schon beantwortet:** Die Frage zielt nicht auf eine Partei
   oder einen Aspekt, den **irgendeine vorherige Assistent-Nachricht**
   (Initial-Content, frühere Folgefrage-Antwort oder Analyse) bereits
   konkret und attribuiert dargestellt hat. Der Initial-Content-Block
   am Anfang des Verlaufs (`[Initial-Content zum Leaf]`) enthält in der
   Regel schon einen Überblick und je Partei einen Positions-Absatz —
   alles, was dort steht, gilt als „schon gesagt". ❌ „Was sagt Mars
   dazu?" verbieten, wenn Mars im Initial-Content oder in einer
   früheren Antwort bereits einen eigenen Block oder Absatz mit
   konkreten Forderungen hatte. ❌ Auch keine Frage, deren Antwort eine
   frühere Bot-Nachricht explizit als „im Material nicht vorhanden"
   markiert hat. Self-Check: Steht die Antwort wortwörtlich oder
   offensichtlich schon irgendwo im bisherigen Gespräch? Wenn ja,
   verwirf sie.
6. **Keine Schein-Integration:** Wenn die Frage ein Zusammenführen,
   einen Widerspruch oder eine Brücke zwischen mehreren Aussagen
   suggeriert (*„Widerspricht X' … nicht Y' …?"*, *„Wie passt X zu
   Y?"*, *„Stimmen X und Y darin überein?"*), müssen **beide** Seiten
   der Brücke in den verfügbaren Quellen zum **konkret gefragten
   Aspekt** tatsächlich Position beziehen. Hat eine der beiden Parteien
   zu diesem Aspekt nichts gesagt, ist die Frage Theater, kein
   Vergleich — der Bot müsste die Lücke mit allgemeinen Aussagen
   füllen, und die Nutzerin lernt nichts Neues. Verwirf sie.

Wenn nach diesem Check keine Frage übrig bleibt: **leere Liste
ausgeben** und stattdessen das `closure_ready`-Signal prüfen. Lieber
keine Folgefrage als eine schwache, generische oder themenfremde —
und auf jeden Fall lieber keine Folgefrage als zwei, von denen eine
schwach ist.

## Closure-Signal — `closure_ready`
Setze `closure_ready=true`, sobald **einer** dieser Indikatoren
zutrifft:
- Die letzte Antwort hat einen Aspekt offen abgelehnt, weil er in den
  vorliegenden Quellen nicht abgedeckt war
  („Dazu finden sich in den vorliegenden Programmen keine
  Positionen…").
- Die letzte Nutzerfrage zeigte in eines der gelisteten
  Nachbar-Unterthemen — die Konversation ist am Rand des Leafs
  angekommen.
- Die letzte Antwort wäre Rehash gewesen, weil zum gefragten Aspekt
  keine neuen, noch nicht zitierten Quellen-IDs verfügbar sind.
- Mechanik, Größenordnung und Begründungen der Hauptpositionen wurden
  im Verlauf bereits zitiert; weitere Quellen würden nur Variationen
  liefern.
- Die zentralen Positionen, Hauptunterschiede und Begründungen der
  Parteien sind im Verlauf benannt — der Verständnis-Aufbau zu diesem
  Unterthema ist im Wesentlichen abgeschlossen.

Lieber an einer natürlichen Stelle abschließen als die Nutzerin mit
Pseudo-Folgefragen im Leaf halten, die nur Bekanntes wiederkäuen.

**Closure-Einladungen sind unverbindlich.** Im Frontend sieht die
Nutzerin neben dem Abschluss-Button immer einen „Weiter erkunden"-
Button und kann jederzeit weitermachen. Du hältst sie also nicht auf,
wenn du Closure setzt — der Button ist eine Einladung, kein Hammer.

**Wiederholungs-Sperre — sehr wichtig.** Wenn ein früherer Assistent-
Turn im Verlauf bereits den Marker
`[closure-Einladung wurde gezeigt]` trägt und die Nutzerin **danach
weiter Fragen gestellt hat**, hat sie die Closure-Einladung gesehen
und entschieden, weiterzumachen. Dann gilt:

- **Setze `closure_ready=false`**, es sei denn, seit der letzten
  Closure-Einladung ist im Verlauf substantiell Neues passiert
  (neue Aspekte besprochen, neue Quellen-IDs zitiert, neue
  Parteivergleiche gezogen) UND auch jetzt wieder einer der
  Closure-Indikatoren oben greift.
- Eine zweite Closure-Einladung im selben Leaf muss durch klaren
  Fortschritt **seit der ersten** gerechtfertigt sein. Sonst nervt
  sie nur.

Bei `closure_ready=true` gilt zusätzlich: **`questions` muss eine leere
Liste sein.** `closure_ready=true` plus Folgefragen ist widersprüchlich.

Das Closure-Signal triggert im Frontend ein eigenes UI-Element mit
Buttons; **gib in den Folgefragen niemals selbst Sätze wie „Thema
abschließen?" oder „Zur Übersicht zurück?" aus** — das ist Aufgabe des
UI, nicht eine Folgefrage.

## Topic-Switch-Signal — `topic_switch_proposal`
Wenn die letzte Nutzerfrage eindeutig besser zu einem der oben
gelisteten Nachbar-Unterthemen passt als zum aktuellen Leaf, fülle
`topic_switch_proposal` mit:
- `target_node_id`: die ID aus der Liste, exakt zwischen den Backticks
  kopiert. **Niemals erfinden, niemals die aktuelle Leaf-ID, niemals
  ein Thema, das nicht in der Liste steht.**
- `target_node_name`: der **fett** geschriebene Name aus der Liste.
- `reason`: ein kurzer deutscher Satz, warum das andere Unterthema
  besser passt (z.B. *„Frage zum Verkehrssektor — dafür gibt's das
  eigene Unterthema Verkehr."*).

**Eher eilig als zögerlich** — sobald der Schwerpunkt der Frage
hörbar zu einem Nachbar-Unterthema kippt, schlage den Wechsel vor;
auch wenn du die Frage gerade noch teilweise im aktuellen Leaf
beantwortet hast. Der Wechsel-Vorschlag ergänzt deine Antwort, er
ersetzt sie nicht. Wenn die Frage im aktuellen Leaf gut aufgehoben
ist, lass das Feld auf null. Nie zwei Nachbarn gleichzeitig
vorschlagen — wähle den klar passendsten.

**Wiederholungs-Sperre.** Wenn der Verlauf bereits einen Marker
`[topic-switch zu „<X>" wurde angeboten]` enthält und die Nutzerin
trotzdem im aktuellen Leaf weitergefragt hat, hat sie das Angebot
implizit abgelehnt. Schlage **denselben** Nachbarn dann nicht erneut
vor — nur wenn die jetzige Frage einen anderen Nachbarn klar besser
trifft, oder wenn die jetzige Frage so eindeutig im alten Nachbarn
liegt, dass ein erneutes Angebot wirklich angebracht ist (z.B. die
Nutzerin schreibt jetzt explizit „lass uns doch zu X wechseln").

`topic_switch_proposal` und `closure_ready` schließen sich nicht aus:
beide dürfen gleichzeitig gesetzt sein, wenn die Konversation am Rand
des Leafs angekommen ist UND ein Nachbar besser passt.
"""
)
