# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
SSE voting-behavior endpoint — POST /api/v1/voting-behavior.

Streams:
  8 type=vote_result — per-vote annotation (replaces V1 voting_behavior_result)
  0                  — summary text deltas (replaces V1 voting_behavior_summary_chunk)
  e / d / [DONE]    — finish events (replaces V1 voting_behavior_complete)

vote_record chunks are retrieved from the single wahlchat_chunks_{ENV} store
via retrieve(source_type="vote_record", ...) — NOT the legacy empty
justified_voting_behavior_dev collection.

The chunk payload shape (verified against the live store) is:
  top-level: text, citation_title, citation_url, publish_date, source_item_id,
             external_id, party_ids, party_id, meta, ...
  meta:      vote_results (list[{party_id, stance, yes, no, abstain, no_show}]),
             motion_outcome

This replaces the old vote_data_json_str approach (which worked against the old
schema). The Vote model is populated from the chunk data:
  - id         ← source_item_id (or external_id fallback)
  - url        ← citation_url
  - date       ← publish_date (truncated to date)
  - title      ← citation_title (or text[:100])
  - voting_results.by_party ← meta.vote_results mapped to VotingResultsByParty
  - voting_results.overall  ← summed from by_party tallies

NOTE: vote_record count is currently 284 which is below Qdrant's default
full_scan_threshold (~10 000). The selective source_type='vote_record' pre-filter
keeps the non-HNSW path cheap for now. REVISIT if vote_record grows past 10 000 —
add party_ids_contains filter to stay within tenant HNSW.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.auth import resolve_user_is_logged_in
from src.chatbot_async import (
    get_improved_rag_query_voting_behavior,
    generate_party_vote_behavior_summary,
)
from src.chat_service import with_heartbeat
from src.firebase_service import aget_context_by_id, aget_party_for_context
from src.ingestion.retrieve import retrieve
from src.models.context import DEFAULT_CONTEXT_ID
from src.models.dtos import (
    VotingBehaviorRequestDto,
    VotingBehaviorVoteDto,
)
from src.models.vote import (
    Link,
    Vote,
    VotingResults,
    VotingResultsByParty,
    VotingResultsOverall,
)
from src.chat_service import MAX_RESPONSE_CHUNK_LENGTH
from src.utils import GENERIC_ERROR_MESSAGE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

# SSE headers
# NOTE: StreamingResponse is used (not EventSourceResponse) because the generator
# yields pre-framed "data: ...\n\n" strings; EventSourceResponse would double-wrap them.
# NOTE: deliberately NO `x-vercel-ai-ui-message-stream: v1` header here — this
# endpoint emits legacy code-prefixed frames (`data: 8{...}` / `data: 0"..."`)
# that the frontend hand-parses; the header would falsely claim v5
# UI-message-stream framing to any AI SDK consumer.
_SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
}


def _chunk_payload_to_vote(payload: dict, party_id: str) -> Vote | None:
    """Map a vote_record ChunkRecord payload to a Vote model instance.

    Returns None if the payload is malformed or the party did not participate
    in this vote (caller should log + skip, never 500).

    Vote model is populated from the chunk payload shape verified against the
    live wahlchat_chunks_dev store:
      - id         ← source_item_id (fallback: external_id)
      - url        ← citation_url (fallback: "")
      - date       ← publish_date[:10] (YYYY-MM-DD)
      - title      ← citation_title (fallback: text[:120])
      - voting_results.by_party ← meta.vote_results (VoteResult list)
      - voting_results.overall  ← summed from by_party tallies
    """
    try:
        meta: dict = payload.get("meta") or {}
        vote_results_raw: list = meta.get("vote_results") or []

        # Require at least one vote_result entry — skip empty/malformed payloads.
        if not vote_results_raw:
            return None

        # Check this party participated in the vote.
        party_result = next(
            (r for r in vote_results_raw if r.get("party_id") == party_id), None
        )
        if party_result is None:
            return None

        # Build by_party list.
        by_party: list[VotingResultsByParty] = []
        total_yes = total_no = total_abstain = total_not_voted = total_members = 0
        for r in vote_results_raw:
            yes = int(r.get("yes") or 0)
            no = int(r.get("no") or 0)
            abstain = int(r.get("abstain") or 0)
            no_show = int(r.get("no_show") or 0)
            members = yes + no + abstain + no_show
            total_yes += yes
            total_no += no
            total_abstain += abstain
            total_not_voted += no_show
            total_members += members
            by_party.append(
                VotingResultsByParty(
                    party=r.get("party_id") or "",
                    members=members,
                    yes=yes,
                    no=no,
                    abstain=abstain,
                    not_voted=no_show,
                )
            )

        overall = VotingResultsOverall(
            yes=total_yes,
            no=total_no,
            abstain=total_abstain,
            not_voted=total_not_voted,
            members=total_members,
        )

        # Build vote identifier and URL.
        vote_id = str(
            payload.get("source_item_id") or payload.get("external_id") or "unknown"
        )
        citation_url = payload.get("citation_url") or ""
        # Derive date string (YYYY-MM-DD) from publish_date.
        publish_date_raw = payload.get("publish_date") or ""
        date_str = publish_date_raw[:10] if publish_date_raw else ""

        title = (
            payload.get("citation_title")
            or (payload.get("text") or "")[:120]
            or "Abstimmung"
        )
        outcome = meta.get("motion_outcome")

        links: list[Link] = []
        if citation_url:
            links.append(Link(url=citation_url, title=title))

        return Vote(
            id=vote_id,
            url=citation_url,
            date=date_str,
            title=title,
            subtitle=outcome,
            detail_text=payload.get("text"),
            links=links,
            voting_results=VotingResults(overall=overall, by_party=by_party),
            short_description=outcome,
            vote_category=None,
            # Do NOT populate from party_ids: that is EVERY faction that
            # participated in the roll call, not the motion's sponsor(s).
            # Rendering it as "Einreichende Partei(en)" mislabels all voting
            # parties as submitters. No submitter metadata exists in the
            # vote_record corpus yet, so leave it empty (the UI hides the
            # section); populate only from real submitter data later.
            submitting_parties=[],
        )

    except Exception as e:  # noqa: BLE001
        logger.warning(
            "vote_record payload could not be mapped to Vote (skipping): %s — payload keys: %s",
            e,
            list(payload.keys()),
        )
        return None


