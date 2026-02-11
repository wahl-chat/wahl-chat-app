# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import asyncio
import logging
import os
import aiohttp
import json

import socketio
import openai
from pydantic import ValidationError

from src.chatbot_async import (
    generate_swiper_assistant_response,
    get_improved_rag_query_voting_behavior,
    generate_pro_con_perspective,
    generate_chat_summary,
    generate_party_vote_behavior_summary,
)
from src.firebase_service import aget_default_context, aget_party_by_id
from src.models.chat import GroupChatSession, Message, Role
from src.models.dtos import (
    ChatResponseCompleteDto,
    ChatSessionInitializedDto,
    ChatUserMessageDto,
    InitChatSessionDto,
    ProConPerspectiveRequestDto,
    ProConPerspectiveDto,
    Status,
    StatusIndicator,
    RequestSummaryDto,
    SummaryDto,
    TextToSpeechRequestDto,
    TextToSpeechResponseDto,
    VoiceTranscribedDto,
    VotingBehaviorRequestDto,
    VotingBehaviorDto,
    Vote,
    VotingBehaviorSummaryChunkDto,
    VotingBehaviorVoteDto,
    WahlChatSwiperResponseCompleteDto,
    WahlChatSwiperUserMessageDto,
)
from src.vector_store_helper import identify_relevant_votes
from src.utils import (
    get_cors_allowed_origins,
    sanitize_text_for_speech,
    build_chat_history_string,
)
from src.chat_service import generate_chat_answer, MAX_RESPONSE_CHUNK_LENGTH
from src.audio_service import transcribe_audio, synthesize_speech

logger = logging.getLogger(__name__)
socketio_logger = logging.getLogger("socketio.asyncserver")
sio = socketio.AsyncServer(
    logger=socketio_logger,
    async_handlers=True,
    async_mode="aiohttp",
    allow_upgrades=True,
    monitor_clients=True,
    cors_allowed_origins=get_cors_allowed_origins(os.getenv("ENV")),
    always_connect=False,
    transports=["websocket"],
)


@sio.event
async def connect(sid: str, environ: dict):
    logger.info(f"Client connected: {sid}")


@sio.event
async def disconnect(sid: str, reason: str):
    if reason == sio.reason.CLIENT_DISCONNECT:
        logger.info(f"The client disconnected: {sid}")
    elif reason == sio.reason.SERVER_DISCONNECT:
        logger.info(f"The server disconnected the client: {sid}")
    else:
        logger.info(f"Disconnect reason for client {sid}: {reason}")
    # Remove the chat session from the session data
    async with sio.session(sid) as session:
        if "chat_sessions" in session:
            logger.info(f"Removing chat session data for client {sid}")
            del session["chat_sessions"]
    logger.info(f"Client disconnected: {sid}")


@sio.on("home")
async def home(sid: str, body: dict):
    await sio.emit("home_response", {"message": "Welcome to the wahl.chat API"}, to=sid)


@sio.on("chat_session_init")
async def init_chat_session(sid: str, body: dict):
    logger.info(f"Client {sid} requested chat session initialization with body: {body}")
    try:
        create_session_dto = InitChatSessionDto(**body)
    except ValidationError as e:
        logger.error(
            f"Error validating chat session initialization for client {sid}: {e}"
        )
        chat_session_initialized_dto = ChatSessionInitializedDto(
            session_id=None,
            status=Status(indicator=StatusIndicator.ERROR, message=str(e)),
        )
        await sio.emit(
            "chat_session_initialized",
            chat_session_initialized_dto.model_dump(),
            to=sid,
        )
        return

    logger.debug(f"Creating group chat session: {create_session_dto}")

    # Resolve context_id: use provided value or fall back to default context
    context_id = create_session_dto.context_id
    if context_id is None:
        default_context = await aget_default_context()
        if default_context is None:
            logger.error(f"No default context found for client {sid}")
            chat_session_initialized_dto = ChatSessionInitializedDto(
                session_id=None,
                status=Status(
                    indicator=StatusIndicator.ERROR,
                    message="No default context found. Please provide a context_id.",
                ),
            )
            await sio.emit(
                "chat_session_initialized",
                chat_session_initialized_dto.model_dump(),
                to=sid,
            )
            return
        context_id = default_context.context_id
        logger.debug(f"No context_id provided, using default: {context_id}")

    chat_session = GroupChatSession(
        session_id=create_session_dto.session_id,
        context_id=context_id,
        chat_history=create_session_dto.chat_history,
        title=create_session_dto.current_title,
        chat_response_llm_size=create_session_dto.chat_response_llm_size,
        last_quick_replies=create_session_dto.last_quick_replies,
        is_cacheable=create_session_dto.is_cacheable,
    )

    async with sio.session(sid) as session:
        session["chat_sessions"] = session.get("chat_sessions", {})
        session["chat_sessions"][create_session_dto.session_id] = chat_session

    logger.debug(f"Chat session initialized for client {sid}")

    chat_session_initialized_dto = ChatSessionInitializedDto(
        session_id=create_session_dto.session_id,
        status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
    )
    await sio.emit(
        "chat_session_initialized",
        chat_session_initialized_dto.model_dump(),
        to=sid,
    )


