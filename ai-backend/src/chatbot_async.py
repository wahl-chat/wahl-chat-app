# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import logging
import os
from typing import AsyncIterator, List, Tuple, Dict
from datetime import datetime
from openai import AsyncOpenAI  # for API format

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.documents import Document
from langchain_core.messages import BaseMessageChunk

from openai.types.chat.chat_completion_message_param import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from src.models.general import LLM, LLMSize
from src.llms import (
    PRE_AND_POST_PROCESSING_LLMS,
    RESPONSE_GENERATION_LLMS,
    get_answer_from_llms,
    get_structured_output_from_llms,
    stream_answer_from_llms,
)
from src.firebase_service import aget_context_by_id
from src.models.context import DEFAULT_CONTEXT_ID
from src.models.context import ContextParty
from src.models.party import WAHL_CHAT_PARTY
from src.models.vote import Vote, VotingResultsByParty
from src.utils import (
    build_document_string_for_context,
    build_message_from_perplexity_response,
    build_party_str,
    load_env,
)
from src.prompts import (
    build_prompt_context,
    get_chat_answer_guidelines,
    get_wahl_chat_answer_guidelines,
    get_swiper_answer_guidelines,
    get_party_vote_behavior_summary_guidelines,
    get_quick_reply_guidelines,
    party_response_system_prompt_template,
    streaming_party_response_user_prompt_template,
    system_prompt_improvement_template,
    system_prompt_improve_general_chat_rag_query_template,
    user_prompt_improvement_template,
    perplexity_system_prompt,
    perplexity_user_prompt,
    determine_question_targets_system_prompt,
    determine_question_targets_user_prompt,
    determine_question_type_system_prompt,
    determine_question_type_user_prompt,
    generate_chat_summary_system_prompt,
    generate_chat_summary_user_prompt,
    generate_chat_title_and_quick_replies_system_prompt,
    generate_chat_title_and_quick_replies_user_prompt,
    generate_wahl_chat_title_and_quick_replies_system_prompt_str,
    party_comparison_system_prompt_template,
    generate_party_vote_behavior_summary_system_prompt,
    generate_party_vote_behavior_summary_user_prompt,
    system_prompt_improvement_rag_template_vote_behavior_summary,
    user_prompt_improvement_rag_template_vote_behavior_summary,
    wahl_chat_response_system_prompt_template,
    reranking_system_prompt_template,
    reranking_user_prompt_template,
    swiper_assistant_system_prompt_template,
    swiper_assistant_user_prompt_template,
    generate_swiper_assistant_title_and_quick_replies_system_prompt,
    generate_swiper_assistant_title_and_quick_replies_user_prompt_str,
)

from src.models.chat import Message
from src.models.structured_outputs import (
    ChatSummaryGenerator,
    GroupChatTitleQuickReplyGenerator,
    QuestionTypeClassifier,
    RerankingOutput,
    create_party_list_generator,
)

load_env()

logger = logging.getLogger(__name__)

chat_response_llms: list[LLM] = RESPONSE_GENERATION_LLMS

voting_behavior_summary_llms: list[LLM] = RESPONSE_GENERATION_LLMS

prompt_improvement_llms: list[LLM] = PRE_AND_POST_PROCESSING_LLMS

generate_party_list_llms: list[LLM] = PRE_AND_POST_PROCESSING_LLMS

generate_message_type_and_general_question_llms: list[LLM] = (
    PRE_AND_POST_PROCESSING_LLMS
)

generate_chat_summary_llms: list[LLM] = PRE_AND_POST_PROCESSING_LLMS

generate_chat_title_and_quick_replies_llms: list[LLM] = PRE_AND_POST_PROCESSING_LLMS

reranking_llms = PRE_AND_POST_PROCESSING_LLMS

perplexity_client = AsyncOpenAI(
    api_key=os.getenv("PERPLEXITY_API_KEY"), base_url="https://api.perplexity.ai"
)


