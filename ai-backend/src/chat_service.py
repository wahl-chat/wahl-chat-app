# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Chat service module containing core chat answer generation logic.
"""

import asyncio
from datetime import datetime
import logging
import random
import uuid
from typing import List, Dict, Optional, Union

import openai
import socketio
from langchain_core.messages import BaseMessageChunk
from langchain_core.documents import Document

from src.chatbot_async import (
    generate_chat_title_and_chick_replies,
    get_question_targets_and_type,
    generate_improvement_rag_query,
    generate_streaming_chatbot_response,
    generate_streaming_chatbot_comparing_response,
)
from src.firebase_service import (
    aget_cached_answers_for_party,
    aget_parties_for_context,
    aget_proposed_questions_for_party,
    awrite_cached_answer_for_party,
)
from src.models.chat import CachedResponse, GroupChatSession, Message, Role
from src.models.dtos import (
    ChatResponseCompleteDto,
    PartyResponseChunkDto,
    PartyResponseCompleteDto,
    QuickRepliesAndTitleDto,
    RespondingPartiesDto,
    SourcesDto,
    Status,
    StatusIndicator,
)
from src.models.context import ContextParty
from src.models.party import WAHL_CHAT_PARTY
from src.vector_store_helper import identify_relevant_docs_with_llm_based_reranking
from src.utils import (
    build_chat_history_string,
    get_chat_history_hash_key,
    sanitize_references,
)

MAX_RESPONSE_CHUNK_LENGTH = 10

logger = logging.getLogger(__name__)


async def emit_cached_party_response(
    sio: socketio.AsyncServer,
    sid: str,
    party: ContextParty,
    group_chat_session: GroupChatSession,
    cached_response: CachedResponse,
):
    """Emit a cached response to the client, simulating streaming."""
    # Sleep for a short time to simulate processing time
    await asyncio.sleep(1)
    sources_dto = SourcesDto(
        session_id=group_chat_session.session_id,
        sources=cached_response.sources,
        party_id=party.party_id,
        rag_query=cached_response.rag_query,
    )
    await sio.emit("sources_ready", sources_dto.model_dump(), to=sid)

    full_response = cached_response.content
    # artificially chunk the response and emit it
    chunk_index = 0
    for i in range(0, len(full_response), MAX_RESPONSE_CHUNK_LENGTH):
        chunk = full_response[i : i + MAX_RESPONSE_CHUNK_LENGTH]
        chat_response_dto = PartyResponseChunkDto(
            session_id=group_chat_session.session_id,
            party_id=party.party_id,
            chunk_index=chunk_index,
            chunk_content=chunk,
            is_end=False,
        )
        await sio.emit(
            "party_response_chunk_ready", chat_response_dto.model_dump(), to=sid
        )
        chunk_index += 1
        await asyncio.sleep(0.025)
    # Emit a finalizing chunk
    chat_response_dto = PartyResponseChunkDto(
        session_id=group_chat_session.session_id,
        party_id=party.party_id,
        chunk_index=chunk_index,
        chunk_content="",
        is_end=True,
    )

    message_id = str(uuid.uuid4())
    chatbot_message = Message(
        id=message_id,
        role="assistant",
        content=full_response,
        sources=cached_response.sources,
        party_id=party.party_id,
        current_chat_title=group_chat_session.title,
        quick_replies=[],
        rag_query=cached_response.rag_query,
    )
    group_chat_session.chat_history.append(chatbot_message)

    # Emit party response complete event
    party_response_complete_dto = PartyResponseCompleteDto(
        session_id=group_chat_session.session_id,
        party_id=party.party_id,
        complete_message=full_response,
        message_id=message_id,
        status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
    )
    logger.debug(f"Party response complete: {party_response_complete_dto}")
    await sio.emit(
        "party_response_complete", party_response_complete_dto.model_dump(), to=sid
    )
    logger.info(
        f"Party response {party_response_complete_dto.model_dump()} for {party.party_id} emitted to client {sid}"
    )


async def fetch_and_emit_party_response(
    sio: socketio.AsyncServer,
    sid: str,
    party: ContextParty,
    conversation_history_str: str,
    question_for_party: str,
    group_chat_session: GroupChatSession,
    all_available_parties: List[ContextParty],
    use_premium_llms: bool,
    is_proposed_question: bool = False,
    is_cacheable_chat: bool = True,
    relevant_docs: Optional[Union[List[Document], Dict[str, List[Document]]]] = None,
    parties_being_compared: Optional[List[ContextParty]] = None,
    is_comparing_question: bool = False,
    improved_rag_query_list: List[str] = [],
):
    """Fetch and emit a party response, with caching and streaming support."""
    # We'll store single-party docs and multi-party docs separately:
    relevant_docs_list: Optional[List[Document]] = None
    relevant_docs_dict: Optional[Dict[str, List[Document]]] = None

    # For caching
    cache_key: Optional[str] = None
    cached_answer_to_emit: Optional[CachedResponse] = None
    cache_conversation_history_str = build_chat_history_string(
        group_chat_session.chat_history, all_available_parties
    )
    # full_response will be assigned a BaseMessageChunk later
    full_response: Optional[BaseMessageChunk] = None

    try:
        # Handle proposed question => possibility of picking a cached response
        logger.debug(
            f"Fetching party response for party {party.party_id}: is_proposed_question={is_proposed_question}, is_cacheable_chat={is_cacheable_chat}"
        )
        if is_proposed_question or is_cacheable_chat:
            if is_proposed_question:
                cache_key = question_for_party
            else:
                cache_key = get_chat_history_hash_key(cache_conversation_history_str)
            logger.debug(
                f"Checking cache for party {party.party_id} with cache key {cache_key}"
            )
            existing_cached_answers: List[
                CachedResponse
            ] = await aget_cached_answers_for_party(party.party_id, cache_key)
            logger.info(
                f"Fetched {len(existing_cached_answers)} cached answers for party {party.party_id} and cache_key {cache_key}"
            )

            cached_answer_limit = 1 if is_proposed_question else 1
            # Select a random cached answer to emit, if None is selected, the chatbot will generate a new response (and add it to the cache for proposed questions)
            # If there are at least `cached_answer_limit` cache answers, we'll always emit a cached answer
            possible_answers: list[CachedResponse | None] | list[CachedResponse] = (
                existing_cached_answers + [None]
                if len(existing_cached_answers) < cached_answer_limit
                else existing_cached_answers
            )
            cached_answer_to_emit = random.choice(possible_answers)
            logger.debug(
                f"Selected cached answer: {cached_answer_to_emit} (None means a new response will be generated)"
            )

        if cached_answer_to_emit is not None:
            logger.info(
                f"Selected cached answer for party {party.party_id} and question {question_for_party}: {cached_answer_to_emit}"
            )
            await emit_cached_party_response(
                sio,
                sid,
                party,
                group_chat_session,
                cached_answer_to_emit,
            )
            return

        # If not is_comparing_question, we do a single-party RAG
        if not is_comparing_question:
            improved_rag_query = await generate_improvement_rag_query(
                party,
                conversation_history_str,
                question_for_party,
                context_id=group_chat_session.context_id,
            )
            logger.debug(f"Improved RAG query: {improved_rag_query}")

            # Identify relevant docs as a list
            relevant_docs_list = await identify_relevant_docs_with_llm_based_reranking(
                party=party,
                rag_query=improved_rag_query,
                chat_history=conversation_history_str,
                user_message=question_for_party,
                context_id=group_chat_session.context_id,
            )
            # comparing scenario requires improved_rag_query to be a list, so match for both scenarios
            improved_rag_query_list = [improved_rag_query]

            logger.debug(f"Identified relevant docs (list): {relevant_docs_list}")

            sources = []
            for source_doc in relevant_docs_list:
                # Safely parse page_number. If it's None, fallback to 0
                page_raw = source_doc.metadata.get("page", 0)
                page_number = int(page_raw if page_raw is not None else 0)
                # Shift by +1 for display indexing
                page_number += 1

                source = {
                    "source": source_doc.metadata.get("document_name"),
                    "page": page_number,
                    "document_publish_date": source_doc.metadata.get(
                        "document_publish_date"
                    ),
                    "url": source_doc.metadata.get("url"),
                    "source_document": source_doc.metadata.get("source_document"),
                }
                sources.append(source)

            sources_dto = SourcesDto(
                session_id=group_chat_session.session_id,
                party_id=party.party_id,
                rag_query=improved_rag_query_list,
                sources=sources,
            )
            await sio.emit("sources_ready", sources_dto.model_dump(), to=sid)

        else:
            # For comparing scenario, we assume relevant_docs is dict
            if relevant_docs is None:
                # Fallback to empty dict if no docs are provided
                relevant_docs_dict = {}
            else:
                # We assume user passed in a dict
                relevant_docs_dict = dict(relevant_docs)  # type: ignore

            logger.debug(f"Identified relevant docs (dict): {relevant_docs_dict}")
            sources = []
            if parties_being_compared:
                for rel_party in parties_being_compared:
                    for source_doc in relevant_docs_dict.get(rel_party.party_id, []):
                        page_raw = source_doc.metadata.get("page", 0)
                        page_number = int(page_raw if page_raw is not None else 0)
                        page_number += 1

                        source = {
                            "source": source_doc.metadata.get("document_name"),
                            "page": page_number,
                            "document_publish_date": source_doc.metadata.get(
                                "document_publish_date"
                            ),
                            "url": source_doc.metadata.get("url"),
                            "source_document": source_doc.metadata.get(
                                "source_document"
                            ),
                            "party_id": rel_party.party_id,
                        }
                        sources.append(source)

            sources_dto = SourcesDto(
                session_id=group_chat_session.session_id,
                party_id=party.party_id,
                rag_query=improved_rag_query_list,
                sources=sources,
            )
            await sio.emit("sources_ready", sources_dto.model_dump(), to=sid)

        # Now generate the answer stream
        if not is_comparing_question:
            chunk_stream = await generate_streaming_chatbot_response(
                party,
                conversation_history_str,
                question_for_party,
                relevant_docs_list or [],
                all_parties=all_available_parties,
                chat_response_llm_size=group_chat_session.chat_response_llm_size,
                context_id=group_chat_session.context_id,
                use_premium_llms=use_premium_llms,
            )
        else:
            chunk_stream = await generate_streaming_chatbot_comparing_response(
                party,
                conversation_history_str,
                question_for_party,
                relevant_docs_dict or {},
                parties_being_compared or [],
                chat_response_llm_size=group_chat_session.chat_response_llm_size,
                use_premium_llms=use_premium_llms,
            )

        chunk_index = 0
        async for message_chunk in chunk_stream:
            logger.debug(f"Received message chunk: {message_chunk}")

            chunk_content = message_chunk.content
            # Skip non-text chunks (e.g. reasoning chunks) if returned by the model
            if (
                isinstance(chunk_content, dict)
                and chunk_content.get("type", "text") != "text"
            ):
                logger.debug(f"Skipping non-text chunk: {chunk_content}")
                continue

            if full_response is None:
                full_response = message_chunk
            else:
                full_response += message_chunk

            # Use text instead of content attribute to deal with new response structure of Gemini-3 (https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai#invocation)
            chunk_text = message_chunk.text
            for i in range(0, len(chunk_text), MAX_RESPONSE_CHUNK_LENGTH):
                if i > 0:
                    # Sleep for a short time to simulate processing time
                    await asyncio.sleep(0.025)
                chunk_content = chunk_text[i : i + MAX_RESPONSE_CHUNK_LENGTH]
                chat_response_dto = PartyResponseChunkDto(
                    session_id=group_chat_session.session_id,
                    party_id=party.party_id,
                    chunk_index=chunk_index,
                    chunk_content=chunk_content,
                    is_end=False,
                )
                await sio.emit(
                    "party_response_chunk_ready", chat_response_dto.model_dump(), to=sid
                )
                chunk_index += 1

        # Emit a finalizing chunk
        chat_response_dto = PartyResponseChunkDto(
            session_id=group_chat_session.session_id,
            party_id=party.party_id,
            chunk_index=chunk_index,
            chunk_content="",
            is_end=True,
        )
        logger.debug(
            f"Emitting final chat response chunk {chat_response_dto} with index {chunk_index} "
            f"for party {party.party_id} to client {sid}"
        )
        await sio.emit(
            "party_response_chunk_ready", chat_response_dto.model_dump(), to=sid
        )

        # Build the full message
        if full_response is None:
            full_response_text = ""
        else:
            full_response_text = full_response.text

        full_response_text = sanitize_references(full_response_text)

        message_id = str(uuid.uuid4())
        chatbot_message = Message(
            id=message_id,
            role="assistant",
            content=full_response_text,
            sources=sources,
            party_id=party.party_id,
            current_chat_title=group_chat_session.title,
            quick_replies=[],
            rag_query=improved_rag_query_list,
        )
        group_chat_session.chat_history.append(chatbot_message)

        # Emit party response complete event
        party_response_complete_dto = PartyResponseCompleteDto(
            session_id=group_chat_session.session_id,
            party_id=party.party_id,
            complete_message=full_response_text,
            message_id=message_id,
            status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
        )
        logger.debug(f"Party response complete: {party_response_complete_dto}")
        await sio.emit(
            "party_response_complete", party_response_complete_dto.model_dump(), to=sid
        )
        logger.info(
            f"Party response {party_response_complete_dto.model_dump()} for {party.party_id} emitted to client {sid}"
        )

        # If it was a proposed question and we generated something new, cache it
        if cache_key is not None and cached_answer_to_emit is None:
            logger.info(
                f"Writing generated response to cache for party {party.party_id} and cache key {cache_key}"
            )
            cached_answer = CachedResponse(
                content=full_response_text,
                sources=sources,
                rag_query=improved_rag_query_list,
                created_at=datetime.now(),
                cached_conversation_history=cache_conversation_history_str,
                depth=len(group_chat_session.chat_history),
                user_message_depth=len(
                    [m for m in group_chat_session.chat_history if m.role == Role.USER]
                ),
            )
            await awrite_cached_answer_for_party(
                party.party_id, cache_key, cached_answer
            )
            logger.debug(f"Written cached answer: {cached_answer}")
    except openai.BadRequestError as e:
        logger.error(
            f"Error fetching and emitting party response for {party.party_id}: {e}",
            exc_info=True,
        )
        party_response_complete_dto = PartyResponseCompleteDto(
            session_id=group_chat_session.session_id,
            party_id=party.party_id,
            complete_message="Diese Frage kann ich leider nicht beantworten.",
            status=Status(
                indicator=StatusIndicator.ERROR,
                message=str(e),
            ),
        )
    except Exception as e:
        logger.error(
            f"Error fetching and emitting party response for {party.party_id}: {e}",
            exc_info=True,
        )
        party_response_complete_dto = PartyResponseCompleteDto(
            session_id=group_chat_session.session_id,
            party_id=party.party_id,
            complete_message="Es tut mir Leid, leider ist ein Fehler aufgetreten. Bitte versuche es später erneut.",
            status=Status(indicator=StatusIndicator.ERROR, message=str(e)),
        )
        await sio.emit(
            "party_response_complete", party_response_complete_dto.model_dump(), to=sid
        )
        return


async def process_party(
    party: ContextParty,
    chat_history_str: str,
    general_question: str,
    relevant_doc_dict: Dict[str, List[Document]],
    lock: asyncio.Lock,
    improved_rag_query_list: List[str],
    context_id: str,
):
    """Process a party's documents for comparison questions."""
    logger.debug(
        f"For Party {party.party_id} the relevant docs are being identified by coroutine"
    )

    improved_rag_query = await generate_improvement_rag_query(
        party, chat_history_str, general_question, context_id=context_id
    )

    relevant_docs = await identify_relevant_docs_with_llm_based_reranking(
        party=party,
        rag_query=improved_rag_query,
        chat_history=chat_history_str,
        user_message=general_question,
        context_id=context_id,
    )

    # Safely update the shared improved_rag_query list
    async with lock:
        improved_rag_query_list.append(improved_rag_query)

    # Safely update the shared dictionary
    async with lock:
        relevant_doc_dict[party.party_id] = relevant_docs