# event to emit a chat summary based on fct from chatbot_async.py
@sio.on("chat_summary_request")
async def chat_summary_request(sid: str, body: dict):
    logger.info(f"Client {sid} requested chat summary from session_id: {body}")
    try:
        request_summary = RequestSummaryDto(**body)
        chat_history = request_summary.chat_history
    except ValidationError as e:
        logger.error(f"Error validating chat summary request for client {sid}: {e}")
        response_dto = SummaryDto(
            chat_summary="",
            status=Status(indicator=StatusIndicator.ERROR, message=str(e)),
        )
        await sio.emit("chat_summary_complete", response_dto.model_dump(), to=sid)
        return

    try:
        chat_summary = await generate_chat_summary(chat_history)
        logger.debug(f"Chat summary generated: {chat_summary}")
        response_dto = SummaryDto(
            chat_summary=chat_summary,
            status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
        )
        await sio.emit("chat_summary_complete", response_dto.model_dump(), to=sid)
    except Exception as e:
        logger.error(
            f"Error generating chat summary for session {request_summary}: {e}"
        )
        response_dto = SummaryDto(
            chat_summary="Hier sollte eigentlich eine Zusammenfassung stehen...",
            status=Status(indicator=StatusIndicator.ERROR, message=str(e)),
        )
        await sio.emit("chat_summary_complete", response_dto.model_dump(), to=sid)
        return


@sio.on("pro_con_perspective_request")
async def get_pro_con_perspective(sid: str, body: dict):
    logger.info(f"Client {sid} requested pro/con perspective with body: {body}")
    try:
        pro_con_assessment = ProConPerspectiveRequestDto(**body)
        party_id = pro_con_assessment.party_id
        context_id = pro_con_assessment.context_id
        last_user_message_str = pro_con_assessment.last_user_message
        last_assistant_message_str = pro_con_assessment.last_assistant_message
    except ValidationError as e:
        logger.error(
            f"Error validating pro/con perspective request for client {sid}: {e}"
        )
        response_dto = ProConPerspectiveDto(
            request_id=None,
            message=Message(role="assistant", content=""),
            status=Status(indicator=StatusIndicator.ERROR, message=str(e)),
        )
        await sio.emit(
            "pro_con_perspective_complete", response_dto.model_dump(), to=sid
        )
        return

    logger.debug(
        f"Generating pro/con perspective for party {party_id} with user message '{last_user_message_str}' and assistant message '{last_assistant_message_str}'"
    )

    try:
        party = await aget_party_by_id(party_id)

        if party is None:
            raise ValueError(f"Party {party_id} not found")

        last_user_message = Message(role="user", content=last_user_message_str)
        last_assistant_message = Message(
            role="assistant", content=last_assistant_message_str
        )

        chat_history = [last_user_message, last_assistant_message]

        pro_con_perspective = await generate_pro_con_perspective(
            chat_history, party, context_id
        )

        logger.debug(f"Emitting pro/con perspective to client {sid}")

        response_dto = ProConPerspectiveDto(
            request_id=pro_con_assessment.request_id,
            message=pro_con_perspective,
            status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
        )

        await sio.emit(
            "pro_con_perspective_complete", response_dto.model_dump(), to=sid
        )
    except Exception as e:
        logger.error(
            f"Error generating pro/con perspective for party {party_id}: {e}",
            exc_info=True,
        )
        response_dto = ProConPerspectiveDto(
            request_id=pro_con_assessment.request_id,
            message=None,
            status=Status(indicator=StatusIndicator.ERROR, message=str(e)),
        )
        await sio.emit(
            "pro_con_perspective_complete", response_dto.model_dump(), to=sid
        )
        return