@router.post("/voting-behavior")
async def voting_behavior_endpoint(request: Request, body: VotingBehaviorRequestDto):
    """POST /api/v1/voting-behavior — streams votes + summary over SSE.

    Retrieves vote_record chunks from the single wahlchat_chunks_{ENV} store
    via retrieve(source_type='vote_record').

    V1 event map:
      voting_behavior_result        → 8 type=vote_result (per vote)
      voting_behavior_summary_chunk → 0 text delta (summary chunks)
      voting_behavior_complete      → e / d / [DONE]
    Pydantic validates request body.

    Auth: verification is OPTIONAL (no 401s). Premium LLM selection for the
    summary is derived server-side from the request's token (a valid,
    non-anonymous `Authorization: Bearer <Firebase ID token>`) — never from the
    client.
    """
    use_premium_llms = resolve_user_is_logged_in(request, "voting-behavior")

    async def stream():
        improved_rag_query = None
        try:
            context_id = body.context_id or DEFAULT_CONTEXT_ID
            party = await aget_party_for_context(context_id, body.party_id)
            if party is None:
                raise ValueError(
                    f"Party {body.party_id} not found in context {context_id}"
                )

            improved_rag_query = await get_improved_rag_query_voting_behavior(
                party, body.last_user_message, body.last_assistant_message
            )

            # Scope retrieval to the election context AND to votes this party
            # actually participated in. Without party_ids_contains, retrieve()
            # returns the GLOBAL top-10 vote_records and _chunk_payload_to_vote
            # then discards the ones the party didn't vote on — so a small party
            # can end up with zero results while relevant votes sit just below
            # the cut. region/legislature/level scoping also prevents mixing
            # Bundestag and Landtag records.
            ctx = await aget_context_by_id(context_id)
            region_path = ctx.region_path if ctx is not None else ["DE"]
            legislature_period_id = (
                ctx.legislature_period_id if ctx is not None else None
            )
            election_level = ctx.level if ctx is not None else None

            vote_payloads: list[dict] = await asyncio.to_thread(
                retrieve,
                improved_rag_query,
                source_type="vote_record",
                party_ids_contains=party.party_id,
                region_path=region_path,
                legislature_period_id=legislature_period_id,
                level=election_level,
                limit=10,
            )

            votes: list[Vote] = []
            for payload in vote_payloads:
                vote = _chunk_payload_to_vote(payload, party.party_id)
                if vote is None:
                    # Party did not participate or payload malformed — skip gracefully.
                    continue

                votes.append(vote)

                # 8: data annotation — vote_result (replaces V1 voting_behavior_result)
                vote_dto = VotingBehaviorVoteDto(
                    request_id=body.request_id,
                    vote=vote,
                )
                yield f"data: 8{json.dumps({'type': 'vote_result', **vote_dto.model_dump()})}\n\n"

            # Stream summary as text deltas (replaces V1 voting_behavior_summary_chunk)
            complete_message = ""
            if party:
                summary_stream = await generate_party_vote_behavior_summary(
                    party,
                    body.last_user_message,
                    body.last_assistant_message,
                    votes,
                    summary_llm_size=body.summary_llm_size,
                    use_premium_llms=use_premium_llms,
                )
                async for chunk in summary_stream:
                    chunk_content = chunk.text
                    if isinstance(chunk_content, str):
                        text_content = chunk_content
                    else:
                        logger.warning(
                            f"Unexpected chunk content type: {type(chunk_content)}"
                        )
                        continue

                    complete_message += text_content

                    # Split chunks per MAX_RESPONSE_CHUNK_LENGTH (preserves V1 chunking)
                    for i in range(0, len(text_content), MAX_RESPONSE_CHUNK_LENGTH):
                        if i > 0:
                            await asyncio.sleep(0.025)
                        split_chunk = text_content[i : i + MAX_RESPONSE_CHUNK_LENGTH]
                        # 0: text delta
                        yield f"data: 0{json.dumps(split_chunk)}\n\n"

            # Emit voting_behavior_complete annotation before finish events.
            # The frontend (generate-voting-behavior-summary.ts) only finalizes on a
            # `voting_behavior_complete` annotation; without it, completeVotingBehavior()
            # is never called and the UI stays in a loading state forever.
            # votes are already serialized Vote models; model_dump gives JSON-safe shape.
            yield f"data: 8{json.dumps({'type': 'voting_behavior_complete', 'request_id': body.request_id, 'votes': [v.model_dump(mode='json') for v in votes], 'message': complete_message})}\n\n"

            # Finish events (replaces V1 voting_behavior_complete)
            yield f"data: e{json.dumps({'finishReason': 'stop', 'usage': {}})}\n\n"
            yield f"data: d{json.dumps({'finishReason': 'stop', 'usage': {}})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(
                f"Error processing voting behavior request: {e}", exc_info=True
            )
            # Generic client-facing message only — full detail is logged above.
            yield f"data: 8{json.dumps({'type': 'error', 'message': GENERIC_ERROR_MESSAGE})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(with_heartbeat(stream()), headers=_SSE_HEADERS)