async def generate_chat_answer(
    sio: socketio.AsyncServer,
    sid: str,
    session_id: str,
    user_message_content: str,
    party_ids: list[str],
    user_is_logged_in: bool = False,
    message_id: Optional[str] = None,
) -> None:
    """
    Core chat answer generation logic.
    Handles session lookup, party selection, response generation, and quick replies.
    Used by both chat_answer_request and voice_message_request.
    """
    # Create user message
    user_message = Message(
        id=message_id,
        role="user",
        content=user_message_content,
    )

    # Access chat session from socket session
    try:
        async with sio.session(sid) as session:
            chat_session: GroupChatSession = session.get("chat_sessions", {}).get(
                session_id
            )
            if chat_session is None:
                raise ValueError(f"Chat session with ID {session_id} not found")

            # Update session with user message
            chat_history = chat_session.chat_history
            # Append the user message if it not identical to the last message
            if (
                len(chat_history) == 0
                or chat_history[-1].content != user_message.content
            ):
                chat_history.append(user_message)

            # check if the user message is in the last quick replies
            last_quick_replies = chat_session.last_quick_replies
            is_beginning_of_chat = len(chat_history) == 1
            logger.debug(f"Is beginning of chat: {is_beginning_of_chat}")
            if (
                not is_beginning_of_chat
                and user_message.content not in last_quick_replies
            ):
                # after the first user message only chat sessions that only use quick replies are cacheable
                chat_session.is_cacheable = False
    except Exception as e:
        logger.error(
            f"Error accessing chat session for client {sid}: {e}", exc_info=True
        )
        chat_response_complete_dto = ChatResponseCompleteDto(
            session_id=session_id,
            status=Status(
                indicator=StatusIndicator.ERROR,
                message="It seems like the chat session has not been started",
            ),
        )
        await sio.emit(
            "chat_response_complete",
            chat_response_complete_dto.model_dump(),
            to=sid,
        )
        return

    all_parties = await aget_parties_for_context(chat_session.context_id)
    pre_selected_parties = [
        party for party in all_parties if party.party_id in party_ids
    ]

    pre_selected_party_ids = [party.party_id for party in pre_selected_parties]
    logger.debug(f"Pre-selected party IDs: {pre_selected_party_ids}")

    chat_history_without_last_user_message = chat_history[:-1]
    chat_history_str = build_chat_history_string(
        chat_history_without_last_user_message, all_parties
    )

    try:
        (
            party_id_list,
            general_question,
            is_comparing_question,
        ) = await get_question_targets_and_type(
            user_message=user_message.content,
            previous_chat_history=chat_history_str,
            all_available_parties=all_parties + [WAHL_CHAT_PARTY],
            currently_selected_parties=pre_selected_parties,
        )
    except openai.BadRequestError as e:
        logger.error(
            f"Error identifying question targets and type: {e}",
            exc_info=True,
        )
        responding_parties_dto = RespondingPartiesDto(
            session_id=session_id,
            party_ids=[WAHL_CHAT_PARTY.party_id],
        )
        logger.debug(
            f"Emitting responding parties {responding_parties_dto.party_ids} to client {sid}"
        )
        await sio.emit(
            "responding_parties_selected",
            responding_parties_dto.model_dump(),
            to=sid,
        )
        party_response_complete_dto = PartyResponseCompleteDto(
            session_id=chat_session.session_id,
            party_id=WAHL_CHAT_PARTY.party_id,
            complete_message="Diese Frage kann ich leider nicht beantworten.",
            status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
        )
        await sio.emit(
            "party_response_complete", party_response_complete_dto.model_dump(), to=sid
        )
        chat_response_complete_dto = ChatResponseCompleteDto(
            session_id=session_id,
            status=Status(
                indicator=StatusIndicator.ERROR,
                message=f"Error identifying question targets and type: {e}",
            ),
        )
        await sio.emit(
            "chat_response_complete",
            chat_response_complete_dto.model_dump(),
            to=sid,
        )
        return

    logger.info(
        f"Identified question targets and type: party_id_list={party_id_list}, general_question={general_question}, is_comparing_question={is_comparing_question}"
    )

    if not party_id_list:
        logger.debug(f"No party IDs selected, defaulting to wahl-chat for client {sid}")
        party_id_list = ["wahl-chat"]
    elif is_beginning_of_chat and len(party_id_list) > 7:
        # If we are in the beginning of the chat, we only allow up to 7 party IDs for automatic selection
        # If more, we default to wahl-chat which will ask the user to select parties
        logger.debug(
            f"Too many party IDs selected at the beginning of the chat, defaulting to wahl-chat for client {sid}"
        )
        party_id_list = ["wahl-chat"]

    parties_to_respond = [
        party
        for party in all_parties + [WAHL_CHAT_PARTY]
        if party.party_id in party_id_list
    ]
    if not is_comparing_question:
        responding_parties_dto = RespondingPartiesDto(
            session_id=session_id,
            party_ids=party_id_list,
        )
    else:
        responding_parties_dto = RespondingPartiesDto(
            session_id=session_id,
            party_ids=["wahl-chat"],
        )
    logger.debug(
        f"Emitting responding parties {responding_parties_dto.party_ids} to client {sid}"
    )
    await sio.emit(
        "responding_parties_selected",
        responding_parties_dto.model_dump(),
        to=sid,
    )

    if len(parties_to_respond) == 1 or not is_comparing_question:
        party_coros = []
        for party in parties_to_respond:
            # get the proposed questions for the party
            proposed_questions_for_party = await aget_proposed_questions_for_party(
                party.party_id
            )
            proposed_questions_group = await aget_proposed_questions_for_party("group")

            is_proposed_question = (
                user_message.content in proposed_questions_for_party
                or user_message.content in proposed_questions_group
            )
            logger.debug(f"Is proposed question: {is_proposed_question}")
            if is_beginning_of_chat and not is_proposed_question:
                # chat sessions with custom initial questions are not cacheable
                chat_session.is_cacheable = False
            party_coros.append(
                fetch_and_emit_party_response(
                    sio,
                    sid,
                    party,
                    chat_history_str,
                    general_question,
                    chat_session,
                    all_available_parties=all_parties,
                    use_premium_llms=user_is_logged_in,
                    is_proposed_question=is_proposed_question,
                    is_cacheable_chat=chat_session.is_cacheable,
                )
            )
    else:
        # chat sessions with comparison answers are not cacheable for now
        chat_session.is_cacheable = False

        parties_being_compared = parties_to_respond
        relevant_doc_dict: dict[str, list] = {}
        improved_rag_query_list: list[str] = []
        lock = asyncio.Lock()

        party_tasks = [
            process_party(
                party,
                chat_history_str,
                general_question,
                relevant_doc_dict,
                lock,
                improved_rag_query_list,
                context_id=chat_session.context_id,
            )
            for party in parties_being_compared
        ]
        try:
            await asyncio.wait_for(
                asyncio.gather(*party_tasks),
                timeout=40,
            )
        except asyncio.TimeoutError as e:
            logger.error(f"Timeout while fetching the correct party documents: {e}")
            chat_response_complete_dto = ChatResponseCompleteDto(
                session_id=session_id,
                status=Status(
                    indicator=StatusIndicator.ERROR,
                    message="Timeout while fetching the correct party documents",
                ),
            )
            await sio.emit(
                "chat_response_complete",
                chat_response_complete_dto.model_dump(),
                to=sid,
            )
            return

        party_coros = []
        logger.info("Comparison response is being fetched by WAHL_CHAT_PARTY")

        party_coros.append(
            fetch_and_emit_party_response(
                sio,
                sid,
                WAHL_CHAT_PARTY,
                chat_history_str,
                user_message.content,
                chat_session,
                all_available_parties=all_parties,
                use_premium_llms=user_is_logged_in,
                is_cacheable_chat=chat_session.is_cacheable,
                relevant_docs=relevant_doc_dict,
                parties_being_compared=parties_being_compared,
                is_comparing_question=is_comparing_question,
                improved_rag_query_list=improved_rag_query_list,
            )
        )

    # wait for all coroutines to finish with a timeout
    try:
        await asyncio.wait_for(
            asyncio.gather(*party_coros),
            timeout=40,
        )
    except asyncio.TimeoutError as e:
        logger.error(f"Timeout while fetching party responses: {e}")
        chat_response_complete_dto = ChatResponseCompleteDto(
            session_id=session_id,
            status=Status(
                indicator=StatusIndicator.ERROR,
                message="Timeout while fetching party responses",
            ),
        )
        await sio.emit(
            "chat_response_complete",
            chat_response_complete_dto.model_dump(),
            to=sid,
        )
        return

    # Create a list of the parties that have been selected to respond and the parties that are already in the chat
    ids_of_parties_in_chat = set(pre_selected_party_ids + party_id_list)
    parties_in_chat = [
        party for party in all_parties if party.party_id in ids_of_parties_in_chat
    ]

    full_conversation_history_str = build_chat_history_string(chat_history, all_parties)

    try:
        chat_title_and_quick_replies = await generate_chat_title_and_chick_replies(
            chat_history_str=full_conversation_history_str,
            chat_title=chat_session.title or "Noch kein Titel vergeben",
            parties_in_chat=parties_in_chat,
            wahl_chat_assistant_last_responded=party_id_list
            == [WAHL_CHAT_PARTY.party_id],
            is_comparing=is_comparing_question,
        )
    except openai.BadRequestError as e:
        logger.error(
            f"Error generating chat title and quick replies: {e}", exc_info=True
        )
        chat_response_complete_dto = ChatResponseCompleteDto(
            session_id=session_id,
            status=Status(
                indicator=StatusIndicator.ERROR,
                message=f"Error generating chat title and quick replies: {e}",
            ),
        )
        await sio.emit(
            "chat_response_complete",
            chat_response_complete_dto.model_dump(),
            to=sid,
        )
        return

    quick_replies_and_title_dto = QuickRepliesAndTitleDto(
        session_id=chat_session.session_id,
        quick_replies=chat_title_and_quick_replies.quick_replies,
        title=chat_title_and_quick_replies.chat_title,
    )
    logger.debug(f"Emitting quick replies and title for client {sid}")
    await sio.emit(
        "quick_replies_and_title_ready",
        quick_replies_and_title_dto.model_dump(),
        to=sid,
    )
    chat_session.last_quick_replies = chat_title_and_quick_replies.quick_replies

    chat_response_complete_dto = ChatResponseCompleteDto(
        session_id=chat_session.session_id,
        status=Status(
            indicator=StatusIndicator.SUCCESS,
            message="Success",
        ),
    )
    await sio.emit(
        "chat_response_complete",
        chat_response_complete_dto.model_dump(),
        to=sid,
    )