@sio.on("chat_answer_request")
async def chat_answer_request(sid: str, body: dict):
    """Socket event handler for chat - handles both text and voice messages.

    If audio_bytes is present, transcribes the audio first, then processes through chat flow.
    """
    logger.info(f"Client {sid} requested chat answer with body: {body}")
    try:
        chat_message_data = ChatUserMessageDto(**body)
    except ValidationError as e:
        logger.error(f"Error validating chat message data for client {sid}: {e}")
        chat_response_complete_dto = ChatResponseCompleteDto(
            session_id=None,
            status=Status(
                indicator=StatusIndicator.ERROR,
                message=str(e),
            ),
        )
        await sio.emit(
            "chat_response_complete",
            chat_response_complete_dto.model_dump(),
            to=sid,
        )
        return

    logger.debug(f"Chat message data: {chat_message_data}")

    user_message_content = chat_message_data.user_message

    # Handle voice message if audio is present
    if chat_message_data.audio_bytes:
        try:
            # Transcribe the audio
            transcribed_text = await transcribe_audio(
                audio_bytes=chat_message_data.audio_bytes,
                language=chat_message_data.language,
            )

            # Emit the transcription to the client if grouped_message_id is provided
            if chat_message_data.grouped_message_id:
                transcribed_dto = VoiceTranscribedDto(
                    session_id=chat_message_data.session_id,
                    grouped_message_id=chat_message_data.grouped_message_id,
                    message_id=chat_message_data.id,
                    transcribed_text=transcribed_text,
                )
                await sio.emit(
                    "voice_transcribed", transcribed_dto.model_dump(), to=sid
                )

            # Use transcribed text as the user message
            user_message_content = transcribed_text

        except openai.BadRequestError as e:
            logger.error(
                f"Error transcribing audio for client {sid}: {e}", exc_info=True
            )
            chat_response_complete_dto = ChatResponseCompleteDto(
                session_id=chat_message_data.session_id,
                status=Status(
                    indicator=StatusIndicator.ERROR,
                    message=f"Fehler bei der Spracherkennung: {e}",
                ),
            )
            await sio.emit(
                "chat_response_complete",
                chat_response_complete_dto.model_dump(),
                to=sid,
            )
            return
        except Exception as e:
            logger.error(
                f"Error processing voice message for client {sid}: {e}", exc_info=True
            )
            chat_response_complete_dto = ChatResponseCompleteDto(
                session_id=chat_message_data.session_id,
                status=Status(
                    indicator=StatusIndicator.ERROR,
                    message="Es ist ein Fehler bei der Verarbeitung der Sprachnachricht aufgetreten.",
                ),
            )
            await sio.emit(
                "chat_response_complete",
                chat_response_complete_dto.model_dump(),
                to=sid,
            )
            return

    await generate_chat_answer(
        sio=sio,
        sid=sid,
        session_id=chat_message_data.session_id,
        user_message_content=user_message_content,
        party_ids=chat_message_data.party_ids,
        user_is_logged_in=chat_message_data.user_is_logged_in,
        message_id=chat_message_data.id,
    )


