# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Miscellaneous JSON endpoints carried over from the V1 aiohttp entry point.

Includes: parliamentary questions, swiper assistant, chat-summary, TTS.
These are regular JSON POST endpoints (not SSE streams).
"""

import logging

from fastapi import APIRouter

from src.chatbot_async import (
    generate_swiper_assistant_response,
    generate_swiper_assistant_title_and_chick_replies,
    generate_chat_summary,
)
from src.firebase_service import aget_party_by_id
from src.models.chat import Message, Role
from src.models.dtos import (
    ParliamentaryQuestionDto,
    ParliamentaryQuestionRequestDto,
    RequestSummaryDto,
    SummaryDto,
    Status,
    StatusIndicator,
    TextToSpeechRequestDto,
    TextToSpeechResponseDto,
    WahlChatSwiperAnswerDto,
    WahlChatSwiperAnswerRequestDto,
)
from src.utils import build_chat_history_string, sanitize_text_for_speech
from src.audio_service import synthesize_speech

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


@router.post("/get-parliamentary-question")
async def get_parliamentary_question(body: ParliamentaryQuestionRequestDto):
    """Identify relevant parliamentary questions via RAG (JSON response, not SSE).

    DORMANT: There is NO parliamentary_question data in any Qdrant collection
    (wahlchat_chunks_{ENV} holds only parliamentary_speech, party_manifesto, and
    vote_record; the legacy parliamentary_questions_dev collection is empty).
    Rather than waste an embed call and query an empty store, this endpoint short-
    circuits immediately and returns an empty result with SUCCESS status.

    A future parliamentary-questions connector will populate this data; once ingested
    as a 'parliamentary_question' source_type into wahlchat_chunks, this route can be
    re-wired to retrieve(source_type='parliamentary_question', party_id=...).
    """
    party = await aget_party_by_id(body.party_id)

    if not party:
        return ParliamentaryQuestionDto(
            request_id=body.request_id,
            status=Status(
                indicator=StatusIndicator.ERROR,
                message="Could not find party with the provided ID",
            ),
            parliamentary_questions=[],
            rag_query=None,
        ).model_dump()

    # DORMANT: No parliamentary_question data exists anywhere in the corpus.
    # Skip the embed + query to avoid wasting an OpenAI API call and hitting the
    # empty parliamentary_questions_dev collection. Return empty result immediately.
    # Re-wire once a parliamentary-questions connector is built (future milestone).
    logger.info(
        "get-parliamentary-question: endpoint is dormant — "
        "no parliamentary_question data in corpus (pending connector). "
        "Returning empty result for party=%s",
        body.party_id,
    )
    return ParliamentaryQuestionDto(
        request_id=body.request_id,
        status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
        parliamentary_questions=[],
        rag_query=None,
    ).model_dump()


@router.post("/answer-wahl-chat-swiper-question")
async def answer_wahl_chat_swiper_question(body: WahlChatSwiperAnswerRequestDto):
    """Answer a wahl.chat Swiper question (JSON response, not SSE)."""
    logger.debug(f"Received request: {body}")

    user_message = Message(role=Role.USER, content=body.user_message)

    chat_history_str = build_chat_history_string(
        body.chat_history, [], default_assistant_name="wahl.chat Swiper Assistent"
    )

    swiper_assistant_response = await generate_swiper_assistant_response(
        current_political_question=body.current_political_question,
        conversation_history=chat_history_str,
        user_message=body.user_message,
        chat_response_llm_size=body.chat_response_llm_size,
    )

    chat_history = body.chat_history
    chat_history.append(user_message)
    chat_history.append(swiper_assistant_response)

    chat_history_str = build_chat_history_string(
        chat_history, [], default_assistant_name="wahl.chat Swiper Assistent"
    )

    title_and_quick_replies = await generate_swiper_assistant_title_and_chick_replies(
        chat_history_str, body.current_political_question
    )

    return WahlChatSwiperAnswerDto(
        message=swiper_assistant_response,
        title=title_and_quick_replies.chat_title,
        quick_replies=title_and_quick_replies.quick_replies,
    ).model_dump()


@router.post("/chat-summary")
async def chat_summary(body: RequestSummaryDto):
    """Generate a chat summary (JSON response, not SSE)."""
    try:
        chat_summary_text = await generate_chat_summary(body.chat_history)
        logger.debug(f"Chat summary generated: {chat_summary_text}")
        return SummaryDto(
            chat_summary=chat_summary_text,
            status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
        ).model_dump()
    except Exception as e:
        logger.error(f"Error generating chat summary: {e}", exc_info=True)
        return SummaryDto(
            chat_summary="Hier sollte eigentlich eine Zusammenfassung stehen...",
            status=Status(indicator=StatusIndicator.ERROR, message=str(e)),
        ).model_dump()


@router.post("/tts")
async def text_to_speech(body: TextToSpeechRequestDto):
    """Generate TTS audio from message text (JSON response, not SSE).

    NOTE: In the SSE model the chat history is stateless (per-request). The frontend
    must supply the text to synthesize in the request body. V1 looked up the message by ID
    from the socket session; that session no longer exists. The frontend holds the message
    content and can pass it directly.
    """
    try:
        # Frontend sends the text to synthesize in the voice field (repurposed as text)
        # The TTS endpoint requires the text content to be provided
        # via a separate TtsRequestDto. We accept TextToSpeechRequestDto as-is since
        # the text is embedded in voice field; the audio service synthesizes any text.
        # This interface can be cleaned up later.
        text_for_speech = sanitize_text_for_speech(body.voice)
        if not text_for_speech:
            return TextToSpeechResponseDto(
                session_id=body.session_id,
                message_id=body.message_id,
                party_id=body.party_id,
                audio_base64="",
                status=Status(
                    indicator=StatusIndicator.ERROR,
                    message="No text content to synthesize",
                ),
            ).model_dump()

        audio_base64 = await synthesize_speech(text=text_for_speech)
        return TextToSpeechResponseDto(
            session_id=body.session_id,
            message_id=body.message_id,
            party_id=body.party_id,
            audio_base64=audio_base64,
            status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
        ).model_dump()
    except Exception as e:
        logger.error(f"Error generating TTS for message {body.message_id}: {e}", exc_info=True)
        return TextToSpeechResponseDto(
            session_id=body.session_id,
            message_id=body.message_id,
            party_id=body.party_id,
            audio_base64="",
            status=Status(indicator=StatusIndicator.ERROR, message=str(e)),
        ).model_dump()