async def rerank_documents(
    relevant_docs: List[Document], user_message: str, chat_history: str
) -> List[Document]:
    # get the context and the relevant documents
    docs = [
        build_document_string_for_context(index, doc, doc_num_label="Index")
        for index, doc in enumerate(relevant_docs)
    ]
    sources_str = "\n".join(docs)
    # build messages for the reranking model
    system_prompt = reranking_system_prompt_template.format(sources=sources_str)
    user_prompt = reranking_user_prompt_template.format(
        conversation_history=chat_history, user_message=user_message
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    # rerank the documents
    response = await get_structured_output_from_llms(
        reranking_llms, messages, RerankingOutput
    )

    # get the reranked document indices
    reranked_doc_indices = getattr(response, "reranked_doc_indices", [])
    logger.debug(f"Reranked document indices: {reranked_doc_indices}")
    try:
        # only take first 5 elements of relevant indices
        relevant_indices = reranked_doc_indices[:5]
        reranked_relevant_docs = [relevant_docs[i] for i in relevant_indices]
        logger.debug(f"Reranked document indices: {relevant_indices}")
        return reranked_relevant_docs
    except Exception as e:
        logger.error(f"Error extracting reranked documents: {e}")
        logger.warning("Returning top-5 of original relevant documents.")
        relevant_docs = relevant_docs[:5]
        return relevant_docs


async def get_question_targets_and_type(
    user_message: str,
    previous_chat_history: str,
    all_available_parties: List[ContextParty],
    currently_selected_parties: List[ContextParty],
) -> Tuple[List[str], str, bool]:
    if len(currently_selected_parties) == 0:
        currently_selected_parties = [WAHL_CHAT_PARTY]

    user_message_for_target_selection = user_message
    if previous_chat_history == "":
        previous_chat_history = f"Chat mit {', '.join([party.name for party in currently_selected_parties])} gestartet.\n"
        if currently_selected_parties != [WAHL_CHAT_PARTY]:
            user_message_for_target_selection = f"@{', '.join([party.name for party in currently_selected_parties])}: {user_message}"

    currently_selected_parties_str = ""
    for party in currently_selected_parties:
        currently_selected_parties_str += build_party_str(party)

    additionally_available_parties = [
        party
        for party in all_available_parties
        if party not in currently_selected_parties
    ]
    additional_party_list_str = ""
    big_additional_parties = [
        party for party in additionally_available_parties if not party.is_small_party
    ]
    small_additional_parties = [
        party for party in additionally_available_parties if party.is_small_party
    ]

    additional_party_list_str += "Große Parteien:\n"
    for party in big_additional_parties:
        additional_party_list_str += build_party_str(party)
    additional_party_list_str += "Kleinparteien:\n"
    for party in small_additional_parties:
        additional_party_list_str += build_party_str(party)

    system_prompt = determine_question_targets_system_prompt.format(
        current_party_list=currently_selected_parties_str,
        additional_party_list=additional_party_list_str,
    )
    user_prompt = determine_question_targets_user_prompt.format(
        previous_chat_history=previous_chat_history,
        user_message=user_message_for_target_selection,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    # Create dynamic PartyListGenerator with valid party IDs from context
    valid_party_ids = [party.party_id for party in all_available_parties]
    party_list_generator = create_party_list_generator(valid_party_ids)

    response_targets = await get_structured_output_from_llms(
        generate_party_list_llms, messages, party_list_generator
    )

    party_id_list = getattr(response_targets, "party_id_list", [])
    logger.debug(f"LLM returned party ID list: {party_id_list}")
    party_id_list = [
        str(party_id) for party_id in party_id_list
    ]  # make sure all party IDs are represented as strings (and not enums)
    # Make sure the party_id_list contains no duplicates
    party_id_list = list(set(party_id_list))

    if len(party_id_list) >= 2:
        # Filter out "wahl-chat" party from the list of selected parties
        party_id_list = [
            party_id
            for party_id in party_id_list
            if party_id != WAHL_CHAT_PARTY.party_id
        ]

    # create a prompt for the question type model
    if len(party_id_list) >= 2:
        system_prompt = determine_question_type_system_prompt.format()
        user_prompt = determine_question_type_user_prompt.format(
            previous_chat_history=previous_chat_history,
            user_message=f'Nutzer: "{user_message_for_target_selection}"',
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        response_question_type = await get_structured_output_from_llms(
            generate_message_type_and_general_question_llms,
            messages,
            QuestionTypeClassifier,
        )

        question_for_parties = getattr(
            response_question_type, "non_party_specific_question", user_message
        )
        is_comparing_question = getattr(
            response_question_type, "is_comparing_question", False
        )
    else:
        question_for_parties = user_message
        is_comparing_question = False

    return (party_id_list, question_for_parties, is_comparing_question)


async def generate_improvement_rag_query(
    party: ContextParty,
    conversation_history: str,
    last_user_message: str,
    context_id: str = DEFAULT_CONTEXT_ID,
) -> str:
    if party.party_id == WAHL_CHAT_PARTY.party_id:
        # Fetch context to get the context name for the template
        context = await aget_context_by_id(context_id)
        context_name = context.name if context else "Bundestagswahl 2025"
        system_prompt = system_prompt_improve_general_chat_rag_query_template.format(
            context_name=context_name
        )
    else:
        system_prompt = system_prompt_improvement_template.format(party_name=party.name)
    user_prompt = user_prompt_improvement_template.format(
        conversation_history=conversation_history,
        last_user_message=last_user_message,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    response = await get_answer_from_llms(prompt_improvement_llms, messages)

    if isinstance(response.content, list):
        if isinstance(response.content[0], str):
            return response.content[0]
        else:
            return response.content[0]["content"]
    return response.content


async def generate_pro_con_perspective(
    chat_history: List[Message], party: ContextParty, context_id: str | None = None
) -> Message:
    # from a list of Message elements, extract the last assistant and user message by checking the role
    last_assistant_message = next(
        (message for message in chat_history[::-1] if message.role == "assistant"), None
    )
    last_user_message = next(
        (message for message in chat_history[::-1] if message.role == "user"), None
    )

    # Get context information
    context = None
    if context_id:
        context = await aget_context_by_id(context_id)
    if context is None:
        context = await aget_context_by_id(DEFAULT_CONTEXT_ID)

    prompt_context = build_prompt_context(context) if context else {}
    now = datetime.now()

    system_prompt = perplexity_system_prompt.format(
        party_name=party.name,
        party_long_name=party.long_name,
        party_description=party.description,
        party_candidate=party.candidate,
        context_name=prompt_context.get("context_name", "Bundestagswahl 2025"),
        context_date_info=prompt_context.get(
            "context_date_info", "Kein spezifisches Datum"
        ),
        context_location=prompt_context.get("context_location", "Deutschland"),
        date=now.strftime("%Y-%m-%d"),
        time=now.strftime("%H:%M"),
    )
    user_prompt = perplexity_user_prompt.format(
        assistant_message=last_assistant_message.content
        if last_assistant_message
        else "",
        user_message=last_user_message.content if last_user_message else "",
        party_name=party.name,
    )

    # Prepare messages with explicit roles
    messages: list[
        ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam
    ] = [
        ChatCompletionSystemMessageParam(role="system", content=system_prompt),
        ChatCompletionUserMessageParam(role="user", content=user_prompt),
    ]

    # chat completion without streaming
    response = await perplexity_client.chat.completions.create(
        model="sonar",
        messages=messages,
    )

    return build_message_from_perplexity_response(response)


async def generate_chat_summary(chat_history: list[Message]) -> str:
    # create a list of messages from the chat history, user messages as "Nutzer: " and assistant messages use the party_id as role
    conversation_history = []
    for message in chat_history:
        if message.role == "user":
            conversation_history.append({"role": "Nutzer", "content": message.content})
        else:
            conversation_history.append(
                {"role": message.party_id or "", "content": message.content}
            )

    system_prompt = generate_chat_summary_system_prompt.format()
    user_prompt = generate_chat_summary_user_prompt.format(
        conversation_history=conversation_history
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    response = await get_structured_output_from_llms(
        generate_chat_summary_llms, messages, ChatSummaryGenerator
    )

    return getattr(
        response, "chat_summary", "Hier sollte eigentlich eine Zusammenfassung stehen."
    )


def get_rag_context(relevant_docs: List[Document]) -> str:
    rag_context = ""
    for doc_num, doc in enumerate(relevant_docs):
        context_obj = build_document_string_for_context(doc_num, doc)
        rag_context += context_obj
    if rag_context == "":
        rag_context = (
            "Keine relevanten Informationen in der Dokumentensammlung gefunden."
        )
    return rag_context


def get_rag_comparison_context(
    relevant_docs: Dict[str, List[Document]], relevant_parties: List[ContextParty]
) -> str:
    rag_context = ""
    doc_num = 0
    for party in relevant_parties:
        rag_context += f"\n\nInformationen von {party.name}:\n"
        for doc in relevant_docs[party.party_id]:
            context_obj = f"""- ID: {doc_num}
- Dokumentname: {doc.metadata.get("document_name", "unbekannt")}
- Partei: {party.name}
- Veröffentlichungsdatum: {doc.metadata.get("document_publish_date", "unbekannt")}
- Inhalt: "{doc.page_content}"

"""
            doc_num += 1
            rag_context += context_obj
    if rag_context == "":
        rag_context = (
            "Keine relevanten Informationen in der Dokumentensammlung gefunden."
        )
    return rag_context


async def get_improved_rag_query_voting_behavior(
    party: ContextParty, last_user_message: str, last_assistant_message: str
) -> str:
    system_prompt = system_prompt_improvement_rag_template_vote_behavior_summary.format(
        party_name=party.name
    )
    user_prompt = user_prompt_improvement_rag_template_vote_behavior_summary.format(
        last_user_message=last_user_message,
        last_assistant_message=last_assistant_message,
        party_name=party.name,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    response = await get_answer_from_llms(prompt_improvement_llms, messages)

    return getattr(response, "content", "")


async def generate_streaming_chatbot_response(
    party: ContextParty,
    conversation_history: str,
    user_message: str,
    relevant_docs: List[Document],
    all_parties: list[ContextParty],
    chat_response_llm_size: LLMSize,
    context_id: str = DEFAULT_CONTEXT_ID,
    use_premium_llms: bool = False,
) -> AsyncIterator[BaseMessageChunk]:
    rag_context = get_rag_context(relevant_docs)

    now = datetime.now()

    if party.party_id == WAHL_CHAT_PARTY.party_id:
        # Fetch context to get the context fields for the template
        context = await aget_context_by_id(context_id)
        prompt_context = build_prompt_context(context) if context else {}

        answer_guidelines = get_wahl_chat_answer_guidelines()
        all_parties_list = ""
        for p in all_parties:
            all_parties_list += f"### {p.long_name}\n"
            all_parties_list += f"Abkürzung: {p.name}\n"
            all_parties_list += f"Beschreibung: {p}\n"
            all_parties_list += (
                f"Spitzenkandidat*In für die Bundestagswahl 2025: {p.candidate}\n"
            )
        system_prompt = wahl_chat_response_system_prompt_template.format(
            context_name=prompt_context.get("context_name", "Bundestagswahl 2025"),
            context_date_info=prompt_context.get(
                "context_date_info", "Kein spezifisches Datum"
            ),
            context_location=prompt_context.get("context_location", "Deutschland"),
            all_parties_list=all_parties_list,
            date=now.strftime("%Y-%m-%d"),
            time=now.strftime("%H:%M"),
            rag_context=rag_context,
            answer_guidelines=answer_guidelines,
        )
    else:
        answer_guidelines = get_chat_answer_guidelines(party.name, is_comparing=False)
        system_prompt = party_response_system_prompt_template.format(
            party_name=party.name,
            party_long_name=party.long_name,
            party_description=party.description,
            party_url=party.website_url,
            party_candidate=party.candidate,
            date=now.strftime("%Y-%m-%d"),
            time=now.strftime("%H:%M"),
            rag_context=rag_context,
            answer_guidelines=answer_guidelines,
        )

    user_prompt = streaming_party_response_user_prompt_template.format(
        conversation_history=conversation_history,
        last_user_message=user_message,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    return await stream_answer_from_llms(
        chat_response_llms,
        messages,
        preferred_llm_size=chat_response_llm_size,
        use_premium_llms=use_premium_llms,
    )


async def generate_streaming_chatbot_comparing_response(
    party: ContextParty,
    conversation_history: str,
    user_message: str,
    relevant_docs: Dict[str, List[Document]],
    relevant_parties: List[ContextParty],
    chat_response_llm_size: LLMSize,
    use_premium_llms: bool = False,
) -> AsyncIterator[BaseMessageChunk]:
    rag_context = get_rag_comparison_context(relevant_docs, relevant_parties)

    now = datetime.now()

    answer_guidelines = get_chat_answer_guidelines(party.name, is_comparing=True)

    parties_being_compared = [party.name for party in relevant_parties]

    system_prompt = party_comparison_system_prompt_template.format(
        party_name=party.name,
        party_long_name=party.long_name,
        party_description=party.description,
        party_url=party.website_url,
        party_candidate=party.candidate,
        date=now.strftime("%Y-%m-%d"),
        time=now.strftime("%H:%M"),
        rag_context=rag_context,
        answer_guidelines=answer_guidelines,
        parties_being_compared=parties_being_compared,
    )

    user_prompt = streaming_party_response_user_prompt_template.format(
        conversation_history=conversation_history,
        last_user_message=user_message,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    return await stream_answer_from_llms(
        chat_response_llms,
        messages,
        preferred_llm_size=chat_response_llm_size,
        use_premium_llms=use_premium_llms,
    )


async def generate_chat_title_and_chick_replies(
    chat_history_str: str,
    chat_title: str,
    parties_in_chat: List[ContextParty],
    wahl_chat_assistant_last_responded: bool = False,
    is_comparing: bool = False,
) -> GroupChatTitleQuickReplyGenerator:
    # filter wahl-chat party out of the list of parties
    parties_in_chat = [
        party for party in parties_in_chat if party.party_id != WAHL_CHAT_PARTY.party_id
    ]
    party_list = ""
    for party in parties_in_chat:
        party_list += f"- {party.name} ({party.long_name}): {party.description}\n"
    if party_list == "":
        party_list = "Noch keine Parteien in diesem Chat."
    if wahl_chat_assistant_last_responded:
        system_prompt = (
            generate_wahl_chat_title_and_quick_replies_system_prompt_str.format(
                party_list=party_list,
                quick_reply_guidelines=get_quick_reply_guidelines(
                    is_comparing=is_comparing
                ),
            )
        )
    else:
        system_prompt = generate_chat_title_and_quick_replies_system_prompt.format(
            party_list=party_list
        )

    user_prompt = generate_chat_title_and_quick_replies_user_prompt.format(
        current_chat_title=chat_title,
        conversation_history=chat_history_str,
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    response = await get_structured_output_from_llms(
        generate_chat_title_and_quick_replies_llms,
        messages,
        GroupChatTitleQuickReplyGenerator,
    )
    return GroupChatTitleQuickReplyGenerator(
        chat_title=getattr(response, "chat_title", ""),
        quick_replies=getattr(response, "quick_replies", []),
    )


async def generate_party_vote_behavior_summary(
    party: ContextParty,
    last_user_message: str,
    last_assistant_message: str,
    votes: List[Vote],
    summary_llm_size: LLMSize,
    use_premium_llms: bool = False,
) -> AsyncIterator[BaseMessageChunk]:
    votes_list = ""
    # sort votes by date (oldest first)
    votes.sort(key=lambda x: x.date)
    for vote in votes:
        submitting_parties: str = "keine angegeben"
        if vote.submitting_parties is not None:
            submitting_parties = ", ".join(vote.submitting_parties)

        party_results = [
            party_vote
            for party_vote in vote.voting_results.by_party
            if party_vote.party == party.party_id
        ]
        if not party_results:
            continue

        party_result = party_results[0]

        votes_list += _format_vote_summary(
            vote,
            (vote.short_description or "Keine Zusammenfassung angegeben.")
            .replace("\n", " ")
            .strip(),
            party_result,
            submitting_parties,
            party.name,
        )

    if votes_list == "":
        votes_list = "Keine passenden Abstimmungen gefunden."

    answer_guidelines = get_party_vote_behavior_summary_guidelines()
    system_prompt = generate_party_vote_behavior_summary_system_prompt.format(
        party_name=party.name,
        party_long_name=party.long_name,
        votes_list=votes_list,
        answer_guidelines=answer_guidelines,
    )
    user_prompt = generate_party_vote_behavior_summary_user_prompt.format(
        user_message=last_user_message,
        assistant_message=last_assistant_message,
        party_name=party.name,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    return await stream_answer_from_llms(
        voting_behavior_summary_llms,
        messages,
        preferred_llm_size=summary_llm_size,
        use_premium_llms=use_premium_llms,
    )


def _format_vote_summary(
    vote: Vote,
    description: str,
    party_result: VotingResultsByParty,
    submitting_parties: str,
    party_name: str,
) -> str:
    return f"""
# Abstimmung {vote.id}
- Datum: {vote.date}
- Thema: {vote.title}
- Zusammenfassung: {description}
- Einbringende Parteien: {submitting_parties}
- Ergebnisse:
    - Insgesamt:
        - Ja: {vote.voting_results.overall.yes}
        - Nein: {vote.voting_results.overall.no}
        - Enthaltungen: {vote.voting_results.overall.abstain}
        - Nicht abgestimmt: {vote.voting_results.overall.not_voted}
        - Gesamtzahl der Mitglieder: {vote.voting_results.overall.members}
    - Abstimmungsverhalten der Partei {party_name}:
        - Ja: {party_result.yes}
        - Nein: {party_result.no}
        - Enthaltungen: {party_result.abstain}
        - Nicht abgestimmt: {party_result.not_voted}
        - Begründung: {party_result.justification if party_result.justification else "Keine Begründung angegeben."}\n\n
"""


async def generate_swiper_assistant_response(
    current_political_question: str,
    conversation_history: str,
    user_message: str,
    chat_response_llm_size: LLMSize,
) -> Message:
    now = datetime.now()
    answer_guidelines = get_swiper_answer_guidelines()
    system_prompt = swiper_assistant_system_prompt_template.format(
        date=now.strftime("%Y-%m-%d"),
        time=now.strftime("%H:%M"),
        answer_guidelines=answer_guidelines,
    )

    user_prompt = swiper_assistant_user_prompt_template.format(
        current_political_question=current_political_question,
        conversation_history=conversation_history,
        user_message=user_message,
    )

    # Prepare messages with explicit roles
    messages: list[
        ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam
    ] = [
        ChatCompletionSystemMessageParam(role="system", content=system_prompt),
        ChatCompletionUserMessageParam(role="user", content=user_prompt),
    ]

    # perplexity chat completion without streaming
    model = "sonar" if chat_response_llm_size == LLMSize.SMALL else "sonar-pro"
    response = await perplexity_client.chat.completions.create(
        model=model,
        messages=messages,
    )

    return build_message_from_perplexity_response(response)


async def generate_swiper_assistant_title_and_chick_replies(
    chat_history_str: str,
    current_political_question: str,
) -> GroupChatTitleQuickReplyGenerator:
    system_prompt = (
        generate_swiper_assistant_title_and_quick_replies_system_prompt.format(
            current_political_question=current_political_question,
            conversation_history=chat_history_str,
        )
    )

    user_prompt = (
        generate_swiper_assistant_title_and_quick_replies_user_prompt_str.format(
            current_political_question=current_political_question,
            conversation_history=chat_history_str,
        )
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    response = await get_structured_output_from_llms(
        generate_chat_title_and_quick_replies_llms,
        messages,
        GroupChatTitleQuickReplyGenerator,
    )
    return GroupChatTitleQuickReplyGenerator(
        chat_title=getattr(response, "chat_title", ""),
        quick_replies=getattr(response, "quick_replies", []),
    )