@sio.on("text_to_speech_request")
async def handle_text_to_speech(sid: str, body: dict):
    """
    Socket event handler for text-to-speech requests.
    Looks up message by ID from chat session, sanitizes it, and returns audio.
    """
    logger.info(f"Client {sid} requested text-to-speech")
    try:
        request_data = TextToSpeechRequestDto(**body)
    except ValidationError as e:
        logger.error(f"Error validating TTS request for client {sid}: {e}")
        response_dto = TextToSpeechResponseDto(
            session_id=body.get("session_id", ""),
            message_id=body.get("message_id", ""),
            party_id=body.get("party_id", ""),
            audio_base64="",
            status=Status(
                indicator=StatusIndicator.ERROR,
                message=str(e),
            ),
        )
        await sio.emit("text_to_speech_complete", response_dto.model_dump(), to=sid)
        return

    try:
        # Look up the chat session
        async with sio.session(sid) as session:
            chat_session: GroupChatSession = session.get("chat_sessions", {}).get(
                request_data.session_id
            )
            if chat_session is None:
                raise ValueError(f"Chat session {request_data.session_id} not found")

            chat_history = chat_session.chat_history

            # Debug: log message IDs in history
            logger.debug(
                f"Looking for message_id={request_data.message_id} in {len(chat_history)} messages"
            )
            for i, msg in enumerate(chat_history):
                logger.debug(
                    f"  Message {i}: id={msg.id}, party_id={msg.party_id}, role={msg.role}"
                )

            # Find the message by ID
            message = None
            for msg in chat_history:
                if msg.id == request_data.message_id:
                    message = msg
                    break

            if message is None:
                raise ValueError(
                    f"Message with ID {request_data.message_id} not found in session. Available IDs: {[m.id for m in chat_history]}"
                )

        # Sanitize the text for speech
        text_for_speech = sanitize_text_for_speech(message.content)

        if not text_for_speech:
            raise ValueError("No text content to synthesize")

        # Synthesize speech
        audio_base64 = await synthesize_speech(text=text_for_speech)

        response_dto = TextToSpeechResponseDto(
            session_id=request_data.session_id,
            message_id=request_data.message_id,
            party_id=request_data.party_id,
            audio_base64=audio_base64,
            status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
        )
        await sio.emit("text_to_speech_complete", response_dto.model_dump(), to=sid)

    except openai.BadRequestError as e:
        logger.error(f"Error synthesizing speech for client {sid}: {e}", exc_info=True)
        response_dto = TextToSpeechResponseDto(
            session_id=request_data.session_id,
            message_id=request_data.message_id,
            party_id=request_data.party_id,
            audio_base64="",
            status=Status(
                indicator=StatusIndicator.ERROR,
                message=f"Error synthesizing text to speech: {e}",
            ),
        )
        await sio.emit("text_to_speech_complete", response_dto.model_dump(), to=sid)
    except Exception as e:
        logger.error(
            f"Error processing TTS request for client {sid}: {e}", exc_info=True
        )
        response_dto = TextToSpeechResponseDto(
            session_id=request_data.session_id,
            message_id=request_data.message_id,
            party_id=request_data.party_id,
            audio_base64="",
            status=Status(
                indicator=StatusIndicator.ERROR,
                message=f"Error generating text to speech: {e}",
            ),
        )
        await sio.emit("text_to_speech_complete", response_dto.model_dump(), to=sid)


@sio.on("voting_behavior_request")
async def get_voting_behavior(sid: str, body: dict):
    try:
        improved_rag_query = None
        request_data = VotingBehaviorRequestDto(**body)

        party = await aget_party_by_id(request_data.party_id)

        if party is None:
            raise ValueError(f"Party {request_data.party_id} not found")

        # Improve the RAG query
        improved_rag_query = await get_improved_rag_query_voting_behavior(
            party, request_data.last_user_message, request_data.last_assistant_message
        )

        # Get the relevant votes for the last answer
        relevant_votes = await identify_relevant_votes(improved_rag_query)

        # Collect all votes first
        votes: list[Vote] = []
        for vote_doc in relevant_votes:
            vote_data_json_str = vote_doc.metadata.get("vote_data_json_str", "{}")
            vote_data = json.loads(vote_data_json_str)
            vote = Vote(**vote_data)

            # Check if the party really voted in this vote
            res = [
                party_vote
                for party_vote in vote.voting_results.by_party
                if party_vote.party == party.party_id
            ]
            if not res:
                continue

            votes.append(vote)
            # Emit each vote as it's processed
            vote_dto = VotingBehaviorVoteDto(
                request_id=request_data.request_id,
                vote=vote,
            )
            await sio.emit(
                "voting_behavior_result",
                vote_dto.model_dump(),
                to=sid,
            )

        # Stream the vote behavior summary
        complete_message = ""
        if party:
            summary_stream = await generate_party_vote_behavior_summary(
                party,
                request_data.last_user_message,
                request_data.last_assistant_message,
                votes,
                summary_llm_size=request_data.summary_llm_size,
                use_premium_llms=request_data.user_is_logged_in,
            )
            chunk_index = 0
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

                for i in range(0, len(text_content), MAX_RESPONSE_CHUNK_LENGTH):
                    if i > 0:
                        # Sleep for a short time to simulate processing time
                        await asyncio.sleep(0.025)
                    split_chunk_content = text_content[
                        i : i + MAX_RESPONSE_CHUNK_LENGTH
                    ]
                    summary_chunk_dto = VotingBehaviorSummaryChunkDto(
                        request_id=request_data.request_id,
                        chunk_index=chunk_index,
                        summary_chunk=split_chunk_content,
                        is_end=False,
                    )

                    # Still emit chunks for progressive display
                    await sio.emit(
                        "voting_behavior_summary_chunk",
                        summary_chunk_dto.model_dump(),
                        to=sid,
                    )
                    chunk_index += 1

        # Send final response
        voting_behavior = VotingBehaviorDto(
            request_id=request_data.request_id,
            message=complete_message,
            status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
            votes=votes,
            rag_query=improved_rag_query,
        )

        await sio.emit("voting_behavior_complete", voting_behavior.model_dump(), to=sid)
    except openai.BadRequestError as e:
        logger.error(f"Error processing voting behavior request: {e}", exc_info=True)
        error_response = VotingBehaviorDto(
            request_id=body.get("request_id"),
            message="Hierzu kann ich leider keine Informationen bereitstellen.",
            status=Status(indicator=StatusIndicator.ERROR, message=str(e)),
            votes=[],
            rag_query=improved_rag_query,
        )
    except Exception as e:
        logger.error(f"Error processing voting behavior request: {e}", exc_info=True)
        error_response = VotingBehaviorDto(
            request_id=body.get("request_id"),
            message="Es tut mir Leid, es ist ein Fehler aufgetreten. Bitte versuche es später erneut.",
            status=Status(indicator=StatusIndicator.ERROR, message=str(e)),
            votes=[],
            rag_query=improved_rag_query,
        )
        await sio.emit("voting_behavior_complete", error_response.model_dump(), to=sid)


