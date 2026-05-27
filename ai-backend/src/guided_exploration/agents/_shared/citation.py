# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Shared citation directive for all answer-streaming agents.

Reused verbatim by every agent that emits cited answer text
(``BaselineAgent``, ``QuickSummaryAgent``, ``LeafConversationHandlerAgent``,
``LeafContentGeneratorAgent``). Sammel-citations on framing/summary
sentences inflate the study's ``encountered_positions`` metric and read
as over-the-top — only sentences that state a concrete claim from a
source get IDs.
"""


CITATION_DIRECTIVE = """    - Zitierstil — KRITISCH, BEFOLGE DIESE REGEL STRIKT:
        - **Standard ist KEINE Quelle.** Setze IDs **nur**, wenn der Satz eine **konkrete, namentlich einer Partei zugeordnete Aussage** wiedergibt (Forderung, Zahl, Plan, konkrete Position). Keine Partei genannt oder keine konkrete Forderung → **keine ID**.
        - **Vage Paraphrasen sind keine konkrete Aussage — auch nicht mit Partei-Badge davor.** „Engere Bedingungen", „strenger", „mehr Pflichten", „mehr Hilfe", „setzt auf X", „will mehr/weniger" usw. fassen das Programm nur zusammen — sie sind Framing, kein Zitat. Eine ID darf nur an einem Satz hängen, der die **konkrete, falsifizierbare Substanz** der Position wiedergibt: Zahlen, Jahreszahlen, Mechanismen, namentliche Adressatenkreise, harte Bedingungen. Wenn die Substanz dir zu lang wird, **lass die ID weg** — eine vage Paraphrase ohne ID ist besser als eine vage Paraphrase mit ID (mit ID wird sie zur Scheinbeleg-Aussage).
        - **IDs kleben an ihrer Aussage — nie am Absatzende.** Pro Aussage höchstens **1–2 IDs**. Drei legitime Formate (Vorzugsreihenfolge):
            1. **Inline:** ID mitten im Satz, unmittelbar hinter ihrer Forderung. Beispiel: `[PARTY_BADGE:venus] will mehr ÖPNV [venus-klima-006], ein Klimaticket [venus-klima-007] und ein Verbrenner-Aus ab 2030 [venus-klima-005].` — bevorzugt für Fließtext mit mehreren Forderungen.
            2. **Ein Satz = eine ID:** Jede Forderung wird ein eigener kurzer Satz, ID direkt am Satzende.
            3. **Listenpunkt = eine ID:** Bei drei oder mehr Forderungen lieber Aufzählung; jeder Punkt trägt seine eigene ID am Ende.
            **Niemals** ein Quellen-Pile (`[id1] [id2] [id3]`) am Ende eines Sammelsatzes.
        - **Komma-Listen mit Sammel- oder End-ID sind verboten — schon ab 2 Forderungen.** Sätze wie „<Partei> fordert A, B und C [id]" oder „A und B [id1, id2]" am Satzende sind nicht erlaubt. Zwei legitime Auflösungen: (a) jede Forderung trägt **ihre eigene ID inline** unmittelbar hinter sich (siehe Inline-Format oben — `A [id1], B [id2] und C [id3]` ist erlaubt), oder (b) du brichst die Liste auf in einzelne Sätze bzw. Listenpunkte mit jeweils eigener ID. Das gilt auch in „Außerdem will die Partei…"- oder „Was das praktisch heißt…"-Passagen.
        - **Niemals Sammel-Zitationen.** Hänge **nie** mehrere IDs (z.B. `[2, 4, 6, 9]` oder `[venus-001, venus-002, venus-003]`) an einen Satz, nur weil sie alle zum Thema passen.
        - **Keine IDs an Framing-/Meta-Sätzen.** Einleitungs-, Einordnungs-, Themen­beschreibungs-, Aspekt-Listen- oder Zusammenfassungs-Sätze bekommen **null** IDs — auch wenn die Quellen vorhanden sind.
        - **Grundhaltungs-/Leitlinien-Sätze sind Framing — keine IDs.** Sätze wie „Bei <Partei> steht <Idee> im Vordergrund" oder „<Partei> setzt auf <Prinzip>" sind interpretative Einordnung, kein Zitat — sie fassen ein Bündel von Forderungen abstrakt zusammen. Die Belege wandern an die darauffolgenden Sätze, die die einzelnen Forderungen ausbuchstabieren.
        - Format: nach dem belegten Satz die ID(s) in eckigen Klammern: `[12]`, `[12, 15]`, oder `[venus-sozial-004]` — **zeichengenau aus den Ausschnitten kopieren, niemals mit Partei-Präfix** (z.B. `[venus:venus-sozial-004]` ist FALSCH; `[venus-sozial-004]` ist korrekt).
        - Eigenwissen → _kursiv_, **keine ID**.

        ❌ **VERBOTEN — Quellen-Pile am Absatzende (häufigster Fehler):**
        ```
        [PARTY_BADGE:venus] will massiv in den ÖPNV investieren. Außerdem wolle
        sie klimaschädliche Subventionen abbauen. Den CO2-Preis will sie deutlich
        erhöhen und ein Klimageld einführen. [venus-klima-006, venus-klima-003, venus-klima-001, venus-klima-002]
        ```

        ✅ **RICHTIG — pro Satz die ID, die genau diesen Satz belegt:**
        ```
        [PARTY_BADGE:venus] will massiv in den ÖPNV investieren. [venus-klima-006]
        Außerdem will sie klimaschädliche Subventionen abbauen. [venus-klima-003]
        Den CO2-Preis will sie deutlich erhöhen [venus-klima-001] und ein Klimageld
        einführen. [venus-klima-002]
        ```

        ❌ **VERBOTEN — Grundhaltung mit Quellen:**
        ```
        Bei [PARTY_BADGE:mars] steht stärker die Idee im Vordergrund, die Rente
        über mehrere Säulen abzusichern. [mars-sozial-001] [mars-sozial-002]
        ```

        ✅ **RICHTIG — Grundhaltung ohne IDs, konkrete Forderungen mit IDs:**
        ```
        Bei [PARTY_BADGE:mars] steht stärker die Idee im Vordergrund, die Rente
        über mehrere Säulen abzusichern.

        - Die Beitragsbemessungsgrenze soll bei 9.300 € liegen. [mars-sozial-001]
        - Eine Aktienrente soll als zusätzliche Säule eingeführt werden. [mars-sozial-002]
        ```

        ❌ **VERBOTEN — Paraphrase als Cite-Anker (vage Substanz):**
        ```
        [PARTY_BADGE:saturn] will das Bürgergeld nur unter engeren
        Bedingungen gewähren [saturn-sozial-005].
        ```
        Was sind die „engeren Bedingungen"? Der Satz sagt es nicht — die ID
        belegt nichts Konkretes. Falscher Cite-Anker.

        ✅ **RICHTIG — konkrete Substanz als Cite-Anker:**
        ```
        [PARTY_BADGE:saturn] will das Bürgergeld nur deutschen Staatsbürgern
        und Zuwanderern nach mindestens fünf Jahren Beitragszahlung gewähren
        [saturn-sozial-005].
        ```"""
