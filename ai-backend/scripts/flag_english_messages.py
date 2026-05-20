#!/usr/bin/env python3
"""Flag study sessions where the participant wrote English to the model.

The study runs in German. Some participants type English messages — most
notably ones who explicitly ask the assistant to answer in English, which
derails the whole conversation. This scan tags every session that contains
at least one *typed* English user message (or an explicit "answer in
English" request) with the ``english`` exclusion reason, so the admin
dashboard can filter them out.

Only genuinely typed text counts. Clicks on the German suggested-follow-up
chips are ignored — a participant who clicked German chips *and* typed
English is still flagged (the German chips don't redeem them). Ultra-short
or ambiguous fragments are skipped unless they match an explicit
English-request phrase.

Language is detected with lingua, restricted to English vs German (far more
robust on short chat text than open-set detection). A message counts as
English when English confidence clears ``EN_THRESHOLD`` and beats German.

Run is idempotent and merges into the same JSON the other exclusion scripts
use; manual tags and other auto-tags are preserved. Defaults to a dry run
that prints every flagged session and its English messages for review —
pass ``--apply`` to actually write.

Usage:
    cd ai-backend
    uv run python scripts/flag_english_messages.py \
        --study 0be379bb-fc01-40dd-b21c-795199053dc2          # dry run
    uv run python scripts/flag_english_messages.py \
        --study 0be379bb-fc01-40dd-b21c-795199053dc2 --apply  # write
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.firebase_service import db  # noqa: E402, F401
from firebase_admin import firestore_async  # noqa: E402
from lingua import Language, LanguageDetectorBuilder  # noqa: E402

STUDY_SESSIONS = "exploration_study_sessions"
GUIDED_SESSIONS = "guided_exploration_sessions"
EXPLORATIONS = "explorations"
CONVERSATIONS = "conversations"

EXCLUSIONS_PATH = (
    project_root.parent / "study-admin" / "data" / "session_exclusions.json"
)
REASON = "english"

# A message is English when English confidence clears this and beats German.
# Tuned conservatively: clear English questions score ~0.9+, while a German
# message with the odd English word stays German. Lower it to catch more.
EN_THRESHOLD = 0.70
# Confidence-based hits must have at least this many substantive word tokens.
# Single tokens (party names like "Saturn", one-word commands like "summary",
# greetings like "hello"/"hallo") are too ambiguous for the EN-vs-DE detector
# to call reliably and produce false positives. Explicit English requests
# bypass this. Two-token phrases ("compare them") still count.
MIN_WORD_TOKENS = 2
# An English message this long (substantive word tokens) is a real sentence,
# enough to flag a session on its own even if everything else was German.
SUBSTANTIAL_EN_TOKENS = 5
# Language-neutral proper nouns (the three fake parties). They carry no
# language signal, so they don't count toward the token requirement.
PROPER_NOUNS = {"venus", "mars", "saturn"}

# Explicit "please answer in English" requests, in both English and German
# phrasing. A match flags the session regardless of the confidence score.
ENGLISH_REQUEST_PATTERNS = [
    r"\bin\s+english\b",
    r"\benglish\s+please\b",
    r"\b(answer|respond|reply|write|speak|talk)\b[^.?!]*\benglish\b",
    r"\bauf\s+engl(isch|ische)\b",
    r"\b(antworte?|antworten|schreib(e|en)?|sprich)\b[^.?!]*\bengl(isch|ische)\b",
    r"\bin\s+englischer\s+sprache\b",
    r"\bswitch\s+to\s+english\b",
    r"\bcan\s+you\s+(speak|write|answer)\s+(in\s+)?english\b",
]
_REQUEST_RE = re.compile("|".join(ENGLISH_REQUEST_PATTERNS), re.IGNORECASE)

_detector = (
    LanguageDetectorBuilder.from_languages(
        Language.ENGLISH, Language.GERMAN
    ).build()
)


def _is_english_request(text: str) -> bool:
    return bool(_REQUEST_RE.search(text))


def _confidences(text: str) -> tuple[float, float]:
    """(english, german) confidence in [0, 1] for an EN-vs-DE classification."""
    values = _detector.compute_language_confidence_values(text)
    en = de = 0.0
    for v in values:
        if v.language == Language.ENGLISH:
            en = v.value
        elif v.language == Language.GERMAN:
            de = v.value
    return en, de


def is_substantive_german(text: str) -> bool:
    """True if ``text`` reads as a genuinely-composed German message.

    Used to tell "wrote real German" apart from "only clicked chips / typed
    the topic seed": needs enough word tokens and German to clearly beat
    English.
    """
    stripped = (text or "").strip()
    if _substantive_token_count(stripped) < MIN_WORD_TOKENS:
        return False
    en, de = _confidences(stripped)
    return de >= EN_THRESHOLD and de > en


def _substantive_token_count(text: str) -> int:
    """Word tokens that carry a language signal (party names excluded)."""
    tokens = re.findall(r"[A-Za-zÄÖÜäöüß]+", text)
    return sum(1 for t in tokens if t.lower() not in PROPER_NOUNS)


def classify(text: str) -> dict | None:
    """Return a hit dict if ``text`` is English / an English request, else None.

    Hit dict: ``{"text", "confidence", "request"}``. Explicit English
    requests always hit. Otherwise the message must read as English *and*
    carry at least ``MIN_WORD_TOKENS`` substantive words, so single proper
    nouns and one-word commands don't trip a false positive.
    """
    stripped = (text or "").strip()
    if not stripped:
        return None
    tokens = _substantive_token_count(stripped)
    if _is_english_request(stripped):
        return {"text": stripped, "confidence": 1.0, "request": True, "tokens": tokens}
    if tokens < MIN_WORD_TOKENS:
        return None
    en, de = _confidences(stripped)
    if en >= EN_THRESHOLD and en >= de:
        return {"text": stripped, "confidence": en, "request": False, "tokens": tokens}
    return None


def _typed_user_texts(messages: list[dict], role_key: str) -> list[str]:
    """Typed (non-chip) user message texts from one message stream.

    ``role_key`` is ``"type"`` for top-level SessionMessages and ``"role"``
    for leaf Conversation messages. Chip clicks are dropped by matching the
    user content against the preceding assistant turn's
    ``suggested_followups`` (same approach as populate_session_exclusions).
    """
    out: list[str] = []
    prev_chips: list[str] = []
    for m in messages:
        if m.get(role_key) == "user":
            content = m.get("content")
            if not isinstance(content, str):
                continue
            if any(content.strip() == c.strip() for c in prev_chips):
                continue  # chip click, not typed
            out.append(content)
        else:
            prev_chips = m.get("suggested_followups") or []
    return out


async def _collect_user_texts(
    fs, chat_id: str | None
) -> tuple[list[str], list[str]]:
    """Typed user texts for a session, as (top_level, leaf).

    Top-level and leaf are returned separately so the caller can treat the
    first top-level message as the topic seed (not genuine German prose).
    """
    if not chat_id:
        return [], []
    g = (await fs.collection(GUIDED_SESSIONS).document(chat_id).get()).to_dict()
    if g is None:
        return [], []

    top = _typed_user_texts(g.get("messages") or [], "type")

    leaf: list[str] = []
    expl = (
        fs.collection(GUIDED_SESSIONS).document(chat_id).collection(EXPLORATIONS)
    )
    async for ed in expl.stream():
        async for cd in ed.reference.collection(CONVERSATIONS).stream():
            msgs = (cd.to_dict() or {}).get("messages") or []
            leaf.extend(_typed_user_texts(msgs, "role"))
    return top, leaf


def _truncate(text: str, n: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


async def scan(study_id: str) -> dict[str, dict]:
    """Return {session_id: {reasons, note, _hits}} for English sessions."""
    fs = firestore_async.client()
    q = fs.collection(STUDY_SESSIONS).where("study_id", "==", study_id)

    flagged: dict[str, dict] = {}
    scanned = 0
    async for d in q.stream():
        scanned += 1
        s = d.to_dict() or {}
        chat_id = (s.get("condition") or {}).get("chat_id")
        top, leaf = await _collect_user_texts(fs, chat_id)
        texts = top + leaf

        hits = [h for h in (classify(t) for t in texts) if h]
        if not hits:
            continue

        # "Genuine German" = substantive German prose the participant
        # actually composed, ignoring the first top-level message (the topic
        # seed) and any chip clicks (already filtered out of ``texts``).
        seed = top[0] if top else None
        german_original = sum(
            1
            for t in texts
            if t is not seed
            and not classify(t)
            and is_substantive_german(t)
        )

        requested = any(h["request"] for h in hits)
        substantial = any(h["tokens"] >= SUBSTANTIAL_EN_TOKENS for h in hits)
        # Flag unless this is a lone short English phrase dropped into an
        # otherwise genuinely-German conversation.
        if not (
            requested
            or len(hits) >= 2
            or substantial
            or german_original == 0
        ):
            continue

        note = f"auto-tag: {len(hits)}/{len(texts)} Nachrichten Englisch"
        if requested:
            note += "; explizite Englisch-Aufforderung"
        if german_original == 0:
            note += "; kein eigenes Deutsch (nur Follow-ups/Seed)"
        note += f' — z.B. "{_truncate(hits[0]["text"])}"'
        flagged[d.id] = {
            "reasons": [REASON],
            "note": note,
            "_hits": hits,
            "_group": s.get("group"),
        }
    print(f"  scanned {scanned} sessions in study {study_id}")
    return flagged


def merge_into_file(new: dict[str, dict], apply: bool) -> tuple[int, int]:
    """Merge ``new`` into the on-disk JSON; returns (added, updated).

    Unions reasons with any existing entry and keeps manual notes appended,
    mirroring populate_session_exclusions so the scripts coexist.
    """
    existing: dict = {}
    if EXCLUSIONS_PATH.exists():
        try:
            existing = json.loads(EXCLUSIONS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

    added = updated = 0
    merged = dict(existing)
    for sid, entry in new.items():
        clean = {"reasons": entry["reasons"], "note": entry["note"]}
        prev = existing.get(sid)
        if prev is None:
            merged[sid] = clean
            added += 1
            continue
        prev_reasons = set(prev.get("reasons") or [])
        union = sorted(prev_reasons | set(clean["reasons"]))
        prev_note = (prev.get("note") or "").strip()
        if prev_note and clean["note"] not in prev_note:
            note = (
                clean["note"]
                if "auto-tag" in prev_note and REASON in str(prev.get("reasons"))
                else f"{clean['note']} | {prev_note}"
            )
        else:
            note = clean["note"] or prev_note
        if union == sorted(prev_reasons) and note == prev_note:
            continue
        merged[sid] = {"reasons": union, "note": note}
        updated += 1

    if apply:
        EXCLUSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = EXCLUSIONS_PATH.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        tmp.replace(EXCLUSIONS_PATH)
    return added, updated


async def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--study", required=True, help="Study id to scan.")
    p.add_argument(
        "--apply",
        action="store_true",
        help="Write to the exclusions JSON. Without it, dry run only.",
    )
    args = p.parse_args()

    print(f"Scanning for English messages (study {args.study})...")
    flagged = await scan(args.study)
    print(f"  {len(flagged)} session(s) flagged english\n")

    for sid, entry in sorted(flagged.items()):
        print(f"  {sid}  (group {entry['_group']})  — {entry['note']}")
        for h in entry["_hits"]:
            tag = "REQUEST" if h["request"] else f"{h['confidence']:.2f}"
            print(f"      [{tag}] {_truncate(h['text'], 100)}")

    added, updated = merge_into_file(flagged, apply=args.apply)
    verb = "wrote" if args.apply else "would write"
    print(f"\n{verb} {added} new, {updated} updated → {EXCLUSIONS_PATH}")
    if not args.apply:
        print("(dry run — pass --apply to write)")


if __name__ == "__main__":
    asyncio.run(main())