@sio.on("mock_websocket_usage")
async def mock_websocket_usage(sid: str, body: dict):
    # initialize chat session
    await init_chat_session(sid, body)

    NUMBER_OF_REQUESTS = 10
    NUMBER_OF_COROUTINES = 10
    NUMBER_OF_CHUNKS = 1000

    async def fetch_cat_fact(session):
        """Fetches a single cat fact from the API."""
        url = "https://httpbin.org/get"
        async with session.get(url) as response:
            if response.status == 200:
                return "is_da"
            else:
                return f"Error: {response.status}"

    async def fetch_facts_coroutine(id, num_requests):
        """Coroutine to fetch a number of cat facts and store them in a shared list."""
        # Create a TCPConnector with a larger pool size
        connector = aiohttp.TCPConnector(limit=200)
        async with aiohttp.ClientSession(connector=connector) as session:
            for _ in range(num_requests):
                _ = await fetch_cat_fact(session)

    # test the effect of multiple coroutines
    num_coroutines = NUMBER_OF_COROUTINES
    num_requests_per_coroutine = NUMBER_OF_REQUESTS

    # Create a list of coroutines
    tasks = [
        fetch_facts_coroutine(i, num_requests_per_coroutine)
        for i in range(num_coroutines)
    ]

    # Run all coroutines concurrently
    await asyncio.gather(*tasks)

    # mock emitting of party responses
    logger.info(f"Mock emitting of {NUMBER_OF_CHUNKS} party responses for client {sid}")
    for i in range(NUMBER_OF_CHUNKS):
        await sio.emit("mock_response_chunk_ready", {"message": f"{i}"}, to=sid)
    logger.info(f"Completed: Mock emitting of party responses for client {sid}")

    # mock emitting of party response complete
    await sio.emit("mock_response_complete", {"message": "Success"}, to=sid)


@sio.on("swiper_assistant_session_init")
async def init_swiper_assistant_session(sid: str, body: dict):
    logger.debug(
        f"Client {sid} requested wahl-chat-swiper session initialization with body: {body}"
    )
    try:
        init_chat_session_dto = InitChatSessionDto(**body)
    except ValidationError as e:
        logger.error(
            f"Error validating wahl-chat-swiper session initialization request for client {sid}: {e}"
        )
        chat_session_initialized_dto = ChatSessionInitializedDto(
            session_id=None,
            status=Status(indicator=StatusIndicator.ERROR, message=str(e)),
        )
        await sio.emit(
            "swiper_assistant_session_initialized",
            chat_session_initialized_dto.model_dump(),
            to=sid,
        )
        return

    logger.debug(f"Creating wahl-chat-swiper session: {init_chat_session_dto}")

    # Resolve context_id: use provided value or fall back to default context
    context_id = init_chat_session_dto.context_id
    if context_id is None:
        default_context = await aget_default_context()
        if default_context is None:
            logger.error(f"No default context found for swiper client {sid}")
            chat_session_initialized_dto = ChatSessionInitializedDto(
                session_id=None,
                status=Status(
                    indicator=StatusIndicator.ERROR,
                    message="No default context found. Please provide a context_id.",
                ),
            )
            await sio.emit(
                "swiper_assistant_session_initialized",
                chat_session_initialized_dto.model_dump(),
                to=sid,
            )
            return
        context_id = default_context.context_id
        logger.debug(
            f"No context_id provided for swiper session, using default: {context_id}"
        )

    chat_session = GroupChatSession(
        session_id=init_chat_session_dto.session_id,
        context_id=context_id,
        title=init_chat_session_dto.current_title,
        chat_history=init_chat_session_dto.chat_history,
        chat_response_llm_size=init_chat_session_dto.chat_response_llm_size,
    )

    async with sio.session(sid) as session:
        session["swiper_assistant_sessions"] = session.get(
            "swiper_assistant_sessions", {}
        )
        session["swiper_assistant_sessions"][chat_session.session_id] = chat_session

    logger.debug(f"Chat session initialized for client {sid}")
    chat_session_initialized_dto = ChatSessionInitializedDto(
        session_id=init_chat_session_dto.session_id,
        status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
    )

    await sio.emit(
        "swiper_assistant_session_initialized",
        chat_session_initialized_dto.model_dump(),
        to=sid,
    )


@sio.on("swiper_assistant_answer_request")
async def swiper_assistant_answer_request(sid: str, body: dict):
    logger.debug(f"Client {sid} requested wahl-chat-swiper answer with body: {body}")

    try:
        chat_message_data = WahlChatSwiperUserMessageDto(**body)
    except ValidationError as e:
        logger.error(
            f"Error validating wahl-chat-swiper message data for client {sid}: {e}"
        )
        chat_response_complete_dto = WahlChatSwiperResponseCompleteDto(
            session_id=None,
            complete_message=Message(
                role=Role.ASSISTANT,
                content="Es tut mir Leid, leider ist ein Fehler aufgetreten. Bitte versuche es später erneut.",
                sources=[],
            ),
            status=Status(
                indicator=StatusIndicator.ERROR,
                message=str(e),
            ),
        )
        await sio.emit(
            "swiper_assistant_response_complete",
            chat_response_complete_dto.model_dump(),
            to=sid,
        )
        return

    logger.debug(f"wahl.chat Swiper message data: {chat_message_data}")

    # Extract user message
    user_message = Message(
        role="user",
        content=chat_message_data.user_message,
    )

    # Access chat session from socket session
    try:
        async with sio.session(sid) as session:
            chat_session: GroupChatSession = session.get(
                "swiper_assistant_sessions", {}
            ).get(chat_message_data.session_id)

            # Update session with user message
            chat_history = chat_session.chat_history
            # Append the user message if it not identical to the last message
            if (
                len(chat_history) == 0
                or chat_history[-1].content != user_message.content
            ):
                chat_history.append(user_message)
    except Exception as e:
        logger.error(
            f"Error accessing wahl-chat-swiper session for client {sid}: {e}",
            exc_info=True,
        )
        chat_response_complete_dto = WahlChatSwiperResponseCompleteDto(
            session_id=chat_message_data.session_id,
            complete_message=Message(
                role=Role.ASSISTANT,
                content="Es tut mir Leid, leider ist ein Fehler aufgetreten. Bitte versuche es später erneut.",
                sources=[],
            ),
            status=Status(
                indicator=StatusIndicator.ERROR,
                message="It seems like the chat session has not been started",
            ),
        )
        await sio.emit(
            "swiper_assistant_response_complete",
            chat_response_complete_dto.model_dump(),
            to=sid,
        )
        return

    chat_history_without_last_user_message = chat_history[:-1]
    chat_history_str = build_chat_history_string(
        chat_history_without_last_user_message, []
    )

    swiper_assistant_response = await generate_swiper_assistant_response(
        current_political_question=chat_message_data.current_political_question,
        conversation_history=chat_history_str,
        user_message=chat_message_data.user_message,
        chat_response_llm_size=chat_session.chat_response_llm_size,
    )

    chat_session.chat_history.append(swiper_assistant_response)

    chat_response_complete_dto = WahlChatSwiperResponseCompleteDto(
        session_id=chat_message_data.session_id,
        complete_message=swiper_assistant_response,
        status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
    )
    await sio.emit(
        "swiper_assistant_response_complete",
        chat_response_complete_dto.model_dump(),
        to=sid,
    )
